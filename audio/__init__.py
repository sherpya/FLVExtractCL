__all__ = [ 'MP3Writer' ]
class AudioWriter(object):
    def WriteChunk(self, chunk, size):
        raise Exception('interface')
    def Finish(self):
        raise Exception('interface')
    def GetPath(self):
        return self._path

from mp3writer import MP3Writer
