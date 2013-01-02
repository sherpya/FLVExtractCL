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

from struct import pack
from ctypes import c_int

from general import BitHelper, OggCRC
from audio import AudioWriter

class OggPacket(object):
    __slots__ = [ 'GranulePosition', 'Data' ]

    def __init__(self, gp=0, data=None):
        self.GranulePosition = gp
        self.Data = data

class SpeexWriter(AudioWriter):
    __slots__  = [ '_fd', '_path', 'serialNumber' ]

    _vendorString = 'FLV Extract'
    _sampleRate = 16000
    _msPerFrame = 20
    _samplesPerFrame = _sampleRate / (1000 / _msPerFrame)
    _targetPageDataSize = 4096

    __slots__ += [ '_packetList', '_packetListDataSize' ]
    __slots__ += ['_pageBuff', '_pageBuffOffset', '_pageSequenceNumber', '_granulePosition' ]
    def __init__(self, path, serialNumber):
        self._path = path
        self._serialNumber = serialNumber

        self._fd = open(path, 'wb')
        self._fd.seek((28 + 80) + (28 + 8 + len(SpeexWriter._vendorString))) # Speex header + Vorbis comment
        self._packetList = []
        self._packetListDataSize = 0

        # Header + max segment table + target data size + extra segment
        self._pageBuff = bytearray(27 + 255 + SpeexWriter._targetPageDataSize + 254)

        self._pageBuffOffset = 0
        self._pageSequenceNumber = 2    # First audio packet
        self._granulePosition = 0

    _subModeSizes = [ 0, 43, 119, 160, 220, 300, 364, 492, 79 ]
    _wideBandSizes = [ 0, 36, 112, 192, 352 ]
    _inBandSignalSizes = [ 1, 1, 4, 4, 4, 4, 4, 4, 8, 8, 16, 16, 32, 32, 64, 64 ]

    def WriteChunk(self, chunk, timeStamp=None):
        chunk = bytearray(chunk)
        frameStart = -1
        frameEnd = 0
        offset = c_int()
        length = len(chunk) * 8

        while (length - offset.value) >= 5:
            x = BitHelper.ReadB(chunk, offset, 1)
            if x != 0:
                # wideband frame
                x = BitHelper.ReadB(chunk, offset, 3)
                if not 1 <= x <= 4: raise Exception
                offset.value += SpeexWriter._wideBandSizes[x] - 4
            else:
                x = BitHelper.ReadB(chunk, offset, 4)
                if 1 <= x <= 8:
                    # narrowband frame
                    if frameStart != -1:
                        self.WriteFramePacket(chunk, frameStart, frameEnd)
                    frameStart = frameEnd
                    offset.value += SpeexWriter._subModeSizes[x] - 5
                elif x == 15:
                    # terminator
                    break
                elif x == 14:
                    # in-band signal
                    if (length - offset.value) < 4: raise Exception
                    x = BitHelper.ReadB(chunk, offset, 4)
                    offset.value += SpeexWriter._inBandSignalSizes[x]
                elif x == 13:
                    # custom in-band signal
                    if (length - offset.value) < 5: raise Exception
                    x = BitHelper.ReadB(chunk, offset, 5)
                    offset.value += x * 8
                else:
                    raise Exception

            frameEnd = offset.value

        if offset.value > length: raise Exception

        if frameStart != -1:
            self.WriteFramePacket(chunk, frameStart, frameEnd)

    def Finish(self):
        self.WritePage()
        self.FlushPage(True)
        self._fd.seek(0)
        self._pageSequenceNumber = 0
        self._granulePosition = 0
        self.WriteSpeexHeaderPacket()
        self.WriteVorbisCommentPacket()
        self.FlushPage(False)
        self._fd.close()

    def WriteFramePacket(self, data, startBit, endBit):
        lengthBits = endBit - startBit
        frame = BitHelper.CopyBlock(data, startBit, lengthBits)

        if (lengthBits % 8) != 0:
            frame[-1] |= 0xff >> ((lengthBits % 8) + 1) # padding

        self.AddPacket(frame, SpeexWriter._samplesPerFrame, True)

    def WriteSpeexHeaderPacket(self):
        data = bytearray(80)

        pos = 0         ; data[pos:pos + 8] = 'Speex   '                                # speex_string
        pos = 8         ; data[pos:pos + 7] = 'unknown'                                 # speex_version
    
        data[28] = 1    # speex_version_id
        data[32] = 80   # header_size

        pos = 36        ; data[pos:pos + 4] = pack('<I', SpeexWriter._sampleRate)       # rate

        data[40] = 1    # mode (e.g. narrowband, wideband)
        data[44] = 4    # mode_bitstream_version
        data[48] = 1    # nb_channels

        pos = 52        ; data[pos:pos + 4] = pack('<i', -1)                            # bitrate
        pos = 56        ; data[pos:pos + 4] = pack('<I', SpeexWriter._samplesPerFrame)  # frame_size

        data[60] = 0    # vbr
        data[64] = 1    # frames_per_packet

        self.AddPacket(data, 0, False)

    def WriteVorbisCommentPacket(self):
        length = len(SpeexWriter._vendorString)
        data = bytearray(8 + length)
        data[0] = length

        pos = 4         ; data[pos:pos + length] = SpeexWriter._vendorString

        self.AddPacket(data, 0, False)

    def AddPacket(self, data, sampleLength, delayWrite):
        length = len(data)
        if length >= 255:
            raise Exception('Packet exceeds maximum size')

        self._granulePosition += sampleLength

        self._packetList.append(OggPacket(self._granulePosition, data))
        self._packetListDataSize += length

        if not delayWrite or (self._packetListDataSize >= self._targetPageDataSize) or (len(self._packetList) == 255):
            self.WritePage()

    def WritePage(self):
        numPackets = len(self._packetList)
        if numPackets == 0: return
        self.FlushPage(False)
        self.WriteToPage('OggS', 0, 4)

        self.WriteToPageUInt8(0)                                                    # Stream structure version
        self.WriteToPageUInt8(0x02 if (self._pageSequenceNumber == 0) else 0)       # Page flags
        self.WriteToPageUInt64(self._packetList[-1].GranulePosition)                # Position in samples
        self.WriteToPageUInt32(self._serialNumber)                                  # Stream serial number
        self.WriteToPageUInt32(self._pageSequenceNumber)                            # Page sequence number
        self.WriteToPageUInt32(0)                                                   # Checksum
        self.WriteToPageUInt8(numPackets)                                           # Page segment count

        for packet in self._packetList:
            self.WriteToPageUInt8(len(packet.Data))

        for packet in self._packetList:
            self.WriteToPage(packet.Data, 0, len(packet.Data))

        self._packetList = []
        self._packetListDataSize = 0
        self._pageSequenceNumber += 1

    def FlushPage(self, isLastPage):
        if self._pageBuffOffset == 0: return

        if isLastPage:
            self._pageBuff[5] |= 0x04

        crc = OggCRC.Calculate(self._pageBuff, 0, self._pageBuffOffset)
        pos = 22        ; self._pageBuff[pos:pos + 4] = pack('<I', crc)

        self._fd.write(self._pageBuff[:self._pageBuffOffset])
        self._pageBuffOffset = 0

    def WriteToPage(self, data, offset, length):
        self._pageBuff[self._pageBuffOffset:self._pageBuffOffset + length] = data[offset:offset + length]
        self._pageBuffOffset += length

    def WriteToPageUInt8(self, value):
        self.WriteToPage(chr(value), 0, 1)

    def WriteToPageUInt32(self, value):
        self.WriteToPage(pack('<I', value), 0, 4)

    def WriteToPageUInt64(self, value):
        self.WriteToPage(pack('<Q', value), 0, 8)
