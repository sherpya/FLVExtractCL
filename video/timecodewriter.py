
class TimeCodeWriter(object):
    def __init__(self, path):
        self._path = path
        self._fd = open(path, 'w')
        self._fd.write('# timecode format v2\n')

    def Write(self, timeStamp):
        self._fd.write('%d\n' % timeStamp)

    def Finish(self):
        self._fd.close()
