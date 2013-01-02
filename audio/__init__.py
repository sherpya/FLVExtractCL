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

__all__ = [ 'AudioTagHeader', 'MP3Writer', 'AACWriter', 'WAVWriter', 'SpeexWriter' ]

from general import Writer
from ctypes import BigEndianStructure, c_ubyte

class AudioTagHeader(BigEndianStructure):
    SoundRates = [ 5512, 11025, 22050, 44100 ]
    SoundSizes = [ 8, 16 ]
    SoundTypes = [ 1 , 2 ]
    PCM, ADPCM, MP3, PCM_LE, NELLY_16k, NELLY_8k, NELLYMOSER, ALAW, ULAW, _, AAC, SPEEX, _, _, MP3_8k, _ = range(16)
    _fields_ = [
                ('SoundFormat',     c_ubyte, 4),
                ('SoundRate',       c_ubyte, 2),
                ('SoundSize',       c_ubyte, 1),
                ('SoundType',       c_ubyte, 1)
                ]

class AudioWriter(Writer):
    def WriteChunk(self, chunk, size):
        raise Exception('interface')
    def Finish(self):
        raise Exception('interface')


from mp3writer import MP3Writer
from aacwriter import AACWriter
from wavwriter import WAVWriter
from speexwriter import SpeexWriter
