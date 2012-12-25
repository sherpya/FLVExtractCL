from struct import unpack_from

from video import VideoWriter

class RawH264Writer(VideoWriter):
    __slots__  = [ '_fd', '_path' ]

    def __init__(self, path):
        self._path = path
        self._startCode = '\x00\x00\x00\x01'
        self._fd = open(path, 'wb')

    __slots__ += [ '_nalLengthSize' ]
    def WriteChunk(self, chunk, timeStamp=-1, frameType=-1):
        length = len(chunk)
        if length < 4: return

        # Reference: decode_frame from libavcodec's h264.c

        # header
        if (chunk[0] == '\x00') and (length >= 10):
            offset = 8

            self._nalLengthSize = (ord(chunk[offset]) & 0x03) + 1 ; offset += 1            
            spsCount = ord(chunk[offset]) & 0x1f ; offset += 1
            ppsCount = -1

            while offset <= (length - 2):
                if (spsCount == 0) and (ppsCount == -1):
                    ppsCount = ord(chunk[offset]) ; offset += 1
                    continue

                if spsCount > 0: spsCount -= 1
                elif ppsCount > 0: ppsCount -= 1
                else: break

                clen = unpack_from('>H', chunk, offset)[0]
                offset += 2
                if (offset + clen) > length: break
                self._fd.write(self._startCode)
                self._fd.write(chunk[offset:])
                offset += clen

        # Video Data
        else:
            offset = 4

            if self._nalLengthSize != 2:
                self._nalLengthSize = 4

            while offset <= (length - self._nalLengthSize):
                fmt = '>H' if (self._nalLengthSize == 2) else '>I'
                clen = unpack_from(fmt, chunk, offset)[0]
                offset += self._nalLengthSize
                if (offset + clen) > length: break
                self._fd.write(self._startCode)
                self._fd.write(chunk[offset:])
                offset += clen

    def Finish(self, averageFrameRate):
        self._fd.close()
