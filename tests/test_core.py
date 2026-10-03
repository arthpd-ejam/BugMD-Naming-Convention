from pathlib import Path

from renamer import core
from renamer.settings import DEFAULT_SETTINGS as S

SHARED = {
    "task": "BM-75415", "brand": "BMD", "product": "VMS", "channel": "META",
    "strategist": "DAV", "editor": "ART", "script": "BigBeautifulSale",
    "project_type": "Unproven", "test_type": "", "pest_angle": "MICE_25_", "date": "03-10-2026",
}


def test_build_name_matches_spec():
    values = dict(SHARED, variation="1", intro="VEO3", format="VID-1080x1920")
    assert core.build_name(S["name_template"], values) == (
        "BM-75415-1_VEO3_BMD_VMS_META_VID-1080x1920_DAV_ART_BigBeautifulSale_Unproven_MICE_25_03-10-2026")


def test_empty_optional_fields_are_dropped():
    values = dict(SHARED, variation="2", intro="CL", format="VID-1080x1080",
                  strategist="", test_type="ScriptTest", pest_angle="")
    assert core.build_name(S["name_template"], values) == (
        "BM-75415-2_CL_BMD_VMS_META_VID-1080x1080_ART_BigBeautifulSale_Unproven_ScriptTest_03-10-2026")


def test_clean_value():
    assert core.clean_value("  MICE__25_ ") == "MICE_25"
    assert core.clean_value('Big:Sale?') == "BigSale"
    assert core.clean_value("_AIAvTest_Old_") == "AIAvTest_Old"


def test_extract_variation_first_number():
    ev = core.extract_variation
    assert ev("BM-75415 V3 1080x1920 final2", "BM-75415") == 3
    assert ev("Ad_9x16_v2") == 2
    assert ev("ad 1080p 4K take5") == 5
    assert ev("IMG_4021") == 4021
    assert ev("BM-75415-1_VEO3_BMD_VMS_META_VID-1080x1920_ART_MICE_25_03-10-2026", "BM-75415") == 1
    assert ev("BM-75415-7_x", "") == 7
    assert ev("final cut") is None
    assert ev("03") == 3


def test_assign_variations_fills_gaps_after_highest():
    assert core.assign_variations(["a", "b", "c"]) == [1, 2, 3]
    assert core.assign_variations(["v2", "intro", "v5", "x"]) == [2, 6, 5, 7]


def test_format_for_resolution():
    assert core.format_for_resolution(1080, 1920) == "VID-1080x1920"
    assert core.format_for_resolution(None, None) == ""


def _rows(tmp_path, names):
    rows = []
    for n in names:
        p = tmp_path / n
        p.write_bytes(b"")
        rows.append(core.FileRow(path=p, variation="1", intro="CL", format="VID-1080x1920"))
    return rows


def test_evaluate_batch_flags_duplicates_and_missing(tmp_path):
    rows = _rows(tmp_path, ["a.mp4", "b.MP4", "c.mov"])
    rows[2].format = ""
    missing = core.evaluate_batch(rows, SHARED, S)
    assert missing == []
    assert [r.status for r in rows] == ["Duplicate name", "Duplicate name", "Missing Format"]
    assert rows[0].new_name.endswith(".mp4") and rows[1].new_name.endswith(".mp4")


def test_evaluate_batch_existing_file_and_unknown_format(tmp_path):
    rows = _rows(tmp_path, ["a.mp4", "b.mp4"])
    rows[1].variation = "2"
    rows[1].format = "VID-720x1280"
    values = dict(SHARED, variation="1", intro="CL", format="VID-1080x1920")
    (tmp_path / (core.build_name(S["name_template"], values) + ".mp4")).write_bytes(b"")
    core.evaluate_batch(rows, SHARED, S)
    assert rows[0].status == "A file with this name already exists"
    assert rows[1].ok and "format not in list" in rows[1].status


def test_evaluate_batch_reports_missing_shared(tmp_path):
    rows = _rows(tmp_path, ["a.mp4"])
    missing = core.evaluate_batch(rows, dict(SHARED, task="", script=" "), S)
    assert missing == ["Task #", "Script"]


def test_parse_existing():
    stem = "BM-75415-3_CL_BMD_VMS_META_VID-1080x1080_DAV_ART_Script_Unproven_03-10-2026"
    assert core.parse_existing(stem, S["intro_styles"]) == {"intro": "CL", "format": "VID-1080x1080"}
    assert core.parse_existing("hook alt", S["intro_styles"]) == {}
