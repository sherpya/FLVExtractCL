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
from ctypes import c_ulonglong
from pathlib import Path
from struct import unpack

from general import BitHelper
from interfaces import IAudioWriter, FLVException


class AACWriter(IAudioWriter, ABC):
    _aac_profile: int
    _samplerate_index: int
    _channel_config: int

    def __init__(self, path: Path):
        self._path = path
        self._fd = self._path.open('wb')

    def write_chunk(self, chunk: bytes, timestamp: int) -> None:
        length = len(chunk)
        if length < 1:
            return

        # Header
        if chunk[0] == 0:
            if length > 3:
                return

            uint16_be = unpack('>H', chunk[1:3])[0]
            bits = c_ulonglong(uint16_be << 48)

            # 0: MAIN - 1: LC - 2: SSR - 3: LTP
            self._aac_profile = BitHelper.read(bits, 5) - 1
            self._samplerate_index = BitHelper.read(bits, 4)
            self._channel_config = BitHelper.read(bits, 4)

            if not (0 <= self._aac_profile <= 3):
                raise FLVException('Unsupported AAC profile.')
            if self._samplerate_index > 12:
                raise FLVException('Invalid AAC sample rate index.')
            if self._channel_config > 6:
                raise FLVException('Invalid AAC channel configuration.')
        else:  # Audio data
            data_size = length - 1
            bits = c_ulonglong()

            # Reference: WriteADTSHeader from FAAC's bitstream.c
            BitHelper.write(bits, 12, 0xfff)  # sync -> always 111111111111
            BitHelper.write(bits, 1, 0)  # id -> 0: MPEG-4 - 1: MPEG-2
            BitHelper.write(bits, 2, 0)  # layer always 00
            BitHelper.write(bits, 1, 1)  # protection absent
            BitHelper.write(bits, 2, self._aac_profile)
            BitHelper.write(bits, 4, self._samplerate_index)
            BitHelper.write(bits, 1, 0)  # private bit
            BitHelper.write(bits, 3, self._channel_config)
            BitHelper.write(bits, 1, 0)  # original/copy
            BitHelper.write(bits, 1, 0)  # home
            # ADTS Variable header
            BitHelper.write(bits, 1, 0)  # copyright identification bit
            BitHelper.write(bits, 1, 0)  # copyright identification start
            BitHelper.write(bits, 13, 7 + data_size)  # Length of the frame incl. header
            BitHelper.write(bits, 11, 0x7ff)  # ADTS buffer fullness, 0x7ff indicates VBR
            BitHelper.write(bits, 2, 0)  # No raw data block in frame

            self._fd.write(int.to_bytes(bits.value, 8, 'big')[1:1 + 7])
            self._fd.write(chunk[1:1 + data_size])

    def finish(self) -> None:
        self._fd.close()
