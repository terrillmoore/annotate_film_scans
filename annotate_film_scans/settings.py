##############################################################################
#
# Name: settings.py
#
# Function:
#       Load, merge, check, and initialize the camera/lens/film/... settings
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
# Notes:
#       Settings come from the built-in settings.json in the package,
#       followed by every *.json file at the top level of the user's
#       settings directory, in sorted order. Each file has the same
#       structure: { category: { entry name: { tag: value, ... } } },
#       plus an optional "defaults": { category: entry name }.
#
#       A later entry replaces an earlier one with the same name
#       wholesale; an entry (or default) whose value is null removes the
#       earlier one. Keys starting with "_" are comments and are ignored
#       at every level.
#
##############################################################################

#### imports ####
from collections.abc import Mapping
from importlib.resources import files as importlib_files
import json
import os
import pathlib
import re
import shutil

#### constants ####
CATEGORIES = ("camera", "lens", "film", "lab", "process", "developer", "author")
DEFAULTS = "defaults"

APP_DIR_NAME = "annotate-film-scans"
ENV_SETTINGS_DIR = "ANNOTATE_FILM_SCANS_CONFIG"

# exiftool groups that make sense in settings entries. Anything else is
# probably a typo, since exiftool quietly ignores tags it can't write.
KNOWN_GROUPS = frozenset((
    "EXIF", "ExifIFD", "IFD0", "IPTC",
    "XMP", "XMP-aux", "XMP-dc", "XMP-exif", "XMP-exifEX", "XMP-photoshop",
    "XMP-xmp", "XMP-AnalogExif", "XMP-AnnotateFilmScans",
    ))

RE_TAG = re.compile(r"([A-Za-z0-9-]+):([A-Za-z][A-Za-z0-9]*)")

class SettingsError(Exception):
    """ problems with settings files """
    pass

#### where things are ####

def builtin_settings_path() -> pathlib.Path:
    return pathlib.Path(str(importlib_files("annotate_film_scans").joinpath("settings.json")))

def templates_path() -> pathlib.Path:
    return pathlib.Path(str(importlib_files("annotate_film_scans").joinpath("templates")))

def user_settings_dir(
        environ: Mapping[str, str] | None = None,
        os_name: str | None = None,
        home: pathlib.Path | None = None
        ) -> pathlib.Path:
    """
    Return the user's settings directory: $ANNOTATE_FILM_SCANS_CONFIG if
    set; otherwise %APPDATA%\\annotate-film-scans on Windows, and
    $XDG_CONFIG_HOME/annotate-film-scans (default ~/.config) elsewhere,
    macOS included.
    """
    if environ is None:
        environ = os.environ
    if os_name is None:
        os_name = os.name
    if home is None:
        home = pathlib.Path.home()

    override = environ.get(ENV_SETTINGS_DIR)
    if override:
        return pathlib.Path(override).expanduser()

    if os_name == "nt":
        appdata = environ.get("APPDATA")
        base = pathlib.Path(appdata) if appdata else home / "AppData" / "Roaming"
    else:
        xdg = environ.get("XDG_CONFIG_HOME")
        # the XDG spec says to ignore relative paths
        if xdg and pathlib.PurePosixPath(xdg).is_absolute():
            base = pathlib.Path(xdg)
        else:
            base = home / ".config"
    return base / APP_DIR_NAME

def user_settings_files(user_dir: pathlib.Path) -> list[pathlib.Path]:
    if not user_dir.is_dir():
        return []
    return sorted(p for p in user_dir.glob("*.json") if p.is_file())

#### reading ####

def _strip_comments(d: dict) -> dict:
    return { k: v for k, v in d.items() if not k.startswith("_") }

def read_settings_file(path: pathlib.Path) -> dict:
    """
    Read and structurally validate one settings file, returning it with
    comments removed. Entries and defaults may be None (meaning "remove").
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as e:
        raise SettingsError(f"{path}: can't read: {e}")
    except json.JSONDecodeError as e:
        raise SettingsError(f"{path}: invalid JSON: {e}")

    if not isinstance(data, dict):
        raise SettingsError(f"{path}: top level must be a JSON object")

    result = dict()
    for category, entries in _strip_comments(data).items():
        if category != DEFAULTS and category not in CATEGORIES:
            raise SettingsError(
                f"{path}: unknown category '{category}' (expected one of: "
                f"{', '.join(CATEGORIES + (DEFAULTS,))})"
                )
        if not isinstance(entries, dict):
            raise SettingsError(f"{path}: '{category}' must be a JSON object")

        entries = _strip_comments(entries)
        if category == DEFAULTS:
            for key, value in entries.items():
                if key not in CATEGORIES:
                    raise SettingsError(f"{path}: defaults: unknown category '{key}'")
                if value is not None and not isinstance(value, str):
                    raise SettingsError(f"{path}: defaults: '{key}' must be an entry name or null")
            result[category] = entries
            continue

        clean = dict()
        for name, tags in entries.items():
            if tags is None:
                clean[name] = None
            elif isinstance(tags, dict):
                clean[name] = _strip_comments(tags)
            else:
                raise SettingsError(f"{path}: {category} '{name}' must be a JSON object or null")
        result[category] = clean
    return result

#### the merged settings ####

class Settings:
    def __init__(self):
        self._data = { c: dict() for c in CATEGORIES }
        self._defaults = dict()
        self._origin = dict()
        self.sources = []

    def __getitem__(self, category: str) -> dict:
        return self._data[category]

    @property
    def defaults(self) -> dict:
        return self._defaults

    def origin(self, category: str, name: str) -> pathlib.Path:
        return self._origin[(category, name)]

    def merge(self, data: dict, origin: pathlib.Path) -> None:
        self.sources.append(origin)
        for category, entries in data.items():
            if category == DEFAULTS:
                for key, value in entries.items():
                    if value is None:
                        self._defaults.pop(key, None)
                    else:
                        self._defaults[key] = value
                continue
            target = self._data[category]
            for name, tags in entries.items():
                if tags is None:
                    target.pop(name, None)
                    self._origin.pop((category, name), None)
                else:
                    target[name] = tags
                    self._origin[(category, name)] = origin

    def check_defaults(self) -> None:
        for category, name in self._defaults.items():
            if name not in self._data[category]:
                raise SettingsError(f"defaults: {category} '{name}' is not defined")

    def check(self) -> list[str]:
        """ return a list of problems that don't prevent loading """
        problems = []
        for category in CATEGORIES:
            for name, tags in self._data[category].items():
                where = f"{self._origin[(category, name)]}: {category} '{name}'"
                for tag in tags:
                    m = RE_TAG.fullmatch(tag)
                    if m is None:
                        problems.append(f"{where}: '{tag}' isn't of the form Group:Tag")
                    elif m.group(1) not in KNOWN_GROUPS:
                        problems.append(f"{where}: '{tag}': unexpected group '{m.group(1)}'")
                if category == "author":
                    for required in ("XMP:Creator", "XMP:Rights"):
                        if required not in tags:
                            problems.append(f"{where}: must set {required}")
        return problems

def load_settings(
        builtin: pathlib.Path | None,
        user_dir: pathlib.Path | None
        ) -> Settings:
    """
    Load the built-in settings file (if any), then the user's settings
    files (if any).
    """
    result = Settings()
    paths = []
    if builtin is not None:
        paths.append(builtin)
    if user_dir is not None:
        paths.extend(user_settings_files(user_dir))
    for path in paths:
        result.merge(read_settings_file(path), path)
    result.check_defaults()
    return result

#### initializing the user's directory ####

def init_settings(
        settings_dir: pathlib.Path,
        source: pathlib.Path | None,
        templates_dir: pathlib.Path
        ) -> list[pathlib.Path]:
    """
    Create the settings directory, populate templates/ from the packaged
    templates, and if source is given, copy it in as settings.json.
    Nothing is written if any target already exists. Returns the list of
    files created.
    """
    if source is not None:
        # make sure it's usable before we commit to anything
        read_settings_file(source)

    copies = [ (t, settings_dir / "templates" / t.name)
               for t in sorted(templates_dir.glob("*.json")) ]
    if len(copies) == 0:
        raise SettingsError(f"no templates found in {templates_dir}")
    if source is not None:
        copies.append((source, settings_dir / "settings.json"))

    existing = [ str(dest) for _, dest in copies if dest.exists() ]
    if existing:
        raise SettingsError(
            "won't overwrite existing file(s): " + ", ".join(existing)
            )

    result = []
    for src, dest in copies:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        result.append(dest)
    return result
