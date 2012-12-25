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
    print 'FLV Extract CL v1.6.2 - Python version by Gianluigi Tiesi <sherpya@netfarm.it>'
    print 'Copyright 2006-2011 J.D. Purcell'
    print 'http://www.moitah.net/'
    print

    opts = parse_options()
    flvFile = FLVFile(opts.inputPath)
    if opts.outputDirectory is not None:
        flvFile.SetOutputDirectory(opts.outputDirectory)
    flvFile.ExtractStreams(opts.extractAudio, opts.extractVideo, opts.extractTimeCodes, opts.overwrite)

    print 'True Frame Rate:', flvFile.TrueFrameRate()
    print 'Average Frame Rate:', flvFile.AverageFrameRate()
    print

    for warn in flvFile.Warnings():
        print 'Warning:', warn

    print 'Finished'

if __name__ == '__main__':
    main()
