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
from abc import ABC
from enum import IntEnum
from fractions import Fraction
from pathlib import Path
from typing import List, BinaryIO, TextIO, Dict

from audio import MP3Writer, WAVWriter, AACWriter, SpeexWriter
from interfaces import IDisposable, IAudioWriter, IVideoWriter, VideoCodecID, FLVException
from video import AVIWriter, RawH264Writer


class DummyWriter:
    def write_chunk(self, data: bytes, timestamp: int | None = None, frametype: int | None = None) -> None: ...

    def write(self, timestamp: int) -> None: ...

    def finish(self, average_framerate: Fraction | None = None) -> None: ...

    def unlink(self) -> None: ...


class Tag(IntEnum):
    AUDIO = 8
    VIDEO = 9
    SCRIPT = 18


class AudioFormat(IntEnum):
    PCM = 0
    ADPCM = 1
    MP3 = 2
    PCM_LE = 3
    NELLY_16k = 4
    NELLY_8k = 5
    NELLYMOSER = 6
    ALAW = 7
    ULAW = 8
    AAC = 10
    SPEEX = 11
    MP3_8k = 14


SampleRates = [5512, 11025, 22050, 44100]


class TimeCodeWriter:
    _path: Path | None = None
    _fd: TextIO | None = None

    def __init__(self, path: Path | None):
        if path is not None:
            self._path = path
            self._fd = self._path.open('w')
            self._fd.write('# timecode format v2\n')

    def write(self, timestamp: int) -> None:
        if self._fd is not None:
            self._fd.write(f'{timestamp}\n')

    def finish(self) -> None:
        if self._fd is not None:
            self._fd.close()
            self._fd = None
            self._path = None

    def unlink(self) -> None:
        if self._path is not None:
            self._path.unlink()


class FLVFile(IDisposable, ABC):
    _input_path: Path
    output_directory: Path

    _overwrite: bool = False
    _fd: BinaryIO | None = None
    _file_offset: int = 0
    _file_length: int = 0

    _audio_writer: IAudioWriter | DummyWriter | None = None
    _video_writer: IVideoWriter | DummyWriter | None = None
    _timecode_writer: TimeCodeWriter | DummyWriter | None = None

    _video_timestamps: List[int]

    _extract_audio: bool = False
    _extract_video: bool = False
    _extract_timecodes: bool = False

    extracted_audio: bool = False
    extracted_video: bool = False
    extracted_timecodes: bool = False

    average_framerate: Fraction | None
    true_framerate: Fraction | None

    warnings: List[str]

    def __init__(self, input_path: Path):
        self._input_path = input_path
        self.output_directory = self._input_path.parent
        self.warnings = []
        self._fd = self._input_path.open('rb')
        self._file_offset = 0
        self._file_length = self._input_path.stat().st_size

    def dispose(self) -> None:
        assert self._fd is not None
        self._fd.close()
        self._fd = None
        self.close_output(None, True)

    def close(self) -> None:
        self.dispose()

    def extract_streams(self, extract_audio: bool, extract_video: bool, extract_timecodes: bool,
                        overwrite: bool) -> None:
        self._overwrite = overwrite
        self._extract_audio = extract_audio
        self._extract_video = extract_video
        self._extract_timecodes = extract_timecodes
        self._video_timestamps = []

        self.seek(0)

        assert self._fd is not None
        if self._file_length < 4 or self._fd.read(4) != b'FLV\x01':
            if self._file_length >= 8 and self._fd.read(4) == b'ftyp':
                raise FLVException('This is a MP4 file. YAMB or MP4Box can be used to extract streams.')
            else:
                raise FLVException('Not a flv file')

        # TODO: check if the input uses an output file extension
        # Please change the extension of this FLV file.

        if not self.output_directory.is_dir():
            raise FLVException("Output directory doesn't exists or not a directory")

        _flags = self.read_uint8()
        data_offset = self.read_uint32()

        self.seek(data_offset)

        _prev_tag_size = self.read_uint32()
        while self._file_offset < self._file_length:
            if not self.read_tag():
                break
            if (self._file_length - self._file_offset) < 4:
                break
            _prev_tag_size = self.read_uint32()

        self.average_framerate = self.calculate_average_framerate()
        self.true_framerate = self.calculate_true_framerate()

        self.close_output(self.average_framerate, False)

    def close_output(self, average_framerate: Fraction | None, disposing: bool) -> None:
        if self._video_writer is not None:
            self._video_writer.finish(average_framerate if average_framerate is not None else Fraction(25, 1))
            if disposing:
                self._video_writer.unlink()
            self._video_writer = None

        if self._audio_writer is not None:
            self._audio_writer.finish()
            if disposing:
                self._audio_writer.unlink()
            self._audio_writer = None

        if self._timecode_writer is not None:
            self._timecode_writer.finish()
            if disposing:
                self._timecode_writer.unlink()
            self._timecode_writer = None

    def read_tag(self) -> bool:
        if (self._file_length - self._file_offset) < 11:
            return False

        # 2bit reserved - 1bit filter - 5bit tagtype
        tag_type = self.read_uint8()
        if tag_type & 0xe0:
            raise FLVException('Encrypted or invalid packet')

        data_size = self.read_uint24()
        timestamp = self.read_uint24()
        timestamp |= self.read_uint8() << 24
        _stream_id = self.read_uint24()  # always 0

        # Read tag data
        if data_size == 0:
            return True

        if (self._file_length - self._file_offset) < data_size:
            return False

        mediainfo = self.read_uint8()
        data_size -= 1

        data = self.read_bytes(data_size)

        if tag_type == Tag.AUDIO:
            if self._audio_writer is None:
                self._audio_writer = self.get_audio_writer(mediainfo) if self._extract_audio else DummyWriter()
                self.extracted_audio = not isinstance(self._audio_writer, DummyWriter)
            self._audio_writer.write_chunk(data, timestamp)
        elif tag_type == Tag.VIDEO and ((mediainfo >> 4) != 5):
            if self._video_writer is None:
                self._video_writer = self.get_video_writer(mediainfo) if self._extract_video else DummyWriter()
                self.extracted_video = not isinstance(self._video_writer, DummyWriter)
            if self._timecode_writer is None:
                path = self._input_path.with_suffix('.txt')
                self._timecode_writer = TimeCodeWriter(
                    path if self._extract_timecodes and self.can_write_to(path) else None)
            self._video_timestamps.append(timestamp)
            self._video_writer.write_chunk(data, timestamp, (mediainfo & 0xf0) >> 4)
            self._timecode_writer.write(timestamp)
        return True

    def get_audio_writer(self, mediainfo: int) -> IAudioWriter | DummyWriter:
        format_ = mediainfo >> 4
        rate = (mediainfo >> 2) & 0x3
        bits = (mediainfo >> 1) & 0x1
        chans = mediainfo & 0x1

        match format_:
            case AudioFormat.MP3 | AudioFormat.MP3_8k:
                path = self._input_path.with_suffix('.mp3')
                return MP3Writer(path, self.warnings) if self.can_write_to(path) else DummyWriter()
            case AudioFormat.PCM | AudioFormat.PCM_LE:
                assert 0 <= rate < 4
                samplerate = SampleRates[rate]
                path = self._input_path.with_suffix('.wav')
                if not self.can_write_to(path):
                    return DummyWriter()
                if format_ == AudioFormat.PCM:
                    self.warnings.append('PCM byte order unspecified, assuming little endian.')
                return WAVWriter(path, 16 if bits == 1 else 8, 2 if chans == 1 else 1, samplerate)
            case AudioFormat.AAC:
                path = self._input_path.with_suffix('.aac')
                return AACWriter(path) if self.can_write_to(path) else DummyWriter()
            case AudioFormat.SPEEX:
                path = self._input_path.with_suffix('.spx')
                return SpeexWriter(path, self._file_length & 0xffffffff) if self.can_write_to(path) else DummyWriter()
            case _:
                self.warnings.append(f'Unable to extract audio ({format_} is unsupported).')
                return DummyWriter()

    def get_video_writer(self, mediainfo: int) -> IVideoWriter | DummyWriter:
        codec_id = mediainfo & 0x0f

        match codec_id:
            case VideoCodecID.H263 | VideoCodecID.VP6 | VideoCodecID.VP6v2:
                path = self._input_path.with_suffix('.avi')
                return AVIWriter(path, codec_id, self.warnings) if self.can_write_to(path) else DummyWriter()
            case VideoCodecID.AVC:
                path = self._input_path.with_suffix('.264')
                return RawH264Writer(path) if self.can_write_to(path) else DummyWriter()
            case _:
                self.warnings.append(f'Unable to extract video ({codec_id}) is unsupported).')
                return DummyWriter()

    def can_write_to(self, path: Path) -> bool:
        return not path.exists() or self._overwrite

    def calculate_average_framerate(self) -> Fraction | None:
        frame_count = len(self._video_timestamps)
        if frame_count > 1:
            n = (frame_count - 1) * 1000
            d = self._video_timestamps[frame_count - 1] - self._video_timestamps[0]
            return Fraction(n, d)
        return None

    def calculate_true_framerate(self) -> Fraction | None:
        delta_count: Dict[int, int] = {}

        # Calculate the distance between the timestamps, count how many times each delta appears
        for i in range(1, len(self._video_timestamps)):
            delta_s = self._video_timestamps[i] - self._video_timestamps[i - 1]

            if delta_s <= 0:
                continue
            delta = delta_s

            if delta in delta_count:
                delta_count[delta] += 1
            else:
                delta_count[delta] = 1

        threshold = len(self._video_timestamps) // 10
        min_delta = 0xffffffff  # UInt32.MaxValue

        # Find the smallest delta that made up at least 10% of the frames (grouping in delta+1
        # because of rounding, e.g. a NTSC video will have deltas of 33 and 34 ms)
        for delta, count in delta_count.items():
            if (delta + 1) in delta_count:
                count += delta_count[delta + 1]
            if (count >= threshold) and (delta < min_delta):
                min_delta = delta

        # Calculate the frame rate based on the smallest delta, and delta+1 if present
        if min_delta != 0xffffffff:
            count = delta_count[min_delta]
            total_time = min_delta * count
            total_frames = count

            if (min_delta + 1) in delta_count:
                count = delta_count[min_delta + 1]
                total_time += (min_delta + 1) * count
                total_frames += count

            if total_time != 0:
                return Fraction(total_frames * 1000, total_time)

        # Unable to calculate frame rate
        return None

    def seek(self, offset: int) -> None:
        assert self._fd is not None
        self._fd.seek(offset)
        self._file_offset = offset

    def read_uint8(self) -> int:
        return ord(self.read_bytes(1))

    def read_uint24(self) -> int:
        data = bytearray(4)
        data[1:4] = self.read_bytes(3)
        return int.from_bytes(data, 'big')

    def read_uint32(self) -> int:
        return int.from_bytes(self.read_bytes(4), 'big')

    def read_bytes(self, size: int) -> bytes:
        self._file_offset += size
        assert self._fd is not None
        return self._fd.read(size)
