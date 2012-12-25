#!/usr/bin/env python

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
    print 'Copyright 2006-2012 J.D. Purcell'
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
