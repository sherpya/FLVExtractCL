__all__ = [ 'CODEC', 'TimeCodeWriter', 'AVIWriter', 'RawH264Writer' ]

class CODEC(object):
    H263    = 2
    VP6     = 4
    VP6v2   = 5
    H264    = 7

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
