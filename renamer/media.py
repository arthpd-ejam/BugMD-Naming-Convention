"""Reads a video's display resolution (width, height) without external tools.

MP4/MOV/M4V, MKV/WebM and AVI are parsed directly. Anything else (e.g. MXF)
falls back to pymediainfo when it is installed (it is bundled in the .exe).
Phone footage stored sideways with a rotation flag is reported as displayed.
"""

import struct
from pathlib import Path

Resolution = tuple[int, int] | None


def read_resolution(path: Path) -> Resolution:
    path = Path(path)
    readers = {
        ".mp4": _read_mp4, ".mov": _read_mp4, ".m4v": _read_mp4,
        ".mkv": _read_mkv, ".webm": _read_mkv, ".avi": _read_avi,
    }
    reader = readers.get(path.suffix.lower())
    if reader:
        try:
            result = reader(path)
            if result:
                return result
        except (OSError, struct.error, ValueError):
            pass
    return _read_mediainfo(path)


# --- MP4 / MOV -------------------------------------------------------------

def _boxes(f, start: int, end: int):
    """Yield (type, payload_start, box_end) for ISO-BMFF boxes in [start, end)."""
    pos = start
    while pos + 8 <= end:
        f.seek(pos)
        header = f.read(8)
        if len(header) < 8:
            return
        size, kind = struct.unpack(">I4s", header)
        payload = pos + 8
        if size == 1:
            size = struct.unpack(">Q", f.read(8))[0]
            payload += 8
        elif size == 0:
            size = end - pos
        if size < 8:
            return
        yield kind, payload, min(pos + size, end)
        pos += size


def _child(f, start, end, kind):
    for k, s, e in _boxes(f, start, end):
        if k == kind:
            return s, e
    return None


def _read_mp4(path: Path) -> Resolution:
    with open(path, "rb") as f:
        f.seek(0, 2)
        moov = _child(f, 0, f.tell(), b"moov")
        if not moov:
            return None
        for kind, s, e in _boxes(f, *moov):
            if kind != b"trak":
                continue
            mdia = _child(f, s, e, b"mdia")
            hdlr = mdia and _child(f, *mdia, b"hdlr")
            if not hdlr:
                continue
            f.seek(hdlr[0] + 8)
            if f.read(4) != b"vide":
                continue
            tkhd = _child(f, s, e, b"tkhd")
            if not tkhd:
                continue
            f.seek(tkhd[0])
            version = f.read(1)[0]
            base = tkhd[0] + (52 if version == 1 else 40)
            f.seek(base)
            matrix = struct.unpack(">9i", f.read(36))
            w, h = (v >> 16 for v in struct.unpack(">2I", f.read(8)))
            if not (w and h):
                w, h = _mp4_sample_size(f, *mdia) or (0, 0)
            if not (w and h):
                continue
            a, b = matrix[0], matrix[1]
            if a == 0 and b != 0:  # rotated 90 or 270 degrees
                w, h = h, w
            return w, h
    return None


def _mp4_sample_size(f, start, end):
    node = (start, end)
    for kind in (b"minf", b"stbl", b"stsd"):
        node = _child(f, *node, kind)
        if not node:
            return None
    f.seek(node[0] + 8 + 8 + 24)  # stsd header, entry header, visual entry prefix
    return struct.unpack(">2H", f.read(4))


# --- MKV / WebM (EBML) -----------------------------------------------------

def _vint(f, keep_marker: bool):
    first = f.read(1)
    if not first:
        raise ValueError("eof")
    b = first[0]
    length = 1
    mask = 0x80
    while length <= 8 and not b & mask:
        mask >>= 1
        length += 1
    if length > 8:
        raise ValueError("bad vint")
    value = b if keep_marker else b & (mask - 1)
    for byte in f.read(length - 1):
        value = (value << 8) | byte
    unknown = not keep_marker and value == (1 << (7 * length)) - 1
    return value, unknown


def _ebml(f, start, end):
    pos = start
    while pos < end:
        f.seek(pos)
        try:
            eid, _ = _vint(f, True)
            size, unknown = _vint(f, False)
        except ValueError:
            return
        data = f.tell()
        stop = end if unknown else min(data + size, end)
        yield eid, data, stop
        pos = stop


def _read_mkv(path: Path) -> Resolution:
    SEGMENT, TRACKS, ENTRY, VIDEO = 0x18538067, 0x1654AE6B, 0xAE, 0xE0
    WIDTH, HEIGHT, DWIDTH, DHEIGHT = 0xB0, 0xBA, 0x54B0, 0x54BA
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        for eid, s, e in _ebml(f, 0, size):
            if eid != SEGMENT:
                continue
            for tid, ts, te in _ebml(f, s, e):
                if tid != TRACKS:
                    continue
                for nid, ns, ne in _ebml(f, ts, te):
                    if nid != ENTRY:
                        continue
                    for vid, vs, ve in _ebml(f, ns, ne):
                        if vid != VIDEO:
                            continue
                        dims = {}
                        for did, ds, de in _ebml(f, vs, ve):
                            if did in (WIDTH, HEIGHT, DWIDTH, DHEIGHT):
                                f.seek(ds)
                                dims[did] = int.from_bytes(f.read(de - ds), "big")
                        w, h = dims.get(WIDTH), dims.get(HEIGHT)
                        if w and h:
                            return w, h
                return None
    return None


# --- AVI -------------------------------------------------------------------

def _read_avi(path: Path) -> Resolution:
    with open(path, "rb") as f:
        head = f.read(64 * 1024)
    if head[:4] != b"RIFF" or head[8:12] != b"AVI ":
        return None
    i = head.find(b"avih")
    if i < 0:
        return None
    w, h = struct.unpack("<2I", head[i + 8 + 32:i + 8 + 40])
    return (w, h) if w and h else None


# --- Fallback --------------------------------------------------------------

def _read_mediainfo(path: Path) -> Resolution:
    try:
        from pymediainfo import MediaInfo
        info = MediaInfo.parse(str(path))
    except Exception:
        return None
    for track in info.tracks:
        if track.track_type == "Video" and track.width and track.height:
            w, h = int(track.width), int(track.height)
            try:
                if int(float(track.rotation or 0)) % 180 == 90:
                    w, h = h, w
            except (TypeError, ValueError):
                pass
            return w, h
    return None
