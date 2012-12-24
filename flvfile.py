import os
from struct import unpack
from fractions import Fraction

from audio import *
from video import *

class FLVException(Exception):
    pass

class DummyWriter(object):
    def WriteChunk(self, *args):
        pass
    def Write(self, *args):
        pass
    def Finish(self, *args):
        pass
    def GetPath(self):
        return None

class TAG(object):
    AUDIO = 0x08
    VIDEO = 0x09

class FLVFile(object):
    __slots__  = [ '_fd', '_inputPath', '_outputDir', '_fileOffset', '_fileLength' ]
    __slots__ += [ '_audioWriter', '_videoWriter', '_timeCodeWriter', '_warnings' ]

    def __init__(self, inputPath):
        self._inputPath = inputPath
        self._outputDir = '.' #os.path.dirname(inputPath) # FIXME
        self._fileOffset = 0
        self._fileLength = os.path.getsize(self._inputPath)
        self._audioWriter = self._videoWriter = self._timeCodeWriter = None
        self._warnings = []

        self._fd = open(inputPath, 'rb')

    def Dispose(self):
        self._fd.close()
        self.CloseOutput(None, True)

    def Close(self):
        self.Dispose()

    __slots__ += [ '_outputPathBase', '_overwrite', '_extractAudio', '_extractVideo', '_extractTimeCodes', '_videoTimeStamps' ]
    __slots__ += [ '_averageFrameRate', '_trueFrameRate' ]
    def ExtractStreams(self, extractAudio, extractVideo, extractTimeCodes, overwrite):
        self._outputPathBase = os.path.join(self._outputDir, os.path.basename(self._inputPath))
        self._overwrite = overwrite
        self._extractAudio = extractAudio
        self._extractVideo = extractVideo
        self._extractTimeCodes = extractTimeCodes
        self._videoTimeStamps = []

        self.Seek(0)

        if self._fd.read(4) != 'FLV\x01':
            raise FLVException('Not a flv file') 

        if not os.path.isdir(self._outputDir):
            raise FLVException('Ouput directory doesn\'t exists or not a directory')

        flags = self.ReadUInt8()
        dataOffset = self.ReadUInt32()

        self.Seek(dataOffset)

        prevTagSize = self.ReadUInt32()
        while self._fileOffset < self._fileLength:
            if not self.ReadTag(): break
            if (self._fileLength - self._fileOffset) < 4: break
            prevTagSize = self.ReadUInt32()

        self._averageFrameRate = self.CalculateAverageFrameRate();
        self._trueFrameRate = self.CalculateTrueFrameRate();

        self.CloseOutput(self._averageFrameRate, False);

    def CloseOutput(self, averageFrameRate, disposing):
        if self._videoWriter is not None:
            self._videoWriter.Finish(averageFrameRate if averageFrameRate else Fraction(25, 1))
            if disposing and self._videoWriter.GetPath() is not None:
                os.unlink(self._videoWriter.GetPath())
            self._videoWriter = None

        if self._audioWriter is not None:
            self._audioWriter.Finish()
            if disposing and self._audioWriter.GetPath() is not None:
                os.unlink(self._audioWriter.GetPath())
            self._audioWriter = None

        if self._timeCodeWriter is not None:
            self._timeCodeWriter.Finish()
            if disposing and self._timeCodeWriter.GetPath() is not None:
                os.unlink(self._timeCodeWriter.GetPath())
            self._timeCodeWriter = None

    def GetAudioWriter(self, mediaInfo):
        format = mediaInfo >> 4
        rate = (mediaInfo >> 2) & 0x3
        bits = (mediaInfo >> 1) & 0x1
        chans = mediaInfo & 0x1

        if format in (SOUNDFORMAT.MP3, SOUNDFORMAT.MP3_8k):
            path = self._outputPathBase + '.mp3'
            return MP3Writer(path, self._warnings)
        elif format in (SOUNDFORMAT.PCM, SOUNDFORMAT.PCM_LE):
            return DummyWriter()
        elif format == SOUNDFORMAT.AAC:
            return DummyWriter()
        elif format == SOUNDFORMAT.SPEEX:
            return DummyWriter()
        else:
            self._warnings.append('Unsupported Sound Format %d' % format)
            return DummyWriter()

    def GetVideoWriter(self, mediaInfo):
        codecID = mediaInfo & 0x0f
        if codecID in (CODEC.H263, CODEC.VP6, CODEC.VP6v2): # -> AVI
            path = self._outputPathBase + '.avi'
            return AVIWriter(path, codecID, self._warnings)
        elif codecID == CODEC.H264: # -> H264 raw
            return DummyWriter()
        else:
            self._warnings.append('Unsupported codecID %d' % codecID)
            return DummyWriter()

    __slots__ += [ '_extractedAudio', '_extractedVideo', '_extractedTimeCodes' ]
    def ReadTag(self):
        if (self._fileLength - self._fileOffset) < 11:
            return False

        # Read tag header
        tagType = self.ReadUInt8()
        dataSize = self.ReadUInt24()
        timeStamp = self.ReadUInt24()
        timeStamp |= self.ReadUInt8() << 24
        streamID = self.ReadUInt24()

        # Read tag data
        if dataSize == 0:
            return True

        if (self._fileLength - self._fileOffset) < dataSize:
            return False

        mediaInfo = self.ReadUInt8()
        dataSize -= 1;
        data = self.ReadBytes(dataSize)

        if tagType == TAG.AUDIO:
            if self._audioWriter is None:
                if self._extractAudio:
                    self._audioWriter = self.GetAudioWriter(mediaInfo)
                    self._extractedAudio = True
                else:
                    self._audioWriter = DummyWriter()
                    self._extractedAudio = False
            self._audioWriter.WriteChunk(data, timeStamp)

        elif tagType == TAG.VIDEO: # and ((mediaInfo >> 4) != 5))
            if self._videoWriter is None:
                if self._extractVideo:
                    self._videoWriter = self.GetVideoWriter(mediaInfo)
                    self._extractedVideo = True
                else:
                    self._videoWriter = DummyWriter()
                    self._extractedVideo = False

            if self._timeCodeWriter is None: # FIXME
                self._timeCodeWriter = DummyWriter()
                self._extractedTimeCodes = False

            self._videoTimeStamps.append(timeStamp)
            self._videoWriter.WriteChunk(data, timeStamp, (mediaInfo & 0xf0) >> 4)
            self._timeCodeWriter.Write(timeStamp)

        return True

    def CanWriteTo(self, path):
        return not os.path.exists(path) or self._overwrite

    def CalculateAverageFrameRate(self):
        frameCount = len(self._videoTimeStamps)
        if frameCount > 1:
            n = (frameCount - 1) * 1000 # TODO: cast uint32_t
            d = self._videoTimeStamps[frameCount - 1] - self._videoTimeStamps[0]
            return Fraction(n, d)
        return None

    # TODO
    def CalculateTrueFrameRate(self):
        return self.CalculateAverageFrameRate()

    def Seek(self, offset):
        self._fd.seek(offset)
        self._fileOffset = offset

    def ReadUInt8(self):
        return ord(self.ReadBytes(1))

    def ReadUInt24(self):
        data = '\x00' + self.ReadBytes(3)
        return unpack('>I', data)[0]

    def ReadUInt32(self):
        return unpack('>I', self.ReadBytes(4))[0]

    def ReadBytes(self, size):
        self._fileOffset += size
        return self._fd.read(size)
