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

__all__ = [ 'CODEC', 'TimeCodeWriter', 'AVIWriter', 'RawH264Writer' ]

class CODEC(object):
    H263        = 2
    SCREEN      = 3
    VP6         = 4
    VP6v2       = 5
    SCREENv2    = 6
    H264        = 7

class VideoWriter(object):
    def WriteChunk(self, chunk, timeStamp, frameType):
        raise Exception('interface')
    def Finish(self, averageFrameRate):
        raise Exception('interface')
    def GetPath(self):
        return self._path

from timecodewriter import TimeCodeWriter
from aviwriter import AVIWriter
from rawh264writer import RawH264Writer
