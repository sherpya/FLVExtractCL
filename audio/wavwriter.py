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
from pathlib import Path
from typing import BinaryIO

from interfaces import IAudioWriter


class WAVWriter(IAudioWriter, ABC):
    _path: Path
    block_align: int

    _fd: BinaryIO
    _wrote_headers = False
    _bits_per_sample: int
    _channel_count: int
    _samplerate: int
    _block_align: int
    _final_sample_len = 0
    _sample_len = 0

    def __init__(self, path: Path, bits_per_sample: int, channel_count: int, samplerate: int):
        self._path = path

        # WAVTools.WAVWriter
        self._fd = self._path.open('wb')
        self._bits_per_sample = bits_per_sample
        self._channel_count = channel_count
        self._samplerate = samplerate
        self._block_align = self._channel_count * (self._bits_per_sample + 7) // 8
        # WAVTools.WAVWriter

        # wtf
        self.block_align = (bits_per_sample // 8) * channel_count

    def write_chunk(self, chunk: bytes, timestamp: int) -> None:
        self.write(chunk, len(chunk) // self.block_align)

    def finish(self) -> None:
        # WAVTools.WAVWriter
        if ((self._sample_len * self._block_align) & 1) == 1:
            self._fd.write(b'\x00')

        if self._sample_len != self._final_sample_len:
            data_chunk_size = self.get_data_chunk_size(self._sample_len)
            self._fd.seek(4)
            self._fd.write((data_chunk_size + (data_chunk_size & 1) + 36).to_bytes(4, 'little'))
            self._fd.seek(40)
            self._fd.write(data_chunk_size.to_bytes(4, 'little'))

        self._fd.close()

    def write_headers(self) -> None:
        data_chunk_size = self.get_data_chunk_size(self._final_sample_len)

        self._fd.write(b'RIFF')
        self._fd.write((data_chunk_size + (data_chunk_size & 1) + 36).to_bytes(4, 'little'))
        self._fd.write(b'WAVE')
        self._fd.write(b'fmt ')
        self._fd.write(int.to_bytes(16, 4, 'little'))
        self._fd.write(int.to_bytes(1, 2, 'little'))
        self._fd.write(self._channel_count.to_bytes(2, 'little'))
        self._fd.write(self._samplerate.to_bytes(4, 'little'))
        self._fd.write((self._samplerate * self._block_align).to_bytes(4, 'little'))
        self._fd.write(self._block_align.to_bytes(2, 'little'))
        self._fd.write(self._bits_per_sample.to_bytes(2, 'little'))
        self._fd.write(b'data')
        self._fd.write(data_chunk_size.to_bytes(4, 'little'))

    def get_data_chunk_size(self, sample_count: int) -> int:
        max_file_size = 0x7ffffffe

        data_size = sample_count * self._block_align
        if (data_size + 44) > max_file_size:
            data_size = ((max_file_size - 44) // self._block_align) * self._block_align
        return data_size

    def write(self, buff: bytes, sample_count: int) -> None:
        if sample_count <= 0:
            return

        if not self._wrote_headers:
            self.write_headers()
            self._wrote_headers = True

        self._fd.write(buff[:sample_count * self._block_align])
        self._sample_len += sample_count
