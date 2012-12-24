from ctypes import BigEndianStructure, c_uint
from struct import pack, unpack_from

from audio import AudioWriter

MPEG1BitRate        = [ 0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320 ]
MPEG2XBitRate       = [ 0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160 ]
MPEG1SampleRate     = [ 44100, 48000, 32000 ]
MPEG20SampleRate    = [ 22050, 24000, 16000 ]
MPEG25SampleRate    = [ 11025, 12000, 8000 ]

class MPEGVersion:
    MPEG25      = 0b00
    RESERVED    = 0b01
    MPEG2       = 0b10
    MPEG1       = 0b11

class LAYER:
    RESERVED    = 0b00
    LAYER3      = 0b01
    LAYER2      = 0b10
    LAYER1      = 0b11

class BITRATE:
    FREE        = 0b0000
    BAD         = 0b1111

class SAMPLERATE:
    RESERVED    = 0b11

class MP3FrameHeader(BigEndianStructure):
    _fields_ = [
                  ('frameSync',     c_uint, 11),
                  ('mpegVersion',   c_uint, 2),
                  ('layer',         c_uint, 2),
                  ('protectionBit', c_uint, 1),
                  ('bitRate',       c_uint, 4),
                  ('sampleRate',    c_uint, 2),
                  ('paddingBit',    c_uint, 1),
                  ('privateBit',    c_uint, 1),
                  ('channelMode',   c_uint, 2),
                  ('modeExt',       c_uint, 2),
                  ('copyright',     c_uint, 1),
                  ('original',      c_uint, 1),
                  ('emphasis',      c_uint, 2)
                  ]

class MP3Writer(AudioWriter):
    __slots__  = [ '_fd', '_path', '_warnings', '_chunkBuffer', '_delayWrite', '_writeVBRHeader', '_totalFrameLength' ]
    __slots__ += [ '_frameOffsets', '_isVBR', '_hasVBRHeader', '_firstBitRate' ]
    __slots__ += [ '_mpegVersion', '_sampleRate', '_channelMode', '_firstFrameHeader' ]

    def __init__(self, path, warnings):
        self._path = path
        self._warnings = warnings
        self._delayWrite = True

        self._chunkBuffer = []
        self._frameOffsets = []

        self._isVBR = self._hasVBRHeader = self._writeVBRHeader = False
        self._firstBitRate = 0
        self._totalFrameLength = 0
        self._mpegVersion = self._sampleRate = self._channelMode = self._firstFrameHeader = 0

        self._fd = open(path, 'wb')

    def WriteChunk(self, chunk, size=None):
        self._chunkBuffer.append(chunk)
        self.ParseMP3Frames(chunk)

        if self._delayWrite and (self._totalFrameLength >= 65536):
            self._delayWrite = False
        if not self._delayWrite:
            self.Flush()

    def Finish(self):
        self.Flush()

        if self._writeVBRHeader:
            self._fd.seek(0)
            self.WriteVBRHeader(False)
        self._fd.close()

    def Flush(self):
        for chunk in self._chunkBuffer:
            self._fd.write(chunk)
        self._chunkBuffer = []

    def ParseMP3Frames(self, buff):
        offset = 0
        length = len(buff)

        while length >= 4:
            hdr = MP3FrameHeader.from_buffer_copy(buff, offset)

            if hdr.frameSync != 0b11111111111:
                print 'Invalid framesync', bin(hdr.frameSync)
                break

            if hdr.mpegVersion == MPEGVersion.RESERVED \
                or hdr.layer != LAYER.LAYER3 \
                or hdr.bitRate in (BITRATE.FREE, BITRATE.BAD) \
                or hdr.sampleRate == SAMPLERATE.RESERVED:
                print 'Invalid frame values'
                break

            bitRate = (MPEG1BitRate[hdr.bitRate] if (hdr.mpegVersion == MPEGVersion.MPEG1) else MPEG2XBitRate[hdr.bitRate]) * 1000
            if hdr.mpegVersion == MPEGVersion.MPEG1:
                sampleRate = MPEG1SampleRate[hdr.sampleRate]
            elif hdr.mpegVersion == MPEGVersion.MPEG2:
                sampleRate = MPEG20SampleRate[hdr.sampleRate]
            else:
                sampleRate = MPEG25SampleRate[hdr.sampleRate]

            frameLen = self.GetFrameLength(hdr.mpegVersion, bitRate, sampleRate, hdr.paddingBit)
            if frameLen > length:
                break

            isVBRHeaderFrame = False
            if len(self._frameOffsets) == 0:
                o = offset + self.GetFrameDataOffset(hdr.mpegVersion, hdr.channelMode)
                if buff[o:o + 4] == 'Xing':
                    isVBRHeaderFrame = True
                    self._delayWrite = False
                    self._hasVBRHeader = True

            if isVBRHeaderFrame:
                pass
            elif self._firstBitRate == 0:
                self._firstBitRate = bitRate
                self._mpegVersion = hdr.mpegVersion
                self._sampleRate = sampleRate
                self._channelMode = hdr.channelMode
                self._firstFrameHeader = unpack_from('>H', buff, offset)[0]
            elif not self._isVBR and (bitRate != self._firstBitRate):
                self._isVBR = True
                if self._hasVBRHeader:
                    pass
                elif self._delayWrite:
                    self.WriteVBRHeader(True)
                    self._writeVBRHeader = True
                    self._delayWrite = False
                else:
                    self._warnings.append('Detected VBR too late, cannot add VBR header')

            self._frameOffsets.append(self._totalFrameLength + offset)

            offset += frameLen
            length -= frameLen
        self._totalFrameLength += len(buff)

    def WriteVBRHeader(self, isPlaceholder):
        buff = bytearray(self.GetFrameLength(self._mpegVersion, 64000, self._sampleRate, 0))
        if not isPlaceholder:
            header = self._firstFrameHeader
            dataOffset = self.GetFrameDataOffset(self._mpegVersion, self._channelMode)
            header &= 0xffff0dff    # Clear bitrate and padding fields
            header |= 0x00010000    # Set protection bit (indicates that CRC is NOT present)
            header |= (5 if self._mpegVersion == MPEGVersion.MPEG1 else 8) << 12 # 64 kbit/sec

            pos = 0                 ; buff[pos:pos + 4] = pack('>H', header)

            pos = dataOffset        ; buff[pos:pos + 4] = 'Xing'
            pos = dataOffset + 4    ; buff[pos:pos + 4] = pack('>H', 0x7) # Flags
            pos = dataOffset + 8    ; buff[pos:pos + 4] = pack('>H', len(self._frameOffsets)) # Frame count
            pos = dataOffset + 12   ; buff[pos:pos + 4] = pack('>H', self._totalFrameLength) # File Length 

            for i in xrange(100):
                frameIndex = int((i / 100.0) * len(self._frameOffsets))
                buff[dataOffset + 16 + i] = (self._frameOffsets[frameIndex] / float(self._totalFrameLength) * 250)
        self._fd.write(buff)

    @staticmethod
    def GetFrameLength(mpegVersion, bitRate, sampleRate, padding):
        return ((144 if (mpegVersion == 3) else 72) * bitRate / sampleRate) + padding

    @staticmethod
    def GetFrameDataOffset(mpegVersion, channelMode):
        if mpegVersion == MPEGVersion.MPEG1:
            o = 17 if (channelMode == 3) else 32
        else:
            o = 9 if (channelMode == 3) else 17
        return o + 4
