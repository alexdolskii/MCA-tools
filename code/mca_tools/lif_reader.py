"""Validate LIF block boundaries before passing a bounded view to readlif.

Bio-Formats LIFReader recognizes zero-filled tails in newer LIF files.
readlif 0.6.5/0.6.6 instead close the handle on a non-magic block and mask
the original error. Only verified zero padding is hidden from the parser;
the source file, pixel offsets and original XML are never modified.
"""

import io
import os
import struct
from dataclasses import dataclass

from readlif.reader import LifFile

_MAGIC = b"\x70\x00\x00\x00"
_MEMORY = b"\x2a"


class LifFormatError(ValueError):
    """An unsupported or incomplete LIF structure, with a byte position."""


@dataclass(frozen=True)
class LifLayout:
    file_size: int
    data_end: int
    block_sizes: tuple[int, ...]

    def as_dict(self):
        return {
            "file_size_bytes": self.file_size,
            "data_end_byte": self.data_end,
            "memory_block_count": len(self.block_sizes),
            "verified_zero_padding_bytes": self.file_size - self.data_end,
        }


def _read_exact(stream, count, limit, label):
    offset = stream.tell()
    available = limit - offset
    if count > available:
        raise LifFormatError(
            f"Incomplete LIF {label} at byte {offset}: "
            f"expected {count} bytes, only {available} remain."
        )
    data = stream.read(count)
    if len(data) != count:
        raise LifFormatError(f"Short read of LIF {label} at byte {offset}.")
    return data


def _expect(stream, expected, limit, label):
    offset = stream.tell()
    found = _read_exact(stream, len(expected), limit, label)
    if found != expected:
        raise LifFormatError(
            f"Invalid LIF {label} at byte {offset}: "
            f"expected {expected.hex(' ')}, found {found.hex(' ')}. "
            "The layout may be unsupported or the file may be incomplete."
        )


def _uint32(stream, limit, label):
    return struct.unpack("<I", _read_exact(stream, 4, limit, label))[0]


def _skip(stream, count, limit, label):
    offset = stream.tell()
    if count > limit - offset:
        raise LifFormatError(
            f"Incomplete LIF {label} at byte {offset}: "
            f"declared end {offset + count} exceeds file size {limit}."
        )
    stream.seek(count, io.SEEK_CUR)


def _scan_layout(stream, size):
    _expect(stream, _MAGIC, size, "header signature")
    _read_exact(stream, 4, size, "header length")
    _expect(stream, _MEMORY, size, "XML marker")
    xml_chars = _uint32(stream, size, "XML length")
    _skip(stream, xml_chars * 2, size, "XML header")
    blocks = []
    while stream.tell() < size:
        offset = stream.tell()
        marker = stream.read(min(4, size - offset))
        if blocks and marker and not any(marker):
            # Check the entire tail, not just its first few bytes. Bounded
            # chunks avoid loading a potentially large padding area into RAM.
            while stream.tell() < size:
                position = stream.tell()
                chunk = stream.read(min(1024 * 1024, size - position))
                if not chunk:
                    raise LifFormatError(
                        f"Short read of LIF zero padding at byte {position}."
                    )
                if any(chunk):
                    first = next(i for i, value in enumerate(chunk) if value)
                    raise LifFormatError(
                        "Unexpected nonzero data after a zero block marker "
                        f"at byte {position + first}; refusing to skip it."
                    )
            return LifLayout(size, offset, tuple(blocks))
        stream.seek(offset)
        _expect(stream, _MAGIC, size, "memory-block signature")
        _read_exact(stream, 4, size, "memory-block header length")
        _expect(stream, _MEMORY, size, "memory-block marker")
        length_offset = stream.tell()
        block_size = _uint32(stream, size, "memory-block size")
        marker = _read_exact(stream, 1, size, "description marker")
        if marker != _MEMORY:
            # The LIF format permits both 32-bit and 64-bit memory lengths.
            stream.seek(length_offset)
            block_size = struct.unpack(
                "<Q", _read_exact(stream, 8, size, "64-bit memory-block size")
            )[0]
            _expect(stream, _MEMORY, size, "description marker")
        description_chars = _uint32(stream, size, "description length")
        _skip(stream, description_chars * 2, size, "memory description")
        _skip(stream, block_size, size, "memory payload")
        if block_size:
            blocks.append(block_size)
    return LifLayout(size, size, tuple(blocks))


class _LimitedReader(io.BufferedReader):
    """Expose a logical EOF without copying or rewriting the source file."""

    def __init__(self, path):
        super().__init__(io.FileIO(path, "r"))
        self.limit = os.fstat(self.fileno()).st_size

    def seek(self, offset, whence=io.SEEK_SET):
        if whence == io.SEEK_END:
            offset, whence = self.limit + offset, io.SEEK_SET
        return super().seek(offset, whence)

    def read(self, size=-1):
        remaining = max(0, self.limit - self.tell())
        return super().read(remaining if size < 0 else min(size, remaining))


def load_lif(path):
    """Load complete blocks; accept padding only after XML size agreement."""
    with _LimitedReader(path) as stream:
        layout = _scan_layout(stream, stream.limit)
        stream.limit = layout.data_end
        stream.seek(0)
        lif = LifFile(stream)
    # Subsequent image reads reopen the original file at its original offsets.
    lif.filename = str(path)
    if layout.data_end < layout.file_size:
        declared = tuple(
            size
            for node in lif.xml_root.iter("Memory")
            if (size := int(node.attrib.get("Size", "0"))) > 0
        )
        if declared != layout.block_sizes:
            raise LifFormatError(
                f"Zero padding starts at byte {layout.data_end}, but the "
                "complete memory blocks do not match the XML-declared "
                "sizes. The file may be incomplete; export was stopped."
            )
    return lif, layout
