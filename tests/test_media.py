import shutil
import subprocess

import pytest

from renamer.media import read_resolution

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


def make(path, size, extra=()):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"color=c=red:s={size}:d=0.2", *extra, str(path)], check=True)


@pytest.mark.parametrize("ext", [".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"])
def test_reads_resolution(tmp_path, ext):
    f = tmp_path / f"clip{ext}"
    make(f, "1080x1920")
    assert read_resolution(f) == (1080, 1920)


def test_faststart_mp4(tmp_path):
    f = tmp_path / "fs.mp4"
    make(f, "1080x1350", ["-movflags", "+faststart"])
    assert read_resolution(f) == (1080, 1350)


def test_rotated_phone_clip(tmp_path):
    src, f = tmp_path / "src.mp4", tmp_path / "rot.mp4"
    make(src, "1920x1080")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-display_rotation", "90",
                    "-i", str(src), "-c", "copy", str(f)], check=True)
    assert read_resolution(f) == (1080, 1920)


def test_garbage_file(tmp_path):
    f = tmp_path / "bad.mp4"
    f.write_bytes(b"not a video at all")
    assert read_resolution(f) is None
