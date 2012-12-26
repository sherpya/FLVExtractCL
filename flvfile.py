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

import os
from struct import unpack
from fractions import Fraction
from ctypes import BigEndianStructure, c_ubyte

from audio import *
from video import *

class FLVException(Exception):
    pass

class DummyWriter(object):
    def WriteChunk(self, *args):
        pass
    def Write(self, *args):
        pass
    def Finish(self, *args):
        pass
    def GetPath(self):
        return None

class TAG(object):
    AUDIO   = 8
    VIDEO   = 9
    SCRIPT  = 18

class AudioTagHeader(BigEndianStructure):
    SoundRates = [ 5512, 11025, 22050, 44100 ]
    SoundSizes = [ 8, 16 ]
    SoundTypes = [ 1 , 2 ]
    _fields_ = [
                ('SoundFormat',     c_ubyte, 4),
                ('SoundRate',       c_ubyte, 2),
                ('SoundSize',       c_ubyte, 1),
                ('SoundType',       c_ubyte, 1)
                ]

class VideoTagHeader(BigEndianStructure):
    _fields_ = [
                ('FrameType',       c_ubyte, 4),
                ('CodecID',         c_ubyte, 4)
                ]


class FLVFile(object):
    __slots__  = [ '_fd', '_inputPath', '_outputDir', '_fileOffset', '_fileLength' ]
    __slots__ += [ '_audioWriter', '_videoWriter', '_timeCodeWriter', '_warnings' ]

    def __init__(self, inputPath):
        self._inputPath = inputPath
        self._outputDir = os.path.abspath(os.path.dirname(inputPath))
        self._fileOffset = 0
        self._fileLength = os.path.getsize(self._inputPath)
        self._audioWriter = self._videoWriter = self._timeCodeWriter = None
        self._warnings = []

        self._fd = open(inputPath, 'rb')

    def SetOutputDirectory(self, outputDir):
        self._outputDir = os.path.abspath(outputDir)

    def Dispose(self):
        self._fd.close()
        self.CloseOutput(None, True)

    def Close(self):
        self.Dispose()

    def AverageFrameRate(self):
        return '%f (%s)' % (self._averageFrameRate, self._averageFrameRate)

    def TrueFrameRate(self):
        return '%f (%s)' % (self._trueFrameRate, self._trueFrameRate)

    def Warnings(self):
        return self._warnings

    __slots__ += [ '_outputPathBase', '_overwrite', '_extractAudio', '_extractVideo', '_extractTimeCodes', '_videoTimeStamps' ]
    __slots__ += [ '_averageFrameRate', '_trueFrameRate' ]
    def ExtractStreams(self, extractAudio, extractVideo, extractTimeCodes, overwrite):
        self._outputPathBase = os.path.join(self._outputDir, os.path.splitext(self._inputPath)[0])
        self._overwrite = overwrite
        self._extractAudio = extractAudio
        self._extractVideo = extractVideo
        self._extractTimeCodes = extractTimeCodes
        self._videoTimeStamps = []

        self._extractedAudio = self._extractedVideo = self._extractedTimeCodes = False

        self.Seek(0)

        if self._fd.read(4) != 'FLV\x01':
            raise FLVException('Not a flv file') 

        if not os.path.isdir(self._outputDir):
            raise FLVException('Ouput directory doesn\'t exists or not a directory')

        _flags = self.ReadUInt8()
        dataOffset = self.ReadUInt32()

        self.Seek(dataOffset)

        _prevTagSize = self.ReadUInt32()
        while self._fileOffset < self._fileLength:
            if not self.ReadTag(): break
            if (self._fileLength - self._fileOffset) < 4: break
            _prevTagSize = self.ReadUInt32()

        self._averageFrameRate = self.CalculateAverageFrameRate();
        self._trueFrameRate = self.CalculateTrueFrameRate();

        self.CloseOutput(self._averageFrameRate, False);

    def CloseOutput(self, averageFrameRate, disposing):
        if self._videoWriter is not None:
            self._videoWriter.Finish(averageFrameRate if averageFrameRate else Fraction(25, 1))
            if disposing and self._videoWriter.GetPath() is not None:
                os.unlink(self._videoWriter.GetPath())
            self._videoWriter = None

        if self._audioWriter is not None:
            self._audioWriter.Finish()
            if disposing and self._audioWriter.GetPath() is not None:
                os.unlink(self._audioWriter.GetPath())
            self._audioWriter = None

        if self._timeCodeWriter is not None:
            self._timeCodeWriter.Finish()
            if disposing and self._timeCodeWriter.GetPath() is not None:
                os.unlink(self._timeCodeWriter.GetPath())
            self._timeCodeWriter = None

    def GetAudioWriter(self, mediaInfo):
        if mediaInfo.SoundFormat in (SOUNDFORMAT.MP3, SOUNDFORMAT.MP3_8k):
            path = self._outputPathBase + '.mp3'
            if not self.CanWriteTo(path): return DummyWriter()
            return MP3Writer(path, self._warnings)
        elif mediaInfo.SoundFormat in (SOUNDFORMAT.PCM, SOUNDFORMAT.PCM_LE):
            path = self._outputPathBase + '.wav'
            if not self.CanWriteTo(path): return DummyWriter()
            sampleRate = AudioTagHeader.SoundRates[mediaInfo.SoundRate]
            bits = AudioTagHeader.SoundSizes[mediaInfo.SoundSize]
            chans = AudioTagHeader.SoundTypes[mediaInfo.SoundType]
            if mediaInfo.SoundFormat == SOUNDFORMAT.PCM:
                self._warnings.append('PCM byte order unspecified, assuming little endian')
            return WAVWriter(path, bits, chans, sampleRate)
        elif mediaInfo.SoundFormat == SOUNDFORMAT.AAC:
            path = self._outputPathBase + '.aac'
            if not self.CanWriteTo(path): return DummyWriter()
            return AACWriter(path, self._warnings)
        elif mediaInfo.SoundFormat == SOUNDFORMAT.SPEEX:
            self._warnings.append('Unsupported Sound Format Speex')
            return DummyWriter()
        else:
            self._warnings.append('Unsupported Sound Format %d' % mediaInfo.SoundFormat)
            return DummyWriter()

    def GetVideoWriter(self, mediaInfo):
        if mediaInfo.CodecID in (CODEC.H263, CODEC.SCREEN, CODEC.SCREENv2, CODEC.VP6, CODEC.VP6v2): # -> AVI
            path = self._outputPathBase + '.avi'
            if not self.CanWriteTo(path): return DummyWriter()
            return AVIWriter(path, mediaInfo.CodecID, self._warnings)
        elif mediaInfo.CodecID == CODEC.H264: # -> H264 raw
            path = self._outputPathBase + '.264'
            if not self.CanWriteTo(path): return DummyWriter()
            return RawH264Writer(path)
        else:
            self._warnings.append('Unsupported CodecID %d' % mediaInfo.CodecID)
            return DummyWriter()

    __slots__ += [ '_extractedAudio', '_extractedVideo', '_extractedTimeCodes' ]
    def ReadTag(self):
        if (self._fileLength - self._fileOffset) < 11:
            return False

        # 2bit reserved - 1bit filter - 5bit tagtype
        tagType = self.ReadUInt8()
        if tagType & 0xe0:
            raise Exception('Encrypted or invalid packet')

        dataSize = self.ReadUInt24()
        timeStamp = self.ReadUInt24()
        timeStamp |= self.ReadUInt8() << 24
        _StreamID = self.ReadUInt24()   # always 0

        # Read tag data
        if dataSize == 0:
            return True

        if (self._fileLength - self._fileOffset) < dataSize:
            return False

        mediaInfo = self.ReadBytes(1)
        audioInfo = AudioTagHeader.from_buffer_copy(mediaInfo)
        videoInfo = VideoTagHeader.from_buffer_copy(mediaInfo)
        dataSize -= 1

        chunk = self.ReadBytes(dataSize)

        if tagType == TAG.AUDIO:
            if self._audioWriter is None:
                if self._extractAudio:
                    self._audioWriter = self.GetAudioWriter(audioInfo)
                    self._extractedAudio = True
                else:
                    self._audioWriter = DummyWriter()
            self._audioWriter.WriteChunk(chunk, timeStamp)

        elif tagType == TAG.VIDEO and (videoInfo.FrameType != 5): # video info/command frame
            if self._videoWriter is None:
                if self._extractVideo:
                    self._videoWriter = self.GetVideoWriter(videoInfo)
                    self._extractedVideo = True
                else:
                    self._videoWriter = DummyWriter()

            if self._timeCodeWriter is None:
                if self._extractTimeCodes:
                    path = self._outputPathBase + '.txt'
                    if self.CanWriteTo(path):
                        self._timeCodeWriter = TimeCodeWriter(path)
                        self._extractedTimeCodes = True
                    else:
                        self._timeCodeWriter = DummyWriter()
                else:
                    self._timeCodeWriter = DummyWriter()

            self._videoTimeStamps.append(timeStamp)
            self._videoWriter.WriteChunk(chunk, timeStamp, videoInfo.FrameType)
            self._timeCodeWriter.Write(timeStamp)

        elif tagType == TAG.SCRIPT:
            pass
        else:
            raise Exception('Unknown tag %d' % tagType)

        return True

    def CanWriteTo(self, path):
        return not os.path.exists(path) or self._overwrite

    def CalculateAverageFrameRate(self):
        frameCount = len(self._videoTimeStamps)
        if frameCount > 1:
            n = (frameCount - 1) * 1000 # TODO: cast uint32_t
            d = self._videoTimeStamps[frameCount - 1] - self._videoTimeStamps[0]
            return Fraction(n, d)
        return None

    def CalculateTrueFrameRate(self):
        deltaCount = {}

        for i in xrange(1, len(self._videoTimeStamps)):
            deltaS = self._videoTimeStamps[i] - self._videoTimeStamps[i - 1]

            if deltaS <= 0: continue
            delta = deltaS

            if delta in deltaCount:
                deltaCount[delta] += 1
            else:
                deltaCount[delta] = 1

        threshold = len(self._videoTimeStamps) / 10
        minDelta = None # let's say None is maxint

        # Find the smallest delta that made up at least 10% of the frames (grouping in delta+1
        # because of rounding, e.g. a NTSC video will have deltas of 33 and 34 ms)
        for (delta, count) in deltaCount.items():
            if (delta + 1) in deltaCount:
                count += deltaCount[delta + 1]
            if (count >= threshold) and ((minDelta is None) or (delta < minDelta)):
                minDelta = delta

        # Calculate the frame rate based on the smallest delta, and delta+1 if present
        if minDelta is not None:
            count = deltaCount[minDelta];
            totalTime = minDelta * count
            totalFrames = count

            if (minDelta + 1) in deltaCount:
                count = deltaCount[minDelta + 1]
                totalTime += (minDelta + 1) * count
                totalFrames += count

            if totalTime != 0:
                return Fraction(totalFrames * 1000, totalTime)

        return None

    def Seek(self, offset):
        self._fd.seek(offset)
        self._fileOffset = offset

    def ReadUInt8(self):
        return ord(self.ReadBytes(1))

    def ReadUInt24(self):
        data = '\x00' + self.ReadBytes(3)
        return unpack('>I', data)[0]

    def ReadUInt32(self):
        return unpack('>I', self.ReadBytes(4))[0]

    def ReadBytes(self, size):
        self._fileOffset += size
        return self._fd.read(size)
