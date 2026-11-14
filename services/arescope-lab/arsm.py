"""Strict, allocation-bounded parser for the Quest ARSM wire format."""

from dataclasses import dataclass
import struct

MAX_VERTICES = 2_000_000
MAX_PNG_BYTES = 24 * 1024 * 1024


class InvalidMesh(ValueError):
    pass


@dataclass(frozen=True)
class MeshInfo:
    version: int
    vertex_count: int
    index_count: int
    atlas_width: int = 0
    atlas_height: int = 0
    png_bytes: int = 0


def parse_arsm(body: bytes) -> MeshInfo:
    if len(body) < 16:
        raise InvalidMesh("Truncated ARSM header")
    magic, version, vertices, indices = struct.unpack_from("<4sIII", body)
    if magic != b"ARSM" or version not in (1, 2):
        raise InvalidMesh("Invalid ARSM magic or version")
    if not 1 <= vertices <= MAX_VERTICES or indices % 3:
        raise InvalidMesh("Invalid vertex or triangle count")
    base = 16 + vertices * 16 + indices * 4
    width = height = png_length = 0
    if version == 1:
        expected = base
    else:
        atlas = base + vertices * 8
        if len(body) < atlas + 12:
            raise InvalidMesh("Truncated UV or atlas block")
        width, height, png_length = struct.unpack_from("<III", body, atlas)
        if png_length > MAX_PNG_BYTES:
            raise InvalidMesh("PNG exceeds 24 MiB")
        expected = atlas + 12 + png_length
    if len(body) != expected:
        raise InvalidMesh("ARSM body length does not match header")
    start = 16 + vertices * 16
    for (index,) in struct.iter_unpack("<I", memoryview(body)[start:base]):
        if index >= vertices:
            raise InvalidMesh("Triangle index outside vertex range")
    return MeshInfo(version, vertices, indices, width, height, png_length)
