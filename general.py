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

from ctypes import c_int, c_uint, c_ulong, c_ulonglong

class BitHelper(object):
    @staticmethod
    def Read(x, length):
        r = c_int(x.value >> (64 - length))
        x.value <<= length
        return r.value

    @staticmethod
    def ReadB(_bytes, offset, length):
        startByte = offset.value / 8
        endByte = (offset.value + length - 1) / 8
        skipBits = offset.value % 8
        bits = c_ulong()

        for i in xrange(min(endByte - startByte, 7) + 1):
            bits.value |= _bytes[startByte + i] << (56 - (i * 8))

        if skipBits != 0: BitHelper.Read(bits, skipBits)
        offset.value += length
        return BitHelper.Read(bits, length)

    @staticmethod
    def Write(x, length, value):
        mask = c_ulonglong(0xffffffffffffffffL >> (64 - length))
        x.value = (x.value << length) | (value & mask.value)

    @staticmethod
    def CopyBlock(_bytes, offset, length):
        startByte = offset / 8
        endByte = (offset + length - 1) / 8
        shiftA = offset % 8
        shiftB = 8 - shiftA

        dst = bytearray((length + 7) / 8)
        dstsize = len(dst)

        if shiftA == 0:
            dst[0:dstsize] = _bytes[startByte:startByte + dstsize]
        else:
            for i in xrange(endByte - startByte):
                dst[i] = ((_bytes[startByte + i] << shiftA) | (_bytes[startByte + i + 1] >> shiftB)) & 0xff
            if i < dstsize:
                dst[i] = (_bytes[startByte + i] << shiftA) & 0xff

        dst[dstsize - 1] &= 0xff << ((dstsize * 8) - length)

        return dst

_lut = {}
for i in xrange(256):
    x = c_uint(i << 24)
    for j in xrange(8):
        if x.value & 0x80000000:
            x.value = (x.value << 1) ^ 0x04c11db7
        else:
            x.value = x.value << 1
    _lut[i] = x.value

class OggCRC(object):
    @staticmethod
    def Calculate(buff, offset, length):
        crc = c_uint()
        for i in xrange(length):
            crc.value = _lut[((crc.value >> 24) ^ buff[offset + i]) & 0xff] ^ (crc.value << 8)
        return crc.value