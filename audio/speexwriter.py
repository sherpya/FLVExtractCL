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
from ctypes import c_int
from dataclasses import dataclass
from pathlib import Path
from typing import List, BinaryIO

from general import BitHelper, OggCRC
from interfaces import IAudioWriter, FLVException


@dataclass
class OggPacket:
    data: bytes
    granule_position: int


VENDOR_STRING = b'FLV Extract Py'
SAMPLERATE = 16000
MS_PER_FRAME = 20
SAMPLES_PER_FRAME = SAMPLERATE // (1000 // MS_PER_FRAME)
TARGET_PAGE_DATA_SIZE = 4096

SUB_MODE_SIZES = [0, 43, 119, 160, 220, 300, 364, 492, 79]
WIDE_BAND_SIZES = [0, 36, 112, 192, 352]
IN_BAND_SIGNAL_SIZES = [1, 1, 4, 4, 4, 4, 4, 4, 8, 8, 16, 16, 32, 32, 64, 64]


class InvalidSpeexData(FLVException):
    pass


class SpeexWriter(IAudioWriter, ABC):
    _path: Path
    _fd: BinaryIO
    _serial_number: int
    _packet_list: List[OggPacket]
    _packet_list_data_size: int
    _page_buff: bytearray
    _page_buff_offset: int
    _page_sequence_number: int
    _granule_position: int

    def __init__(self, path: Path, serial_number: int):
        self._path = path
        self._serial_number = serial_number
        self._fd = self._path.open('wb')
        self._fd.seek((28 + 80) + (28 + 8 + len(VENDOR_STRING)))  # Speex header + Vorbis comment
        self._packet_list = []
        self._packet_list_data_size = 0
        # Header + max segment table + target data size + extra segment
        self._page_buff = bytearray(27 + 255 + TARGET_PAGE_DATA_SIZE + 254)
        self._page_buff_offset = 0
        self._page_sequence_number = 2  # First audio packet
        self._granule_position = 0

    def write_chunk(self, chunk: bytes, timestamp: int) -> None:
        frame_start = -1
        frame_end = 0
        offset = c_int(0)
        length = len(chunk) * 8

        while (length - offset.value) >= 5:
            x = BitHelper.read_frombytes(chunk, offset, 1)
            if x != 0:
                # wideband frame
                x = BitHelper.read_frombytes(chunk, offset, 3)
                if not 1 <= x <= 4:
                    raise InvalidSpeexData
                offset.value += WIDE_BAND_SIZES[x] - 4
            else:
                x = BitHelper.read_frombytes(chunk, offset, 4)
                if 1 <= x <= 8:
                    # narrowband frame
                    if frame_start != -1:
                        self.write_frame_packet(chunk, frame_start, frame_end)
                    frame_start = frame_end
                    offset.value += SUB_MODE_SIZES[x] - 5
                elif x == 15:
                    # terminator
                    break
                elif x == 14:
                    # in-band signal
                    if (length - offset.value) < 4:
                        raise InvalidSpeexData
                    x = BitHelper.read_frombytes(chunk, offset, 4)
                    offset.value += IN_BAND_SIGNAL_SIZES[x]
                elif x == 13:
                    # custom in-band signal
                    if (length - offset.value) < 5:
                        raise InvalidSpeexData
                    x = BitHelper.read_frombytes(chunk, offset, 5)
                    offset.value += x * 8
                else:
                    raise InvalidSpeexData

            frame_end = offset.value

        if offset.value > length:
            raise InvalidSpeexData

        if frame_start != -1:
            self.write_frame_packet(chunk, frame_start, frame_end)

    def finish(self) -> None:
        self.write_page()
        self.flush_page(True)
        self._fd.seek(0)
        self._page_sequence_number = 0
        self._granule_position = 0
        self.write_speex_header_packet()
        self.write_vorbis_comment_packet()
        self.flush_page(False)
        self._fd.close()

    def write_frame_packet(self, data: bytes, start_bit: int, end_bit: int) -> None:
        length_bits = end_bit - start_bit
        frame = BitHelper.copy_block(data, start_bit, length_bits)

        if (length_bits % 8) != 0:
            frame[-1] |= 0xff >> ((length_bits % 8) + 1)  # padding

        self.add_packet(frame, SAMPLES_PER_FRAME, True)

    def write_speex_header_packet(self) -> None:
        data = bytearray(80)
        data[0:8] = b'Speex   '  # speex_string
        data[8:8 + 7] = b'unknown'  # speex_version
        data[28] = 1  # speex_version_id
        data[32] = 80  # header_size
        data[36:36 + 4] = SAMPLERATE.to_bytes(4, 'big')  # rate
        data[40] = 1  # mode (e.g. narrowband, wideband)
        data[44] = 4  # mode_bitstream_version
        data[48] = 1  # nb_channels
        data[52:52 + 4] = int.to_bytes(0xffffffff, 4, 'big')  # -1: bitrate
        data[56:56 + 4] = SAMPLES_PER_FRAME.to_bytes(4, 'big')  # frame_size
        data[60] = 0  # vbr
        data[64] = 1  # frames_per_packet
        self.add_packet(data, 0, False)

    def write_vorbis_comment_packet(self) -> None:
        length = len(VENDOR_STRING)
        data = bytearray(8 + length)
        data[0] = length
        data[4:4 + length] = VENDOR_STRING
        self.add_packet(data, 0, False)

    def add_packet(self, data: bytes, sample_length: int, delay_write: bool) -> None:
        length = len(data)
        if length >= 255:
            raise FLVException('Packet exceeds maximum size')

        self._granule_position += sample_length
        packet = OggPacket(data=data, granule_position=self._granule_position)
        self._packet_list.append(packet)
        self._packet_list_data_size += length

        if not delay_write or (self._packet_list_data_size >= TARGET_PAGE_DATA_SIZE) or (len(self._packet_list) == 255):
            self.write_page()

    def write_page(self) -> None:
        numPackets = len(self._packet_list)
        if numPackets == 0:
            return
        self.flush_page(False)
        self.write_to_page(b'OggS', 0, 4)

        self.write_to_page_uint8(0)  # Stream structure version
        self.write_to_page_uint8(0x02 if (self._page_sequence_number == 0) else 0)  # Page flags
        self.write_to_page_uint64(self._packet_list[-1].granule_position)  # Position in samples
        self.write_to_page_uint32(self._serial_number)  # Stream serial number
        self.write_to_page_uint32(self._page_sequence_number)  # Page sequence number
        self.write_to_page_uint32(0)  # Checksum
        self.write_to_page_uint8(numPackets)  # Page segment count

        for packet in self._packet_list:
            self.write_to_page_uint8(len(packet.data))

        for packet in self._packet_list:
            self.write_to_page(packet.data, 0, len(packet.data))

        self._packet_list = []
        self._packet_list_data_size = 0
        self._page_sequence_number += 1

    def flush_page(self, is_last_page: bool) -> None:
        if self._page_buff_offset == 0:
            return

        if is_last_page:
            self._page_buff[5] |= 0x04

        crc = OggCRC.calculate(self._page_buff, 0, self._page_buff_offset)
        self._page_buff[22: 22 + 4] = crc.to_bytes(4, 'little')
        self._fd.write(self._page_buff[:self._page_buff_offset])
        self._page_buff_offset = 0

    def write_to_page(self, data: bytes, offset: int, length: int) -> None:
        self._page_buff[self._page_buff_offset: self._page_buff_offset + length] = data[offset: offset + length]
        self._page_buff_offset += length

    def write_to_page_uint8(self, value: int) -> None:
        self.write_to_page(bytearray([value]), 0, 1)

    def write_to_page_uint32(self, value: int) -> None:
        self.write_to_page(value.to_bytes(4, 'little'), 0, 4)

    def write_to_page_uint64(self, value: int) -> None:
        self.write_to_page(value.to_bytes(8, 'little'), 0, 8)
