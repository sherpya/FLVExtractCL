from struct import unpack_from

from bitops import BitGet, BitSet
from audio import AudioWriter

class AACWriter(AudioWriter):
    __slots__  = [ '_fd', '_path', '_warnings' ]

    def __init__(self, path, warnings):
        self._path = path
        self._warnings = warnings
        self._fd = open(path, 'wb')

    __slots__ += [ '_aacProfile', '_sampleRateIndex', '_channelConfig' ]
    def WriteChunk(self, chunk, size=None):
        length = len(chunk)
        if length < 1: return

        # header
        if (chunk[0] == '\x00') and (length >= 3):
            bits = unpack_from('>H', chunk, 1)[0] << 48

            # 0: MAIN - 1: LC - 2: SSR - 3: LTP
            bits, self._aacProfile = BitGet(bits, 5)
            bits, self._sampleRateIndex = BitGet(bits, 4)
            bits, self._channelConfig = BitGet(bits, 4)

            self._aacProfile -= 1

            if not (0 <= self._aacProfile <= 3):
                raise Exception('Unsupported AAC profile')
            if self._sampleRateIndex > 12:
                raise Exception('Invalid AAC sample rate index')
            if self._channelConfig > 6:
                raise Exception('Invalid AAC channel configuration')

        # data
        else:
            dataSize = length - 1

            bits = 0L
            bits = BitSet(bits, 12, 0xfff)                  # sync -> always 111111111111
            bits = BitSet(bits,  1, 0)                      # id -> 0: MPEG-4 - 1: MPEG-2
            bits = BitSet(bits,  2, 0)                      # layer always 00
            bits = BitSet(bits,  1, 1)                      # protection absent
            bits = BitSet(bits,  2, self._aacProfile)
            bits = BitSet(bits,  4, self._sampleRateIndex)
            bits = BitSet(bits,  1, 0)                      # private bit
            bits = BitSet(bits,  3, self._channelConfig)
            bits = BitSet(bits,  1, 0)                      # original/copy
            bits = BitSet(bits,  1, 0)                      # home
            # ADTS Variable header
            bits = BitSet(bits,  1, 0)                      # copyright identification bit
            bits = BitSet(bits,  1, 0)                      # copyright identification start
            bits = BitSet(bits, 13, 7 + dataSize)           # Length of the frame incl. header
            bits = BitSet(bits, 11, 0x7ff)                  # ADTS buffer fullness, 0x7ff indicates VBR
            bits = BitSet(bits,  2, 0)                      # No raw data block in frame

            self._fd.write(('%x' % bits).decode('hex'))
            self._fd.write(chunk[1:])

    def Finish(self):
        self._fd.close()
