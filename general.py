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

from os import SEEK_SET
from struct import pack, unpack_from
from ctypes import c_int, c_uint, c_ulong, c_ulonglong

class Writer(object):
    __slots__ = [ '_path', '_fd']
    def __init__(self, path, mode='wb'):
        self._path = path
        self._fd = open(self._path, mode)

    def Write(self, buff, offset=0, size=None):
        if size is None: size = len(buff) - offset
        buff = buff[offset:offset + size]
        assert len(buff) == size
        self._fd.write(buff)

    def WriteFourCC(self, fourCC):
        if len(fourCC) != 4:
            raise Exception('Invalid fourCC length')
        self.Write(fourCC)

    def Seek(self, pos, whence=SEEK_SET):
        self._fd.seek(pos, whence)

    def Close(self):
        self._fd.close()

    def GetPath(self):
        return self._path

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

class BitConverterBE(object):
    @staticmethod
    def ToUInt16(buff, offset=0):
        return unpack_from('>H', str(buff[offset:offset + 2]))[0]

    @staticmethod
    def FromUInt32(value):
        return pack('>I', value)

    @staticmethod
    def ToUInt32(buff, offset=0):
        return unpack_from('>I', str(buff[offset:offset + 4]))[0]

    @staticmethod
    def FromUInt64(value):
        return pack('>Q', value)

    @staticmethod
    def ToUInt64(buff, offset=0):
        return unpack_from('>Q', str(buff[offset:offset + 8]))[0]


class BitConverterLE(object):
    @staticmethod
    def FromUInt16(value):
        return pack('<H', value)

    @staticmethod
    def FromUInt32(value):
        return pack('<I', value)

    @staticmethod
    def FromInt32(value):
        return pack('<i', value)

    @staticmethod
    def FromUInt64(value):
        return pack('<Q', value)

_lut = {}
def makeTable(i):
    x = c_uint(i << 24)
    for _ in xrange(8):
        if x.value & 0x80000000:
            x.value = (x.value << 1) ^ 0x04c11db7
        else:
            x.value = x.value << 1
    return x.value

_lut = map(makeTable, xrange(256))

class OggCRC(object):
    @staticmethod
    def Calculate(buff, offset, length):
        crc = c_uint()
        for i in xrange(length):
            crc.value = _lut[((crc.value >> 24) ^ buff[offset + i]) & 0xff] ^ (crc.value << 8)
        return crc.value
