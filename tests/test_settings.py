import json

import pytest

from renamer import settings


@pytest.fixture(autouse=True)
def appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(settings, "app_dir", lambda: tmp_path / "exe")
    (tmp_path / "exe").mkdir()


def test_text_to_list():
    assert settings.text_to_list(" META\n\nTIKTOK, META ,YOUTUBE\n") == ["META", "TIKTOK", "YOUTUBE"]


def test_mapping_round_trip():
    text = "BMD: EPC, VMS\n\nSHA:OG,CC\nNEW"
    mapping = settings.text_to_mapping(text)
    assert mapping == {"BMD": ["EPC", "VMS"], "SHA": ["OG", "CC"], "NEW": []}
    assert settings.text_to_mapping(settings.mapping_to_text(mapping)) == mapping


def test_user_settings_win_over_shared_file(tmp_path):
    (tmp_path / "exe" / "settings.json").write_text(json.dumps({"channels": ["SHARED"]}))
    assert settings.load_settings()[0]["channels"] == ["SHARED"]
    s, _ = settings.load_settings()
    s["channels"] = ["MINE"]
    settings.save_settings(s)
    loaded, warning = settings.load_settings()
    assert loaded["channels"] == ["MINE"] and warning is None
    assert loaded["editors"] == settings.DEFAULT_SETTINGS["editors"]


def test_defaults_when_no_files():
    s, warning = settings.load_settings()
    assert s["brands"]["BMD"][0] == "EPC" and warning is None
