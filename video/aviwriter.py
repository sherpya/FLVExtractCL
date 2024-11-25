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
from fractions import Fraction
from os import SEEK_CUR
from pathlib import Path
from typing import List

from general import BitHelper
from interfaces import IVideoWriter, VideoCodecID, FLVException


class VideoSizes:
    CIF = (352, 288)
    QCIF = (176, 144)
    SQCIF = (128, 96)
    QVGA = (320, 240)
    QQVGA = (160, 120)


class AVIWriter(IVideoWriter, ABC):
    # Chunk:          Off:  Len:
    #
    # RIFF AVI          0    12
    #   LIST hdrl      12    12
    #     avih         24    64
    #     LIST strl    88    12
    #       strh      100    64
    #       strf      164    48
    #   LIST movi     212    12
    #     (frames)    224   ???
    #   idx1          ???   ???

    _codec_id: int = 0
    _width: int = 0
    _height: int = 0
    _frame_count: int = 0
    _movi_data_size: int = 0
    _index_chunk_size: int = 0
    _index: List[int]
    _is_alpha_writer: bool = False
    _alpha_writer: 'AVIWriter | None' = None
    _warnings: List[str]

    @property
    def fourcc(self) -> bytes:
        match self._codec_id:
            case VideoCodecID.H263:
                return b'FLV1'
            case VideoCodecID.VP6 | VideoCodecID.VP6v2:
                return b'VP6F'
            case VideoCodecID.SCREEN | VideoCodecID.SCREENv2:  # FIXME: v2?
                return b'FSV1'
            case _:
                raise FLVException(f'Invalid codec ID {self._codec_id}')

    def __init__(self, path: Path, codec_id: int, warnings: List[str], is_alpha_writer: bool = False):
        if codec_id not in (VideoCodecID.H263, VideoCodecID.VP6, VideoCodecID.VP6v2):
            raise FLVException('Unsupported video codec')

        self._path = path
        self._fd = self._path.open('wb')
        self._codec_id = codec_id
        self._warnings = warnings
        self._is_alpha_writer = is_alpha_writer

        if codec_id == VideoCodecID.VP6v2 and not self._is_alpha_writer:
            self._alpha_writer = AVIWriter(self._path.with_suffix('.alpha.avi'), codec_id, warnings, True)

        self._fd.write(b'RIFF')
        self._fd.write(int.to_bytes(0, 4, 'little'))  # chunk size
        self._fd.write(b'AVI ')

        self._fd.write(b'LIST')
        self._fd.write(int.to_bytes(192, 4, 'little'))
        self._fd.write(b'hdrl')

        self._fd.write(b'avih')
        self._fd.write(int.to_bytes(56, 4, 'little'))
        self._fd.write(int.to_bytes(0, 4, 'little'))
        self._fd.write(int.to_bytes(0, 4, 'little'))
        self._fd.write(int.to_bytes(0, 4, 'little'))
        self._fd.write(int.to_bytes(0x10, 4, 'little'))
        self._fd.write(int.to_bytes(0, 4, 'little'))  # frame count
        self._fd.write(int.to_bytes(0, 4, 'little'))
        self._fd.write(int.to_bytes(1, 4, 'little'))
        self._fd.write(int.to_bytes(0, 4, 'little'))
        self._fd.write(int.to_bytes(0, 4, 'little'))  # width
        self._fd.write(int.to_bytes(0, 4, 'little'))  # height
        self._fd.write(int.to_bytes(0, 4, 'little'))
        self._fd.write(int.to_bytes(0, 4, 'little'))
        self._fd.write(int.to_bytes(0, 4, 'little'))
        self._fd.write(int.to_bytes(0, 4, 'little'))

        self._fd.write(b'LIST')
        self._fd.write(int.to_bytes(116, 4, 'little'))
        self._fd.write(b'strl')

        self._fd.write(b'strh')
        self._fd.write(int.to_bytes(56, 4, 'little'))
        self._fd.write(b'vids')
        self._fd.write(self.fourcc)
        self._fd.write(int.to_bytes(0, 4, 'little'))
        self._fd.write(int.to_bytes(0, 4, 'little'))
        self._fd.write(int.to_bytes(0, 4, 'little'))
        self._fd.write(int.to_bytes(0, 4, 'little'))  # frame rate denominator
        self._fd.write(int.to_bytes(0, 4, 'little'))  # frame rate numerator
        self._fd.write(int.to_bytes(0, 4, 'little'))
        self._fd.write(int.to_bytes(0, 4, 'little'))  # frame count
        self._fd.write(int.to_bytes(0, 4, 'little'))
        self._fd.write(int.to_bytes(-1, 4, 'little', signed=True))
        self._fd.write(int.to_bytes(0, 4, 'little'))
        self._fd.write(int.to_bytes(0, 2, 'little'))
        self._fd.write(int.to_bytes(0, 2, 'little'))
        self._fd.write(int.to_bytes(0, 2, 'little'))  # width
        self._fd.write(int.to_bytes(0, 2, 'little'))  # height

        self._fd.write(b'strf')
        self._fd.write(int.to_bytes(40, 4, 'little'))
        self._fd.write(int.to_bytes(40, 4, 'little'))
        self._fd.write(int.to_bytes(0, 4, 'little'))  # width
        self._fd.write(int.to_bytes(0, 4, 'little'))  # height
        self._fd.write(int.to_bytes(1, 2, 'little'))
        self._fd.write(int.to_bytes(24, 2, 'little'))

        self._fd.write(self.fourcc)
        self._fd.write(int.to_bytes(0, 4, 'little'))  # biSizeImage
        self._fd.write(int.to_bytes(0, 4, 'little'))
        self._fd.write(int.to_bytes(0, 4, 'little'))
        self._fd.write(int.to_bytes(0, 4, 'little'))
        self._fd.write(int.to_bytes(0, 4, 'little'))

        self._fd.write(b'LIST')
        self._fd.write(int.to_bytes(0, 4, 'little'))  # chunk size
        self._fd.write(b'movi')

        self._index = []

    def write_chunk(self, chunk: bytes, timestamp: int, frame_type: int) -> None:
        offset = 0
        length = len(chunk)

        if self._codec_id == VideoCodecID.VP6:
            offset = 1
            length -= 1
        elif self._codec_id == VideoCodecID.VP6v2:
            offset = 4
            if length >= 4:
                alpha_offset = int.from_bytes(chunk[:4], 'big') & 0xffffff
                if not self._is_alpha_writer:
                    length = alpha_offset
                else:
                    offset += alpha_offset
                    length -= offset
            else:
                length = 0

        length = max(length, 0)
        length = min(length, len(chunk) - offset)

        self._index.append(0x10 if (frame_type == 1) else 0)
        self._index.append(self._movi_data_size + 4)
        self._index.append(length)

        if (self._width == 0) and (self._height == 0):
            self.get_frame_size(chunk)

        self._fd.write(b'00dc')
        self._fd.write(length.to_bytes(4, 'little', signed=True))
        self._fd.write(chunk[offset:offset + length])

        if (length % 2) != 0:
            self._fd.write(b'\x00')
            length += 1

        self._movi_data_size += length + 8
        self._frame_count += 1

        if self._alpha_writer is not None:
            self._alpha_writer.write_chunk(chunk, timestamp, frame_type)

    def get_frame_size(self, chunk: bytes) -> None:
        match self._codec_id:
            case VideoCodecID.H263:
                # Reference: flv_h263_decode_picture_header from libavcodec's h263.c
                if len(chunk) < 10:
                    return

                x = c_ulonglong(int.from_bytes(chunk[2:2 + 8], 'big'))

                if BitHelper.read(x, 1) != 1:
                    return

                BitHelper.read(x, 5)
                BitHelper.read(x, 8)

                format_ = BitHelper.read(x, 3)

                match format_:
                    case 0:
                        self._width = BitHelper.read(x, 8)
                        self._height = BitHelper.read(x, 8)
                    case 1:
                        self._width = BitHelper.read(x, 16)
                        self._height = BitHelper.read(x, 16)
                    case 2:
                        self._width, self._height = VideoSizes.CIF
                    case 3:
                        self._width, self._height = VideoSizes.QCIF
                    case 4:
                        self._width, self._height = VideoSizes.SQCIF
                    case 5:
                        self._width, self._height = VideoSizes.QVGA
                    case 6:
                        self._width, self._height = VideoSizes.QQVGA
                    case _:
                        return

            case VideoCodecID.SCREEN | VideoCodecID.SCREENv2:  # FIXME: v2?
                # Reference: flashsv_decode_frame from libavcodec's flashsv.c
                # notice: libavcodec checks if width/height changes
                if len(chunk) < 4:
                    return

                x = c_ulonglong(int.from_bytes(chunk[:4], 'big') << 32)
                BitHelper.read(x, 4)  # blockWidth
                self._width = BitHelper.read(x, 12)
                BitHelper.read(x, 4)  # blockHeight
                self._height = BitHelper.read(x, 12)

                # header = int.from_bytes(chunk[:4], byteorder='big')
                # _block_width = (header >> 28) & 0xf  # first 4 bits
                # self._width = (header >> 16) & 0xf  # next 12 bits
                # _block_height = (header >> 12) & 0xf  # next 4 bits
                # self._height = header & 0xfff  # last 12 bits

            case VideoCodecID.VP6 | VideoCodecID.VP6v2:
                # Reference: vp6_parse_header from libavcodec's vp6.c
                skip = 1 if (self._codec_id == VideoCodecID.VP6) else 4
                if len(chunk) < (skip + 8):
                    return

                x = c_ulonglong(int.from_bytes(chunk[skip:skip + 8], 'big'))
                delta_frame_lag = BitHelper.read(x, 1)
                _quant = BitHelper.read(x, 6)
                separated_coeff_flag = BitHelper.read(x, 1)
                _sub_version = BitHelper.read(x, 5)
                filter_header = BitHelper.read(x, 2)
                _interlaced_flag = BitHelper.read(x, 1)

                if delta_frame_lag != 0:
                    return

                if separated_coeff_flag != 0 or filter_header == 0:  # skip 16 bit
                    BitHelper.read(x, 16)

                self._height = BitHelper.read(x, 8) * 16
                self._width = BitHelper.read(x, 8) * 16

                # chunk[0] contains the width and height (4 bits each, respectively) that should
                # be cropped off during playback, which will be non-zero if the encoder padded
                # the frames to a macroblock boundary.  But if you use this adjusted size in the
                # AVI header, DirectShow seems to ignore it, and it can cause stride or chroma
                # alignment problems with VFW if the width/height aren't multiples of 4.
                if not self._is_alpha_writer:
                    crop_x = chunk[0] >> 4
                    crop_y = chunk[0] & 0xf
                    if (crop_x != 0) or (crop_y != 0):
                        self._warnings.append(
                            f'Suggested cropping: {crop_x} pixels from right, {crop_y} pixels from bottom')

    def write_index_chunk(self) -> None:
        index_data_size = self._frame_count * 16

        self._fd.write(b'idx1')
        self._fd.write(index_data_size.to_bytes(4, 'little'))

        for i in range(self._frame_count):
            self._fd.write(b'00dc')
            self._fd.write(self._index[(i * 3) + 0].to_bytes(4, 'little'))
            self._fd.write(self._index[(i * 3) + 1].to_bytes(4, 'little'))
            self._fd.write(self._index[(i * 3) + 2].to_bytes(4, 'little'))

        self._index_chunk_size = index_data_size + 8

    def finish(self, average_framerate: Fraction) -> None:
        self.write_index_chunk()

        self._fd.seek(4)
        self._fd.write(
            int.to_bytes(224 + self._movi_data_size + self._index_chunk_size - 8, 4, 'little'))

        self._fd.seek(24 + 8)
        self._fd.write(int.to_bytes(0, 4, 'little'))
        self._fd.seek(12, SEEK_CUR)
        self._fd.write(self._frame_count.to_bytes(4, 'little'))
        self._fd.seek(12, SEEK_CUR)
        self._fd.write(self._width.to_bytes(4, 'little'))
        self._fd.write(self._height.to_bytes(4, 'little'))

        self._fd.seek(100 + 28)
        self._fd.write(average_framerate.denominator.to_bytes(4, 'little'))
        self._fd.write(average_framerate.numerator.to_bytes(4, 'little'))
        self._fd.seek(4, SEEK_CUR)
        self._fd.write(self._frame_count.to_bytes(4, 'little'))
        self._fd.seek(16, SEEK_CUR)
        self._fd.write(self._width.to_bytes(2, 'little'))
        self._fd.write(self._height.to_bytes(2, 'little'))

        self._fd.seek(164 + 12)
        self._fd.write(self._width.to_bytes(4, 'little'))
        self._fd.write(self._height.to_bytes(4, 'little'))
        self._fd.seek(8, SEEK_CUR)
        self._fd.write(int.to_bytes(self._width * self._height * 6, 4, 'little'))

        self._fd.seek(212 + 4)
        self._fd.write(int.to_bytes(self._movi_data_size + 4, 4, 'little'))

        self._fd.close()

        if self._alpha_writer is not None:
            self._alpha_writer.finish(average_framerate)
