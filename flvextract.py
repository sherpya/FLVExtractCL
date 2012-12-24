#!/usr/bin/env python

from optparse import OptionParser
from flvfile import FLVFile

def parse_options():
    parser = OptionParser(usage='%prog [options] source')
    parser.add_option('-v', dest='extractVideo',help='Extract video.', action='store_true', default=False)
    parser.add_option('-a', dest='extractAudio', help='Extract audio.', action='store_true', default=False)
    parser.add_option('-t', dest='extractTimeCodes', help='Extract timecodes.', action='store_true', default=False)
    parser.add_option('-o', dest='overwrite', help='Overwrite output files without prompting.', action='store_true', default=False)
    parser.add_option('-d', dest='outputDirectory', help='''Output directory. If not specified, output files will be written
in the same directory as the source file.''')

    (options, source) = parser.parse_args()

    if len(source) != 1:
        parser.print_help()
        parser.exit()

    setattr(options, 'inputPath', source[0])
    return options

def main():
    opts = parse_options()
    flvFile = FLVFile(opts.inputPath)
    flvFile.ExtractStreams(opts.extractAudio, opts.extractVideo, opts.extractTimeCodes, opts.overwrite)

if __name__ == '__main__':
    main()
