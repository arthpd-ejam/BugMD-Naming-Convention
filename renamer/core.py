"""Pure naming logic: cleaning values, building names, picking variation numbers,
and validating a batch before it is renamed. No GUI or file-system writes here."""

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


def extract_variation(stem: str, task: str = "") -> int | None:
    """First number in the filename, ignoring the task number, resolutions,
    aspect ratios, dates and the like."""
    s = stem
    if task.strip():
        s = re.sub(re.escape(task.strip()), " ", s, flags=re.IGNORECASE)
    for pattern in _NOT_VARIATION:
        s = pattern.sub(" ", s)
    m = re.search(r"\d+", s)
    return int(m.group()) if m else None


def assign_variations(stems: list[str], task: str = "") -> list[int]:
    """Variation per file. Files without a number get the next numbers after the
    highest found (or 1, 2, 3... when no file has one)."""
    found = [extract_variation(s, task) for s in stems]
    next_num = max((v for v in found if v is not None), default=0) + 1
    result = []
    for v in found:
        if v is None:
            v, next_num = next_num, next_num + 1
        result.append(v)
    return result


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


def missing_fields(values: dict, required: list[str]) -> list[str]:
    return [k for k in required if not clean_value(values.get(k, ""))]


def evaluate_batch(rows: list[FileRow], shared: dict, settings: dict) -> list[str]:
    """Compute new names and statuses in place. Returns batch-level problems
    (missing shared fields); per-file problems are written to each row."""
    required = settings["required_fields"]
    per_file = {"variation", "intro", "format"}
    batch_missing = [k for k in missing_fields(shared, required) if k not in per_file]
    known_formats = set(settings.get("formats", []))
    batch_paths = {r.path.resolve() for r in rows}

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
        elif (target.exists() and target.resolve() not in batch_paths
              and row.path.name.lower() != row.new_name.lower()):
            row.status, row.ok = "A file with this name already exists", False
        elif row.path.name == row.new_name:
            row.status = "Unchanged"
        seen.setdefault(key, row)
        if row.ok and row.warnings and row.status == "Ready":
            row.status = "Ready (" + "; ".join(row.warnings) + ")"
    return [FIELD_LABELS[k] for k in batch_missing]
