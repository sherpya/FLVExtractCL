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

from ctypes import BigEndianStructure, c_uint, c_ulonglong
from os import SEEK_CUR

from general import BitHelper, BitConverterBE, BitConverterLE
from video import VideoTagHeader, VideoWriter

class H263FrameHeader(BigEndianStructure):
    _fields_ = [
                  ('header',                c_uint, 17),
                  ('picformat',             c_uint, 5),
                  ('ts',                    c_uint, 8),
                  ('format',                c_uint, 3)
                ]

class FLASHSVFrameHeader(BigEndianStructure):
    _fields_ = [
                  ('blockWidth',            c_uint, 4),
                  ('imageWidth',            c_uint, 12),
                  ('blockHeight',           c_uint, 4),
                  ('imageHeight',           c_uint, 12)
                ]

class VP6FrameHeader(BigEndianStructure):
    _fields_ = [
                  ('deltaFrameFlag',        c_uint, 1),
                  ('quant',                 c_uint, 6),
                  ('separatedCoeffFlag',    c_uint, 1),
                  ('subVersion',            c_uint, 5),
                  ('filterHeader',          c_uint, 2),
                  ('interlacedFlag',        c_uint, 1)
                  ]

class VideoFormat(object):
    CIF     = (352, 288)
    QCIF    = (176, 144)
    SQCIF   = (128, 96)
    QVGA    = (320, 240)
    QQVGA   = (160, 120)

class AVIWriter(VideoWriter):
    __slots__  = [ '_codecID', '_warnings', '_isAlphaWriter', '_alphaWriter' ]
    __slots__ += [ '_width', '_height', '_frameCount' ]
    __slots__ += [ '_index', '_moviDataSize' ]

    # Chunk:          Off:  Len:
    #
    # RIFF AVI          0    12
    #   LIST hdrl      12    12
    #     avih         24    64
    #     LIST strl    88    12
    #       strh      100    64
    #       strf      164    48
    #   LIST movi     212    12
    #     (frames)    224   ???
    #   idx1          ???   ???

    def CodecFourCC(self):
        if self._codecID == VideoTagHeader.H263:
            return 'FLV1'
        elif self._codecID in (VideoTagHeader.VP6, VideoTagHeader.VP6v2):
            return 'VP6F'
        elif self._codecID in (VideoTagHeader.SCREEN, VideoTagHeader.SCREENv2): # FIXME: v2?
            return 'FSV1'

    def __init__(self, path, codecID, warnings, isAlphaWriter=False):
        super(AVIWriter, self).__init__(path)
        self._codecID = codecID
        self._isAlphaWriter = isAlphaWriter
        self._alphaWriter = None
        self._warnings = warnings

        self._width = self._height = self._frameCount = 0
        self._index = []
        self._moviDataSize = 0

        if codecID not in (VideoTagHeader.H263, VideoTagHeader.SCREEN, VideoTagHeader.SCREENv2, VideoTagHeader.VP6, VideoTagHeader.VP6v2):
            raise Exception('Unsupported video codec')

        if (codecID == VideoTagHeader.VP6v2) and not isAlphaWriter:
            self._alphaWriter = AVIWriter(path[:-4] + 'alpha.avi', codecID, warnings, True)

        self.WriteFourCC('RIFF')
        self.Write(BitConverterLE.FromUInt32(0)) # chunk size
        self.WriteFourCC('AVI ')

        self.WriteFourCC('LIST')
        self.Write(BitConverterLE.FromUInt32(192))
        self.WriteFourCC('hdrl')

        self.WriteFourCC('avih')
        self.Write(BitConverterLE.FromUInt32(56))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0x10))
        self.Write(BitConverterLE.FromUInt32(0)) # frame count
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(1))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0)) # width
        self.Write(BitConverterLE.FromUInt32(0)) # height
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0))

        self.WriteFourCC('LIST')
        self.Write(BitConverterLE.FromUInt32(116))
        self.WriteFourCC('strl')

        self.WriteFourCC('strh')
        self.Write(BitConverterLE.FromUInt32(56))
        self.WriteFourCC('vids')
        self.WriteFourCC(self.CodecFourCC())
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0)) # frame rate denominator
        self.Write(BitConverterLE.FromUInt32(0)) # frame rate numerator
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0)) # frame count
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromInt32(-1))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt16(0))
        self.Write(BitConverterLE.FromUInt16(0))
        self.Write(BitConverterLE.FromUInt16(0)) # width
        self.Write(BitConverterLE.FromUInt16(0)) # height

        self.WriteFourCC('strf')
        self.Write(BitConverterLE.FromUInt32(40))
        self.Write(BitConverterLE.FromUInt32(40))
        self.Write(BitConverterLE.FromUInt32(0)) # width
        self.Write(BitConverterLE.FromUInt32(0)) # height
        self.Write(BitConverterLE.FromUInt16(1))
        self.Write(BitConverterLE.FromUInt16(24))
    
        self.WriteFourCC(self.CodecFourCC())
        self.Write(BitConverterLE.FromUInt32(0)) # biSizeImage
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0))
    
        self.WriteFourCC('LIST')
        self.Write(BitConverterLE.FromUInt32(0)) # chunk size
        self.WriteFourCC('movi')

    def WriteChunk(self, chunk, timeStamp, frameType):
        offset = 0
        length = len(chunk)

        if self._codecID == VideoTagHeader.VP6:
            offset = 1
            length -= 1
        elif self._codecID == VideoTagHeader.VP6v2:
            offset = 4
            if length >= 4:
                alphaOffset = BitConverterBE.ToUInt32(chunk, 0) & 0xffffff
                if not self._isAlphaWriter:
                    length = alphaOffset
                else:
                    offset += alphaOffset
                    length -= offset
            else:
                length = 0

        length = max(length, 0)
        length = min(length, len(chunk) - offset)

        self._index.append(0x10 if (frameType == 1) else 0)
        self._index.append(self._moviDataSize + 4)
        self._index.append(length)

        if (self._width == 0) and (self._height == 0):
            self.GetFrameSize(chunk)

        self.WriteFourCC('00dc')
        self.Write(BitConverterLE.FromInt32(length))
        self.Write(chunk, offset, length)

        if (length % 2) != 0:
            self.Write('\x00')
            length += 1

        self._moviDataSize += length + 8
        self._frameCount += 1

        if self._alphaWriter is not None:
            self._alphaWriter.WriteChunk(chunk, timeStamp, frameType)

    def GetFrameSize(self, chunk):
        if self._codecID == VideoTagHeader.H263:
            # Reference: flv_h263_decode_picture_header from libavcodec's h263.c
            if len(chunk) < 10: return

            x = c_ulonglong(BitConverterBE.ToUInt64(chunk, 2))

            if BitHelper.Read(x, 1) != 1:
                return

            BitHelper.Read(x, 5)
            BitHelper.Read(x, 8)

            _format = BitHelper.Read(x, 3)

            if _format == 0:
                self._width = BitHelper.Read(x, 8)
                self._height = BitHelper.Read(x, 8)
            elif _format == 1:
                self._width = BitHelper.Read(x, 16)
                self._height = BitHelper.Read(x, 16)
            elif _format == 2:
                self._width, self._height = VideoFormat.CIF
            elif _format == 3:
                self._width, self._height = VideoFormat.QCIF
            elif _format == 4:
                self._width, self._height = VideoFormat.SQCIF
            elif _format == 5:
                self._width, self._height = VideoFormat.QVGA
            elif _format == 6:
                self._width, self._height = VideoFormat.QQVGA

            #hdr = H263FrameHeader.from_buffer_copy(chunk)

            #if hdr.header != 1: # h263 header
            #    return

            #if hdr.picformat not in (0, 1): # picture format 0: h263 escape codes 1: 11-bit escape codes 
            #    return

        elif self._codecID in (VideoTagHeader.SCREEN, VideoTagHeader.SCREENv2): # FIXME: v2?
            # Reference: flashsv_decode_frame from libavcodec's flashsv.c
            # notice: libavcodec checks if width/height changes
            if len(chunk) < 4: return

            hdr = FLASHSVFrameHeader.from_buffer_copy(chunk)
            self._width = hdr.imageWidth
            self._height = hdr.imageHeight

        elif self._codecID in (VideoTagHeader.VP6, VideoTagHeader.VP6v2):
            # Reference: vp6_parse_header from libavcodec's vp6.c
            skip = 1 if (self._codecID == VideoTagHeader.VP6) else 4
            if len(chunk) < (skip + 8): return

            hdr = VP6FrameHeader.from_buffer_copy(chunk, skip)

            if hdr.deltaFrameFlag != 0:
                return

            if hdr.separatedCoeffFlag or hdr.filterHeader: # skip 16 bit
                xy = chunk[skip + 2:skip + 4]
            else:
                xy = chunk[skip:skip + 2]

            self._height = xy[0] * 16
            self._width = xy[1] * 16

            # chunk[0] contains the width and height (4 bits each, respectively) that should
            # be cropped off during playback, which will be non-zero if the encoder padded
            # the frames to a macroblock boundary.  But if you use this adjusted size in the
            # AVI header, DirectShow seems to ignore it, and it can cause stride or chroma
            # alignment problems with VFW if the width/height aren't multiples of 4.
            if not self._isAlphaWriter:
                cropX = chunk[0] >> 4
                cropY = chunk[0] & 0xf
                if (cropX != 0) or (cropY != 0):
                    self._warnings.append('Suggested cropping: %d pixels from right, %d pixels from bottom' % (cropX, cropY))

    __slots__ += [ '_indexChunkSize' ]
    def WriteIndexChunk(self):
        indexDataSize = self._frameCount * 16

        self.WriteFourCC('idx1')
        self.Write(BitConverterLE.FromUInt32(indexDataSize))

        for i in xrange(self._frameCount):
            self.WriteFourCC('00dc')
            self.Write(BitConverterLE.FromUInt32(self._index[(i * 3) + 0]))
            self.Write(BitConverterLE.FromUInt32(self._index[(i * 3) + 1]))
            self.Write(BitConverterLE.FromUInt32(self._index[(i * 3) + 2]))

        self._indexChunkSize = indexDataSize + 8

    def Finish(self, averageFrameRate):
        self.WriteIndexChunk()

        self.Seek(4)
        self.Write(BitConverterLE.FromUInt32(224 + self._moviDataSize + self._indexChunkSize - 8))

        self.Seek(24 + 8)
        self.Write(BitConverterLE.FromUInt32(0))
        self.Seek(12, SEEK_CUR)
        self.Write(BitConverterLE.FromUInt32(self._frameCount))
        self.Seek(12, SEEK_CUR)
        self.Write(BitConverterLE.FromUInt32(self._width))
        self.Write(BitConverterLE.FromUInt32(self._height))

        self.Seek(100 + 28)
        self.Write(BitConverterLE.FromUInt32(averageFrameRate.denominator))
        self.Write(BitConverterLE.FromUInt32(averageFrameRate.numerator))
        self.Seek(4, SEEK_CUR)
        self.Write(BitConverterLE.FromUInt32(self._frameCount))
        self.Seek(16, SEEK_CUR)
        self.Write(BitConverterLE.FromUInt16(self._width))
        self.Write(BitConverterLE.FromUInt16(self._height))

        self.Seek(164 + 12)
        self.Write(BitConverterLE.FromUInt32(self._width))
        self.Write(BitConverterLE.FromUInt32(self._height))
        self.Seek(8, SEEK_CUR)
        self.Write(BitConverterLE.FromUInt32(self._width * self._height * 6))

        self.Seek(212 + 4)
        self.Write(BitConverterLE.FromUInt32(self._moviDataSize + 4))

        self.Close()

        if self._alphaWriter is not None:
            self._alphaWriter.Finish(averageFrameRate)
            self._alphaWriter = None
