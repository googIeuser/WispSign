"""Generate packaging/assets/wispsign.ico: a lime "W" on a near-black rounded tile.

Pure standard library (struct + zlib); the icon is committed, this script only
documents and reproduces it.
"""

import itertools
import struct
import zlib
from pathlib import Path

BG = (11, 11, 11, 255)
LIME = (182, 255, 0, 255)
CLEAR = (0, 0, 0, 0)
SIZES = (16, 32, 48, 64, 128, 256)
TARGET = Path(__file__).resolve().parent / "assets" / "wispsign.ico"
# W polyline in a unit square, drawn as thick segments.
W_POINTS = ((0.18, 0.25), (0.34, 0.75), (0.5, 0.42), (0.66, 0.75), (0.82, 0.25))
STROKE = 0.065
CORNER = 0.2


def _dist_to_segment(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5


def _inside_tile(x, y):
    cx = min(max(x, CORNER), 1 - CORNER)
    cy = min(max(y, CORNER), 1 - CORNER)
    return ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 <= CORNER


def _pixel(x, y):
    if not _inside_tile(x, y):
        return CLEAR
    near = min(_dist_to_segment(x, y, a, b) for a, b in itertools.pairwise(W_POINTS))
    return LIME if near <= STROKE else BG


def _png(size):
    rows = bytearray()
    for j in range(size):
        rows.append(0)
        for i in range(size):
            samples = [
                _pixel((i + sx / 2 + 0.25) / size, (j + sy / 2 + 0.25) / size)
                for sx in range(2)
                for sy in range(2)
            ]
            rows += bytes(sum(s[c] for s in samples) // 4 for c in range(4))

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + chunk(b"IEND", b"")
    )


def build_ico():
    images = [_png(s) for s in SIZES]
    out = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    for size, data in zip(SIZES, images):
        dim = 0 if size >= 256 else size
        out += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return out + b"".join(images)


if __name__ == "__main__":
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_bytes(build_ico())
    print(f"wrote {TARGET}")
