# FLV Extract
# Copyright (C) 2006-2012 J.D. Purcell (moitah@yahoo.com)
# Python port (C) 2012-2024 Gianluigi Tiesi <sherpya@gmail.com>
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
from abc import ABC
from fractions import Fraction
from pathlib import Path

from interfaces import IVideoWriter

START_CODE = b'\x00\x00\x00\x01'


class RawH264Writer(IVideoWriter, ABC):
    _nal_length_size: int = 0

    def __init__(self, path: Path):
        self._path = path
        self._fd = self._path.open('wb')

    def write_chunk(self, chunk: bytes, timestamp: int, frame_type: int) -> None:
        length = len(chunk)
        if length < 4:
            return

        # Reference: decode_frame from libavcodec's h264.c

        # header
        if chunk[0] == 0:
            if length < 10:
                return

            offset = 8

            self._nal_length_size = (chunk[offset] & 0x03) + 1
            offset += 1
            sps_count = chunk[offset] & 0x1f
            offset += 1
            pps_count = -1

            while offset <= (length - 2):
                if (sps_count == 0) and (pps_count == -1):
                    pps_count = chunk[offset]
                    offset += 1
                    continue

                if sps_count > 0:
                    sps_count -= 1
                elif pps_count > 0:
                    pps_count -= 1
                else:
                    break

                len_ = int.from_bytes(chunk[offset:offset + 2], 'big')
                offset += 2
                if (offset + len_) > length:
                    break
                self._fd.write(START_CODE)
                self._fd.write(chunk[offset:offset + len_])
                offset += len_
        else:  # Video Data
            offset = 4

            if self._nal_length_size != 2:
                self._nal_length_size = 4

            while offset <= (length - self._nal_length_size):
                if self._nal_length_size == 2:
                    len_ = int.from_bytes(chunk[offset:offset + 2], 'big')
                else:
                    len_ = int.from_bytes(chunk[offset:offset + 4], 'big')
                offset += self._nal_length_size
                if (offset + len_) > length:
                    break
                self._fd.write(START_CODE)
                self._fd.write(chunk[offset:offset + len_])
                offset += len_

    def finish(self, average_framerate: Fraction) -> None:
        self._fd.close()
