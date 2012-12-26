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
from audio import AudioWriter

class WAVWriter(AudioWriter):
    __slots__  = [ '_fd', '_path', 'blockAlign' ]
    __slots__ += [ '_bitsPerSample', '_channelCount', '_sampleRate', '_blockAlign', '_canSeek' ]
    __slots__ += [ '_sampleLen', '_finalSampleLen', '_wroteHeaders' ]

    def __init__(self, path, bitsPerSample, channelCount, sampleRate):
        self.blockAlign = (bitsPerSample / 8) * channelCount

        # WAVTools.WAVWriter
        self._bitsPerSample = bitsPerSample
        self._channelCount = channelCount
        self._sampleRate = sampleRate
        self._blockAlign = self._channelCount * ((self._bitsPerSample + 7) / 8)

        self._sampleLen = self._finalSampleLen = 0
        self._wroteHeaders = False

        self._path = path
        self._fd = open(path, 'wb')
        try:
            self._fd.tell()
        except IOError:
            self._canSeek = False
        else:
            self._canSeek = True

    def WriteChunk(self, chunk, timeStamp=None):
        self.Write(chunk, len(chunk) / self.blockAlign)

    def Finish(self):
        self.Close()

    def WriteFourCC(self, fourCC):
        if len(fourCC) != 4:
            raise Exception('Invalid fourCC length')
        self._fd.write(fourCC)

    def WriteHeaders(self):
        dataChunkSize = self.GetDataChunkSize(self._finalSampleLen)

        self.WriteFourCC('RIFF')
        self._fd.write(pack('>I', dataChunkSize + (dataChunkSize & 1) + 36))
        self.WriteFourCC('WAVE')
        self.WriteFourCC('fmt ')
        self._fd.write(pack('<I', 16))
        self._fd.write(pack('<H', 1))
        self._fd.write(pack('<H', self._channelCount))
        self._fd.write(pack('<I', self._sampleRate))
        self._fd.write(pack('<I', self._sampleRate * self._blockAlign))
        self._fd.write(pack('<H', self._blockAlign))
        self._fd.write(pack('<H', self._bitsPerSample))
        self.WriteFourCC('data')
        self._fd.write(pack('<I', dataChunkSize))

    def GetDataChunkSize(self, sampleCount):
        maxFileSize = 0x7ffffffe

        dataSize = sampleCount * self._blockAlign
        if (dataSize + 44) > maxFileSize:
            dataSize = ((maxFileSize - 44) / self._blockAlign) * self._blockAlign
        return dataSize

    def Close(self):
        if ((self._sampleLen * self._blockAlign) & 1) == 1:
            self._fd.write('\x00')

        if self._sampleLen != self._finalSampleLen:
            if not self._canSeek:
                raise Exception('Samples written differs from the expected sample count')

            dataChunkSize = self.GetDataChunkSize(self._sampleLen)
            self._fd.seek(4)
            self._fd.write(pack('<I', dataChunkSize + (dataChunkSize & 1) + 36))
            self._fd.seek(40)
            self._fd.write(pack('<I', dataChunkSize))

        self._fd.close()

    def Write(self, buff, sampleCount):
        if sampleCount <= 0: return

        if not self._wroteHeaders:
            self.WriteHeaders()
            self._wroteHeaders = True

        self._fd.write(buff) # length should be sampleCount * self._blockAlign
        self._sampleLen += sampleCount
