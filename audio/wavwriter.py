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

from general import BitConverterLE
from audio import AudioWriter

class WAVWriter(AudioWriter):
    __slots__  = [ 'blockAlign', '_bitsPerSample', '_channelCount', '_sampleRate', '_blockAlign' ]
    __slots__ += [ '_sampleLen', '_finalSampleLen', '_wroteHeaders' ]

    def __init__(self, path, bitsPerSample, channelCount, sampleRate):
        super(WAVWriter, self).__init__(path)

        self.blockAlign = (bitsPerSample / 8) * channelCount

        # WAVTools.WAVWriter
        self._bitsPerSample = bitsPerSample
        self._channelCount = channelCount
        self._sampleRate = sampleRate
        self._blockAlign = self._channelCount * ((self._bitsPerSample + 7) / 8)

        self._sampleLen = self._finalSampleLen = 0
        self._wroteHeaders = False

    def WriteChunk(self, chunk, timeStamp=None):
        self.WriteSamples(chunk, len(chunk) / self.blockAlign)

    def WriteHeaders(self):
        dataChunkSize = self.GetDataChunkSize(self._finalSampleLen)

        self.WriteFourCC('RIFF')
        self.Write(BitConverterLE.FromUInt32(dataChunkSize + (dataChunkSize & 1) + 36))
        self.WriteFourCC('WAVE')
        self.WriteFourCC('fmt ')
        self.Write(BitConverterLE.FromUInt32(16))
        self.Write(BitConverterLE.FromUInt16(1))
        self.Write(BitConverterLE.FromUInt16(self._channelCount))
        self.Write(BitConverterLE.FromUInt32(self._sampleRate))
        self.Write(BitConverterLE.FromUInt32(self._sampleRate * self._blockAlign))
        self.Write(BitConverterLE.FromUInt16(self._blockAlign))
        self.Write(BitConverterLE.FromUInt16(self._bitsPerSample))
        self.WriteFourCC('data')
        self.Write(BitConverterLE.FromUInt32(dataChunkSize))

    def GetDataChunkSize(self, sampleCount):
        maxFileSize = 0x7ffffffe

        dataSize = sampleCount * self._blockAlign
        if (dataSize + 44) > maxFileSize:
            dataSize = ((maxFileSize - 44) / self._blockAlign) * self._blockAlign
        return dataSize

    def Finish(self):
        if ((self._sampleLen * self._blockAlign) & 1) == 1:
            self.Write('\x00')

        if self._sampleLen != self._finalSampleLen:
            dataChunkSize = self.GetDataChunkSize(self._sampleLen)
            self.Seek(4)
            self.Write(BitConverterLE.FromUInt32(dataChunkSize + (dataChunkSize & 1) + 36))
            self.Seek(40)
            self.Write(BitConverterLE.FromUInt32(dataChunkSize))

        self.Close()

    def WriteSamples(self, buff, sampleCount):
        if sampleCount <= 0: return

        if not self._wroteHeaders:
            self.WriteHeaders()
            self._wroteHeaders = True

        self.Write(buff, 0, sampleCount * self._blockAlign)
        self._sampleLen += sampleCount
