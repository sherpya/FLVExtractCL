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

#def GetMask(size):
#    return (1 << size) - 1

#def BitGet(x, length, size=64):
#    r = x >> (size - length)
#    x = (x << length) & GetMask(size)
#    return (x, r)

#def BitSet(x, length, value, size=64):
#    mask = GetMask(size) >> (size - length)
#    return (x << length) | (value & mask)

from ctypes import c_int, c_ulonglong

class BitHelper(object):
    @staticmethod
    def Read(x, length):
        r = c_int(x.value >> (64 - length))
        x.value <<= length
        return r.value

    @staticmethod
    def Write(x, length, value):
        mask = c_ulonglong(0xffffffffffffffffL >> (64 - length))
        x.value = (x.value << length) | (value & mask.value)
