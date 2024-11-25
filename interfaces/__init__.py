from abc import ABC, abstractmethod
from enum import IntEnum
from fractions import Fraction
from pathlib import Path


class IDisposable(ABC):
    @abstractmethod
    def dispose(self) -> None: ...


class IAudioWriter(ABC):
    _path: Path

    @abstractmethod
    def write_chunk(self, chunk: bytes, timestamp: int) -> None: ...

    @abstractmethod
    def finish(self) -> None: ...

    def unlink(self) -> None:
        self._path.unlink()


class IVideoWriter(ABC):
    _path: Path

    @abstractmethod
    def write_chunk(self, chunk: bytes, timestamp: int, frametype: int) -> None: ...

    @abstractmethod
    def finish(self, average_framerate: Fraction) -> None: ...

    def unlink(self) -> None:
        self._path.unlink()


class VideoCodecID(IntEnum):
    H263 = 2
    SCREEN = 3
    VP6 = 4
    VP6v2 = 5
    SCREENv2 = 6
    AVC = 7


class FLVException(Exception):
    pass
