import pytest

from renamer import ops


@pytest.fixture(autouse=True)
def appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


def test_swap_and_undo(tmp_path):
    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    a.write_text("A")
    b.write_text("B")
    done = ops.rename_files([(a, b), (b, a)])
    ops.save_undo(tmp_path, done)
    assert a.read_text() == "B" and b.read_text() == "A"
    path, entry = ops.latest_undo()
    assert ops.undo(path, entry) == 2
    assert a.read_text() == "A" and b.read_text() == "B"
    assert ops.latest_undo() is None


def test_failure_rolls_back(tmp_path):
    a, c, blocker = tmp_path / "a.mp4", tmp_path / "c.mp4", tmp_path / "taken.mp4"
    a.write_text("A")
    c.write_text("C")
    blocker.write_text("X")
    with pytest.raises(FileExistsError):
        ops.rename_files([(a, tmp_path / "new.mp4"), (c, blocker)])
    assert a.read_text() == "A" and c.read_text() == "C" and blocker.read_text() == "X"
    assert sorted(p.name for p in tmp_path.iterdir() if p.is_file()) == ["a.mp4", "c.mp4", "taken.mp4"]
