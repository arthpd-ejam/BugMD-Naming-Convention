"""Loads the editable dropdown lists (settings.json) and per-user remembered values."""

import copy
import json
import os
import sys
from pathlib import Path

APP_NAME = "BugMD Video Renamer"
SETTINGS_FILENAME = "settings.json"

DEFAULT_SETTINGS = {
    "_help": (
        "Edit the lists below to add or remove dropdown options. "
        "name_template controls the final name; a segment between underscores "
        "is dropped when all of its fields are empty."
    ),
    "name_template": (
        "{task}-{variation}_{intro}_{brand}_{product}_{channel}_{format}_"
        "{strategist}_{editor}_{script}_{project_type}_{test_type}_{pest_angle}_{date}"
    ),
    "required_fields": [
        "task", "variation", "intro", "brand", "product", "channel", "format",
        "editor", "script", "project_type", "date",
    ],
    "date_format": "%d-%m-%Y",
    "format_prefix": "VID-",
    "video_extensions": [".mp4", ".mov", ".mxf", ".avi", ".mkv", ".m4v", ".webm"],
    "intro_styles": ["CL", "BA", "TT", "SBS", "AA", "Banner", "Prod", "VEO3", "PAP", "FS"],
    "brands": {
        "BMD": ["EPC", "VMS", "FNT", "SQS", "PDP", "NBZ", "WH"],
        "SHA": ["OG", "CC", "AS"],
        "HYD": ["TRSS", "TALC"],
        "NVD": ["AMS", "EWP"],
    },
    "channels": ["META", "TIKTOK", "YOUTUBE", "APPLOVIN", "AMAZON", "TV"],
    "formats": [
        "VID-1080x1920", "VID-1080x1350", "VID-1080x1080", "VID-1080x1620", "VID-1920x1080",
    ],
    "strategists": ["DAV", "CHR", "HOLLY", "AUT"],
    "editors": [
        "CRL", "JOC", "MRK", "ART", "FRO", "IVN", "MIC", "RPH",
        "JUN", "AGU", "ANA", "IGN", "PAO",
    ],
    "project_types": {
        "Proven": ["BackendTest", "THT", "16x9", "Spanish", "German", "BackendTest_VEO3"],
        "Retro": [
            "IntroTest", "HookTest", "LeadTest", "POVTest", "AIAvTest", "NewEdit", "VOF",
            "VOM", "Rehash", "IntroTest_VEO3", "HookTest_VEO3", "VEO3", "Rehash_Spanish",
        ],
        "Unproven": ["ScriptTest"],
    },
}


def app_dir() -> Path:
    """Folder holding the .exe when frozen, otherwise the project root."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def user_data_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.join(Path.home(), ".config")
    path = Path(base) / "BugMD-Video-Renamer"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_settings(path: Path | None = None) -> tuple[dict, Path, str | None]:
    """Return (settings, path, warning). Writes defaults if the file is missing.

    Keys missing from the file fall back to the defaults so an older or
    partially edited settings.json keeps working.
    """
    path = path or app_dir() / SETTINGS_FILENAME
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    warning = None
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                settings.update(json.load(f))
        except (OSError, ValueError) as e:
            warning = f"Could not read {path.name} ({e}). Using built-in defaults."
    else:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_SETTINGS, f, indent=2)
        except OSError:
            pass  # read-only location; defaults still work
    return settings, path, warning


def load_state() -> dict:
    try:
        with open(user_data_dir() / "state.json", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    try:
        with open(user_data_dir() / "state.json", "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except OSError:
        pass
