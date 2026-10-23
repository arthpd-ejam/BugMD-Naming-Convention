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


def test_extract_variation_skips_years_and_dropdown_values():
    ev = core.extract_variation
    ignore = core.dropdown_values(S)
    assert ev("BM-75298 2026 Intro2", "BM-75298", ignore) == 2
    assert ev("2026_hook_3", "", ignore) == 3
    assert ev("BM-75298_VEO3_v2", "BM-75298", ignore) == 2
    assert ev("VEO3 IntroTest_VEO3 cut 4", "", ignore) == 4
    assert ev("DJI_20261003_0007", "", ignore) == 7
    assert ev("Intro 5 take 1") == 5
    assert ev("intro_12_9x16") == 12
    assert ev("IntroTest 6") == 6
    # A name this app produced: the number after the task wins, even with Intro/years later.
    assert ev("BM-75298-3_VEO3_BMD_Intro9_06-10-2026", "BM-75298", ignore) == 3


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


def test_intro_and_project_type_are_optional(tmp_path):
    rows = _rows(tmp_path, ["a.mp4"])
    rows[0].intro = ""
    missing = core.evaluate_batch(rows, dict(SHARED, project_type=""), S)
    assert missing == [] and rows[0].ok
    assert rows[0].new_name == (
        "BM-75415-1_BMD_VMS_META_VID-1080x1920_DAV_ART_BigBeautifulSale_MICE_25_03-10-2026.mp4")


def test_marked_version_number_beats_first_number():
    ev = core.extract_variation
    ignore = core.dropdown_values(S)
    assert ev("BM-75914_3Oils_9x16_roughcut_v7_motion", "BM-75957", ignore) == 7
    assert ev("BM-75914_3Oils_9x16_roughcut_v8_K2", "BM-75957", ignore) == 8
    assert ev("BM-75914_3Oils_v7_4x5", "BM-75914", ignore) == 7
    assert ev("3Oils var_2", "", ignore) == 2
    assert ev("Intro3_v7", "", ignore) == 3          # Intro number still wins
    assert ev("VEO3 hook 4", "", ignore) == 4         # VEO3 is not "v" + number
    assert ev("BM-75957-5_BMD_v9", "BM-75957", ignore) == 5
    # No v-number: skip "3Oils", use a real number or none at all.
    assert ev("BM-75914_3Oils_final2_4x5", "BM-75957", ignore) == 2
    assert ev("BM-75914_3Oils_final_4x5", "BM-75957", ignore) is None
    assert core.assign_variations(["3Oils_v7", "3Oils_v8", "3Oils_final"], "", ignore) == [7, 8, 9]


def test_fix_duplicates_keeps_format_pairs(tmp_path):
    rows = _rows(tmp_path, ["a_9x16.mp4", "b_9x16.mp4", "a_4x5.mp4", "b_4x5.mp4", "c.mp4"])
    for r in rows:
        r.variation = "3"
    rows[2].format = rows[3].format = "VID-1080x1350"
    rows[4].variation, rows[4].format = "4", "VID-1080x1080"
    assert core.fix_duplicates(rows, SHARED, S) == 2
    assert [r.variation for r in rows] == ["3", "5", "3", "5", "4"]
    assert all(r.ok for r in rows)
