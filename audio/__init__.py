__all__ = [ 'SOUNDFORMAT', 'MP3Writer' ]

class SOUNDFORMAT(object):
    PCM     = 0
    ADPCM   = 1
    MP3     = 2
    PCM_LE  = 3
    AAC     = 10
    SPEEX   = 11
    MP3_8k  = 14

class AudioWriter(object):
    def WriteChunk(self, chunk, size):
        raise Exception('interface')
    def Finish(self):
        raise Exception('interface')
    def GetPath(self):
        return self._path

from mp3writer import MP3Writer
