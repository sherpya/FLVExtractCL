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

from ctypes import c_ulonglong

from general import BitHelper, BitConverterBE
from audio import AudioWriter

class AACWriter(AudioWriter):
    __slots__  = [ '_fd', '_path', '_warnings' ]

    def __init__(self, path, warnings):
        self._path = path
        self._warnings = warnings
        self._fd = open(path, 'wb')

    __slots__ += [ '_aacProfile', '_sampleRateIndex', '_channelConfig' ]
    def WriteChunk(self, chunk, size=None):
        length = len(chunk)
        if length < 1: return

        # header
        if chunk[0] == 0:
            if length > 3: return

            bits = c_ulonglong(BitConverterBE.ToUInt16(chunk, 1) << 48)

            # 0: MAIN - 1: LC - 2: SSR - 3: LTP
            self._aacProfile = BitHelper.Read(bits, 5) - 1
            self._sampleRateIndex = BitHelper.Read(bits, 4)
            self._channelConfig = BitHelper.Read(bits, 4)

            if not (0 <= self._aacProfile <= 3):
                raise Exception('Unsupported AAC profile')
            if self._sampleRateIndex > 12:
                raise Exception('Invalid AAC sample rate index')
            if self._channelConfig > 6:
                raise Exception('Invalid AAC channel configuration')

        # data
        else:
            dataSize = length - 1

            bits = c_ulonglong()
            BitHelper.Write(bits, 12, 0xfff)                    # sync -> always 111111111111
            BitHelper.Write(bits,  1, 0)                        # id -> 0: MPEG-4 - 1: MPEG-2
            BitHelper.Write(bits,  2, 0)                        # layer always 00
            BitHelper.Write(bits,  1, 1)                        # protection absent
            BitHelper.Write(bits,  2, self._aacProfile)
            BitHelper.Write(bits,  4, self._sampleRateIndex)
            BitHelper.Write(bits,  1, 0)                        # private bit
            BitHelper.Write(bits,  3, self._channelConfig)
            BitHelper.Write(bits,  1, 0)                        # original/copy
            BitHelper.Write(bits,  1, 0)                        # home
            # ADTS Variable header
            BitHelper.Write(bits,  1, 0)                        # copyright identification bit
            BitHelper.Write(bits,  1, 0)                        # copyright identification start
            BitHelper.Write(bits, 13, 7 + dataSize)             # Length of the frame incl. header
            BitHelper.Write(bits, 11, 0x7ff)                    # ADTS buffer fullness, 0x7ff indicates VBR
            BitHelper.Write(bits,  2, 0)                        # No raw data block in frame

            # pack() would emit 8 bytes instead of 7
            self._fd.write(('%x' % bits.value).decode('hex'))
            self._fd.write(chunk[1:])

    def Finish(self):
        self._fd.close()
