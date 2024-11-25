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
from enum import IntEnum
from pathlib import Path
from typing import List, BinaryIO

from general import BitHelper
from interfaces import IAudioWriter

# http://www.mp3-tech.org/programmer/frame_header.html

MPEG1BitRate = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]
MPEG2XBitRate = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]
MPEG1SampleRate = [44100, 48000, 32000]
MPEG20SampleRate = [22050, 24000, 16000]
MPEG25SampleRate = [11025, 12000, 8000]


class MPEGVersion(IntEnum):
    MPEG25 = 0
    RESERVED = 1
    MPEG2 = 2
    MPEG1 = 3


class Layer(IntEnum):
    RESERVED = 0
    LAYER3 = 1
    LAYER2 = 2
    LAYER1 = 3


class Bitrate(IntEnum):
    FREE = 0
    BAD = 15


class Samplerate(IntEnum):
    RESERVED = 3


class ChannelMode(IntEnum):
    STEREO = 0
    JOINTSTEREO = 1
    DUALMONO = 2
    MONO = 3


class MP3Writer(IAudioWriter, ABC):
    _path: Path
    _fd: BinaryIO
    _warnings: List[str]
    _chunk_buffer: List[bytes]
    _frame_offsets: List[int]
    _total_frame_length: int = 0
    _is_vbr: bool = False
    _delay_write: bool
    _has_vbr_header: bool = False
    _write_vbr_header: bool = False
    _first_bit_rate: int = 0
    _mpeg_version: int = 0
    _sample_rate: int = 0
    _channel_mode: int = 0
    _first_frame_header: int = 0

    def __init__(self, path: Path, warnings: List[str]):
        self._path = path
        self._fd = self._path.open('wb')
        self._warnings = warnings
        self._delay_write = True
        self._chunk_buffer = []
        self._frame_offsets = []

    def write_chunk(self, chunk: bytes, timestamp: int) -> None:
        self._chunk_buffer.append(chunk)
        self.parse_mp3_frames(chunk)

        if self._delay_write and (self._total_frame_length >= 65536):
            self._delay_write = False
        if not self._delay_write:
            self.flush()

    def finish(self) -> None:
        self.flush()
        if self._write_vbr_header:
            self._fd.seek(0)
            self.write_vbr_header(False)
        self._fd.close()

    def flush(self) -> None:
        for chunk in self._chunk_buffer:
            self._fd.write(chunk)
        self._chunk_buffer = []

    def parse_mp3_frames(self, buff: bytes) -> None:
        offset = 0
        length = len(buff)

        while length >= 4:
            header = c_ulonglong(int.from_bytes(buff[offset:offset + 4], 'big') << 32)
            if BitHelper.read(header, 11) != 0x7ff:
                self._warnings.append('Invalid frame sync')
                break

            mpeg_version = BitHelper.read(header, 2)
            layer = BitHelper.read(header, 2)
            BitHelper.read(header, 1)
            bitrate = BitHelper.read(header, 4)
            samplerate = BitHelper.read(header, 2)
            padding = BitHelper.read(header, 1)
            channel_mode = BitHelper.read(header, 2)

            if (mpeg_version == MPEGVersion.RESERVED
                    or layer != 1
                    or bitrate in (Bitrate.FREE, Bitrate.BAD)
                    or samplerate == Samplerate.RESERVED):
                self._warnings.append(f'Malformed frame')
                break

            bitrate = (MPEG1BitRate[bitrate] if (mpeg_version == MPEGVersion.MPEG1) else MPEG2XBitRate[bitrate]) * 1000

            if mpeg_version == MPEGVersion.MPEG1:
                samplerate = MPEG1SampleRate[samplerate]
            elif mpeg_version == MPEGVersion.MPEG2:
                samplerate = MPEG20SampleRate[samplerate]
            else:
                samplerate = MPEG25SampleRate[samplerate]

            frame_len = self.get_frame_length(mpeg_version, bitrate, samplerate, padding)
            if frame_len > length:
                break

            is_vbr_header_frame = False
            if len(self._frame_offsets) == 0:
                o = offset + self.get_frame_data_offset(mpeg_version, channel_mode)
                if buff[o: o + 4] == b'Xing':
                    is_vbr_header_frame = True
                    self._delay_write = False
                    self._has_vbr_header = True

            if is_vbr_header_frame:
                pass
            elif self._first_bit_rate == 0:
                self._first_bit_rate = bitrate
                self._mpeg_version = mpeg_version
                self._sample_rate = samplerate
                self._channel_mode = channel_mode
                self._first_frame_header = int.from_bytes(buff[offset:offset + 4], 'big')
            elif not self._is_vbr and (bitrate != self._first_bit_rate):
                self._is_vbr = True
                if self._has_vbr_header:
                    pass
                elif self._delay_write:
                    self.write_vbr_header(True)
                    self._write_vbr_header = True
                    self._delay_write = False
                else:
                    self._warnings.append('Detected VBR too late, cannot add VBR header')

            self._frame_offsets.append(self._total_frame_length + offset)

            offset += frame_len
            length -= frame_len
        self._total_frame_length += len(buff)

    def write_vbr_header(self, is_placeholder: bool) -> None:
        buff = bytearray(self.get_frame_length(self._mpeg_version, 64000, self._sample_rate, 0))
        if not is_placeholder:
            header = self._first_frame_header
            data_offset = self.get_frame_data_offset(self._mpeg_version, self._channel_mode)
            header &= 0xffff0dff  # Clear bitrate and padding fields
            header |= 0x00010000  # Set protection bit (indicates that CRC is NOT present)
            header |= (5 if self._mpeg_version == MPEGVersion.MPEG1 else 8) << 12  # 64 kbit/sec

            buff[0:4] = header.to_bytes(4, 'big')
            buff[data_offset: data_offset + 4] = b'Xing'
            # Flags
            buff[data_offset + 4: data_offset + 4 + 4] = int.to_bytes(0x7, 4, 'big')
            # Frame count
            buff[data_offset + 8:data_offset + 8 + 4] = len(self._frame_offsets).to_bytes(4, 'big')
            # File Length
            buff[data_offset + 12:data_offset + 12 + 4] = self._total_frame_length.to_bytes(4, 'big')

            for i in range(100):
                frame_index = int((i / 100.0) * len(self._frame_offsets))
                buff[data_offset + 16 + i] = int(self._frame_offsets[frame_index] / self._total_frame_length * 250)
        self._fd.write(buff)

    @staticmethod
    def get_frame_length(mpeg_version: int, bitrate: int, samplerate: int, padding: int) -> int:
        return ((144 if (mpeg_version == MPEGVersion.MPEG1) else 72) * bitrate // samplerate) + padding

    @staticmethod
    def get_frame_data_offset(mpeg_version: int, channel_mode: int) -> int:
        if mpeg_version == MPEGVersion.MPEG1:
            o = 17 if (channel_mode == ChannelMode.MONO) else 32
        else:
            o = 9 if (channel_mode == ChannelMode.MONO) else 17
        return o + 4
