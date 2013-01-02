#
# FLV Extract
# Copyright (C) 2006-2012  J.D. Purcell (moitah@yahoo.com)
# Python port by Gianluigi Tiesi <sherpya@netfarm.it>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

from general import BitConverterBE
from video import VideoWriter

class RawH264Writer(VideoWriter):
    __slots__  = [ '_fd', '_path', '_nalLengthSize' ]

    def __init__(self, path):
        self._path = path
        self._startCode = '\x00\x00\x00\x01'
        self._nalLengthSize = 0
        self._fd = open(path, 'wb')

    def WriteChunk(self, chunk, timeStamp=-1, frameType=-1):
        length = len(chunk)
        if length < 4: return

        # Reference: decode_frame from libavcodec's h264.c

        # header
        if chunk[0] == 0:
            if length < 10: return

            offset = 8

            self._nalLengthSize = (chunk[offset] & 0x03) + 1 ; offset += 1
            spsCount = chunk[offset] & 0x1f ; offset += 1
            ppsCount = -1

            while offset <= (length - 2):
                if (spsCount == 0) and (ppsCount == -1):
                    ppsCount = chunk[offset] ; offset += 1
                    continue

                if spsCount > 0: spsCount -= 1
                elif ppsCount > 0: ppsCount -= 1
                else: break

                clen = BitConverterBE.ToUInt16(chunk, offset)
                offset += 2
                if (offset + clen) > length: break
                self._fd.write(self._startCode)
                self._fd.write(chunk[offset:offset + clen])
                offset += clen

        # Video Data
        else:
            assert self._nalLengthSize
            offset = 4

            if self._nalLengthSize != 2:
                self._nalLengthSize = 4

            while offset <= (length - self._nalLengthSize):
                if self._nalLengthSize == 2:
                    clen = BitConverterBE.ToUInt16(chunk, offset)
                else:
                    clen = BitConverterBE.ToUInt32(chunk, offset)
                offset += self._nalLengthSize
                if (offset + clen) > length: break
                self._fd.write(self._startCode)
                self._fd.write(chunk[offset:])
                offset += clen

    def Finish(self, averageFrameRate):
        self._fd.close()
