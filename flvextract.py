#!/usr/bin/env python3
# FLV Extract
# Copyright (C) 2006-2012 J.D. Purcell (moitah@yahoo.com)
# Python port (C) 2012-2024 Gianluigi Tiesi <sherpya@gmail.com>
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
from argparse import ArgumentParser, Namespace
from pathlib import Path

from flvfile import FLVFile


class Arguments(Namespace):
    source_path: Path
    extract_video: bool
    extract_audio: bool
    extract_timecodes: bool
    overwrite: bool
    output_directory: Path | None


def main() -> None:
    print('FLV Extract CL v1.6.5 - Python version by Gianluigi Tiesi <sherpya@gmail.com>')
    print('Copyright 2006-2012 J.D. Purcell')
    print()

    parser = ArgumentParser()
    parser.add_argument('-v',
                        dest='extract_video',
                        help='Extract video.',
                        action='store_true',
                        default=False)
    parser.add_argument('-a',
                        dest='extract_audio',
                        help='Extract audio.',
                        action='store_true',
                        default=False)
    parser.add_argument('-t',
                        dest='extract_timecodes',
                        help='Extract timecodes.',
                        action='store_true',
                        default=False)
    parser.add_argument('-o',
                        dest='overwrite',
                        help='Overwrite output files without prompting.',
                        action='store_true',
                        default=False)
    parser.add_argument(
        '-d',
        dest='dir',
        type=Path,
        help='''Output directory. If not specified, output files will be written
in the same directory as the source file.''')

    parser.add_argument('source_path', type=Path, help='Source FLV File')
    args = parser.parse_args(namespace=Arguments())

    flvFile = FLVFile(args.source_path)
    if args.dir is not None:
        flvFile.output_directory = args.dir
    flvFile.extract_streams(args.extract_audio, args.extract_video, args.extract_timecodes, args.overwrite)

    print(f'True Frame Rate: {flvFile.true_framerate:g} ({flvFile.true_framerate})')
    print(f'Average Frame Rate: {flvFile.average_framerate:g} ({flvFile.average_framerate})')
    print()

    for warn in flvFile.warnings:
        print(f'Warning: {warn}')

    print('Finished')


if __name__ == '__main__':
    main()
