"""Pure naming logic: cleaning values, building names, picking variation numbers,
and validating a batch before it is renamed. No GUI or file-system writes here."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                  *(f"LPT{i}" for i in range(1, 10))}
MAX_PATH = 259

FIELD_LABELS = {
    "task": "Task #", "variation": "Variation", "intro": "Intro Style", "brand": "Brand",
    "product": "Product", "channel": "Channel", "format": "Format", "strategist": "Strategist",
    "editor": "Editor", "script": "Script", "project_type": "Project Type",
    "test_type": "Test Type", "pest_angle": "Pest_Angle", "date": "Date",
}

# Tokens that contain digits but are never the variation number.
_NOT_VARIATION = [
    re.compile(r"\d{3,5}\s*[xX×]\s*\d{3,5}"),        # resolution 1080x1920
    re.compile(r"(?<!\d)\d{1,2}\s*[xX:]\s*\d{1,2}(?!\d)"),  # aspect ratio 9x16, 4:5
    re.compile(r"(?<!\d)(?:480|720|1080|1440|2160|4320)[pP](?![a-zA-Z])"),
    re.compile(r"(?<![a-zA-Z0-9])[2-8][kK](?![a-zA-Z])"),  # 4K
    re.compile(r"(?<!\d)\d{1,4}[-.]\d{1,2}[-.]\d{2,4}(?!\d)"),  # dates
    re.compile(r"(?<![a-zA-Z])[A-Za-z]{1,5}-\d{3,}"),     # task ids like BM-75415
]


def clean_value(value) -> str:
    """Trim, drop characters Windows forbids, collapse repeated underscores and
    strip underscores from the ends."""
    s = INVALID_CHARS.sub("", str(value or "")).strip()
    s = re.sub(r"_+", "_", s)
    return s.strip("_ ").strip()


def build_name(template: str, values: dict) -> str:
    """Fill the template; a '_' segment whose fields are all empty is dropped."""
    parts = []
    for segment in re.split(r"_(?![^{]*\})", template):  # "_" outside {placeholders}
        keys = re.findall(r"\{(\w+)\}", segment)
        cleaned = {k: clean_value(values.get(k, "")) for k in keys}
        if keys and not any(cleaned.values()):
            continue
        filled = segment
        for k, v in cleaned.items():
            filled = filled.replace("{" + k + "}", v)
        filled = filled.strip("-")
        if filled:
            parts.append(filled)
    name = re.sub(r"_+", "_", "_".join(parts)).strip("_ .")
    return name


_YEAR_OR_LONG = re.compile(r"(?<!\d)(?:(?:19|20)\d{2}|\d{5,})(?!\d)")  # 2026, 20261003
_INTRO_NUMBER = re.compile(r"intro(?![a-z])[\s_#-]*(\d+)", re.IGNORECASE)    # Intro2, intro_2
_MARKED_NUMBER = re.compile(                                                   # v7, var_2, version 3
    r"(?<![a-z])(?:variation|version|var|ver|v)[\s_#-]*(\d+)(?!\d)", re.IGNORECASE)


def extract_variation(stem: str, task: str = "", ignore: tuple[str, ...] = ()) -> int | None:
    """Variation number in a filename, in order of preference:
    1. the number right after the task number in a name this app made (BM-75415-3_...)
    2. the number after "Intro" (Intro2, Intro 2, intro_2)
    3. the number after v / var / ver / version / variation (v7, V8, var_2)
    4. the first number (not glued to the front of a word like 3Oils) left after removing the task number, resolutions, ratios,
       dates, years, long numbers and any dropdown values with digits (e.g. VEO3)."""
    s = stem
    task = task.strip()
    if task:
        m = re.search(re.escape(task) + r"-(\d+)(?!\d)", s, flags=re.IGNORECASE)
        if m:
            return int(m.group(1))
        s = re.sub(re.escape(task), " ", s, flags=re.IGNORECASE)
    for token in sorted({t for t in ignore if t and re.search(r"\d", t)}, key=len, reverse=True):
        s = re.sub(r"(?<![A-Za-z0-9])" + re.escape(token) + r"(?![A-Za-z0-9])", " ", s,
                   flags=re.IGNORECASE)
    for pattern in _NOT_VARIATION:
        s = pattern.sub(" ", s)
    s = _YEAR_OR_LONG.sub(" ", s)
    # A number glued to the front of a word (3Oils, 2nd) is part of a name, not a variation.
    m = (_INTRO_NUMBER.search(s) or _MARKED_NUMBER.search(s)
         or re.search(r"\d+(?![0-9A-Za-z])", s))
    return int(m.group(m.lastindex or 0)) if m else None


def assign_variations(stems: list[str], task: str = "", ignore: tuple[str, ...] = ()) -> list[int]:
    """Variation per file. Files without a number get the next numbers after the
    highest found (or 1, 2, 3... when no file has one)."""
    found = [extract_variation(s, task, ignore) for s in stems]
    next_num = max((v for v in found if v is not None), default=0) + 1
    result = []
    for v in found:
        if v is None:
            v, next_num = next_num, next_num + 1
        result.append(v)
    return result


def dropdown_values(settings: dict) -> tuple[str, ...]:
    """Every option in the dropdown lists (used to keep e.g. 'VEO3' from being read
    as variation 3)."""
    values = list(settings.get("intro_styles", [])) + list(settings.get("formats", []))
    values += settings.get("channels", []) + settings.get("strategists", []) + settings.get("editors", [])
    for mapping in (settings.get("brands", {}), settings.get("project_types", {})):
        for k, items in mapping.items():
            values += [k, *items]
    return tuple(values)


def parse_existing(stem: str, intro_styles: list[str], format_prefix: str = "VID-") -> dict:
    """Intro and format already present in a filename (e.g. one this app named),
    so re-loading a renamed folder keeps per-file choices."""
    tokens = stem.split("_")
    fmt = re.compile(re.escape(format_prefix) + r"\d+x\d+$", re.IGNORECASE)
    found = {}
    for t in tokens:
        if "intro" not in found and t in intro_styles:
            found["intro"] = t
        if "format" not in found and fmt.match(t):
            found["format"] = format_prefix + t[len(format_prefix):]
    return found


def format_for_resolution(width: int | None, height: int | None, prefix: str = "VID-") -> str:
    if not width or not height:
        return ""
    return f"{prefix}{width}x{height}"


@dataclass
class FileRow:
    path: Path
    variation: str = ""
    variation_edited: bool = False
    intro: str = ""
    format: str = ""
    resolution: str = ""
    new_name: str = ""
    status: str = ""
    ok: bool = False
    warnings: list[str] = field(default_factory=list)


def fix_duplicates(rows: list[FileRow], shared: dict, settings: dict) -> int:
    """Give clashing files new variation numbers. In each group of identical names
    the first file keeps its number; the 2nd, 3rd... get the next free numbers.
    The same position in different groups gets the same new number, so the 9x16
    and 4x5 cuts of one variation stay paired. Returns how many files changed."""
    evaluate_batch(rows, shared, settings)
    groups: dict[str, list[FileRow]] = {}
    for row in rows:
        if row.status == "Duplicate name":
            groups.setdefault(row.new_name.lower(), []).append(row)
    used = [int(r.variation) for r in rows if clean_value(r.variation).isdigit()]
    base = max(used, default=0)
    changed = 0
    for group in groups.values():
        for k, row in enumerate(group[1:], 1):
            row.variation, row.variation_edited = str(base + k), True
            changed += 1
    evaluate_batch(rows, shared, settings)
    return changed


def missing_fields(values: dict, required: list[str]) -> list[str]:
    return [k for k in required if not clean_value(values.get(k, ""))]


def folder_names(folder: Path) -> set[str]:
    """Lower-cased names of everything in a folder (one directory read)."""
    try:
        return {name.lower() for name in os.listdir(folder)}
    except OSError:
        return set()


def evaluate_batch(rows: list[FileRow], shared: dict, settings: dict,
                   existing: set[str] | None = None) -> list[str]:
    """Compute new names and statuses in place. Returns batch-level problems
    (missing shared fields); per-file problems are written to each row.

    existing: lower-cased names already in the folder. Pass a cached set to avoid
    touching the disk (slow on Windows/network drives when called per keystroke)."""
    required = settings["required_fields"]
    per_file = {"variation", "intro", "format"}
    batch_missing = [k for k in missing_fields(shared, required) if k not in per_file]
    known_formats = set(settings.get("formats", []))
    if existing is None:
        existing = set()
        for parent in {r.path.parent for r in rows}:
            existing |= folder_names(parent)
    batch_names = {r.path.name.lower() for r in rows}

    for row in rows:
        values = dict(shared, variation=row.variation, intro=row.intro, format=row.format)
        row.warnings = []
        row.new_name = build_name(settings["name_template"], values) + row.path.suffix.lower()
        missing = [FIELD_LABELS[k] for k in missing_fields(values, required) if k in per_file]
        if missing:
            row.status, row.ok = "Missing " + ", ".join(missing), False
            continue
        if row.variation and not clean_value(row.variation).isdigit():
            row.warnings.append("variation is not a number")
        if row.format and row.format not in known_formats:
            row.warnings.append("format not in list")
        row.status, row.ok = "Ready", True

    # Collisions inside the batch and with other files already in the folder.
    seen: dict[str, FileRow] = {}
    for row in rows:
        if not row.ok:
            continue
        key = row.new_name.lower()
        target = row.path.with_name(row.new_name)
        if Path(row.new_name).stem.upper() in RESERVED_NAMES:
            row.status, row.ok = "Reserved Windows name", False
        elif len(str(target)) > MAX_PATH:
            row.status, row.ok = "Path too long", False
        elif key in seen:
            row.status, row.ok = "Duplicate name", False
            other = seen[key]
            if other.ok:
                other.status, other.ok = "Duplicate name", False
        elif key in existing and key not in batch_names:
            row.status, row.ok = "A file with this name already exists", False
        elif row.path.name == row.new_name:
            row.status = "Unchanged"
        seen.setdefault(key, row)
        if row.ok and row.warnings and row.status == "Ready":
            row.status = "Ready (" + "; ".join(row.warnings) + ")"
    return [FIELD_LABELS[k] for k in batch_missing]
