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

from ctypes import c_int, c_uint, c_ulonglong


class BitHelper:
    @staticmethod
    def read(x: c_ulonglong, length: int) -> int:
        r = c_int(x.value >> (64 - length))
        x.value <<= length
        return r.value

    @staticmethod
    def read_frombytes(bytes_: bytes, offset: c_int, length: int) -> int:
        start_byte = offset.value // 8
        end_byte = (offset.value + length - 1) // 8
        skip_bits = offset.value % 8
        bits = c_ulonglong(0)

        for i in range(min(end_byte - start_byte, 7) + 1):
            bits.value |= bytes_[start_byte + i] << (56 - (i * 8))

        if skip_bits != 0:
            BitHelper.read(bits, skip_bits)

        offset.value += length
        return BitHelper.read(bits, length)

    @staticmethod
    def write(x: c_ulonglong, length: int, value: int) -> None:
        mask = c_ulonglong(0xffffffffffffffff >> (64 - length))
        x.value = (x.value << length) | (value & mask.value)

    @staticmethod
    def copy_block(bytes_: bytes, offset: int, length: int) -> bytearray:
        start_byte = offset // 8
        end_byte = (offset + length - 1) // 8
        shift_a = offset % 8
        shift_b = 8 - shift_a

        dst = bytearray((length + 7) // 8)
        dstsize = len(dst)

        if shift_a == 0:
            dst[0:dstsize] = bytes_[start_byte: start_byte + dstsize]
        else:
            i = 0
            for i in range(end_byte - start_byte):
                dst[i] = ((bytes_[start_byte + i] << shift_a) | (bytes_[start_byte + i + 1] >> shift_b)) & 0xff
            if i < dstsize:
                dst[i] = (bytes_[start_byte + i] << shift_a) & 0xff

        dst[dstsize - 1] &= 0xff << ((dstsize * 8) - length)

        return dst


def make_table(i: int) -> int:
    x = c_uint(i << 24)
    for _ in range(8):
        if x.value & 0x80000000:
            x.value = (x.value << 1) ^ 0x04c11db7
        else:
            x.value = x.value << 1
    return x.value


_lut = [make_table(x) for x in range(256)]


class OggCRC(object):
    @staticmethod
    def calculate(buff: bytes, offset: int, length: int) -> int:
        crc = c_uint()
        for i in range(length):
            crc.value = _lut[((crc.value >> 24) ^ buff[offset + i]) & 0xFF] ^ (crc.value << 8)
        return crc.value
