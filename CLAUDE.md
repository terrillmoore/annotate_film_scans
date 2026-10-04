# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

annotate-film-scans is a CLI tool that batch-annotates film scan images (JPEG, TIFF, PSD, etc.) with EXIF/XMP metadata -- capture date/time, camera, lens, film, exposure, development info, and more. It reads a CSV "shot info" file describing each frame's metadata, then uses `exiftool` to write tags and copy files to an output directory with sequential numbering.

## Build and Run

Requires Python >= 3.13, `uv`, and `exiftool` (installed separately via Homebrew/apt/scoop).

```bash
make test        # run the tests (uv run pytest)
make build       # build distribution in dist/
make clean       # remove .venv, egg-info, __pycache__, .pytest_cache
make distclean   # clean + remove dist/
```

Run directly:
```bash
uv run annotate-film-scans [options] input_files...
```

The Makefile needs GNU make >= 4.4.1 (`gmake` on macOS).

## Tests

pytest, in `tests/`. Write tests first (red/green).

- **test_settings.py** -- the settings module: directory lookup per platform, merge, defaults, check, init, and that the packaged settings and templates are valid.
- **test_app_settings.py** -- the settings command-line options, via `App(argv)`.
- **test_shotinfo.py** -- CSV parsing and time propagation, via a real `App` and `ShotInfoFile.read_from_path()`.
- **test_app_run.py** -- end to end: runs the app on a 1x1 JPEG and reads the tags back with exiftool. Skipped if exiftool isn't on `PATH`.

Tests isolate themselves from the real user settings by setting `ANNOTATE_FILM_SCANS_CONFIG` to a temp directory (pytest `monkeypatch`). `App()` takes an optional `argv` list for this.

Unit tests aren't enough for changes to `_copy()` or tag handling; also run a real roll (dry run, then real run to a scratch directory) and check the output with `exiftool -config annotate_film_scans/exiftool.config`. Without `-config`, exiftool won't show the custom XMP namespaces.

## Architecture

Source modules in `annotate_film_scans/`:

- **app.py** -- `App` class: argument parsing, settings loading, orchestration. Calls `exiftool` via `subprocess.run()` to read scanner make/model and to write metadata + copy files. `__main__.main()` creates `App()` and calls `App.run()`, which dispatches to annotate, `--init-settings`, or `--check-settings`. Settings options are parsed by a pre-parser first, because the settings supply the choices and defaults for the main parser.
- **shotinfo.py** -- `ShotInfoFile` class: parses CSV files with an optional YAML-like header (delimited by `--`) for file-wide options. Handles property inheritance across rows, frame range expansion (`frame`/`frame2`), time propagation via timedelta, and conversion of shot info fields to EXIF/XMP tag dictionaries (`_expand_attrs()`).
- **settings.py** -- loads the built-in `settings.json`, then `*.json` from the user's settings directory (`$ANNOTATE_FILM_SCANS_CONFIG`; `%APPDATA%\annotate-film-scans` on Windows; `$XDG_CONFIG_HOME` or `~/.config/annotate-film-scans` elsewhere), merging per entry (`null` deletes, `_` keys are comments, `defaults` section). Also `--check-settings` validation and `--init-settings` (copies `templates/`).
- **constants.py** -- Immutable `Constants` class (uses `__slots__`). Defines shot field names, regex patterns for f-stop/exposure/time/temperature validation, and XMP tag name constants for custom namespaces (XMP-AnalogExif, XMP-AnnotateFilmScans).

**settings.json** holds the built-in, general-purpose entries (films, commercial labs, C-41/E-6/B&W, developers, the `fixed` lens); personal cameras, lenses, author etc. belong in the user's settings directory. **templates/** holds one example file per category for `--init-settings`. **exiftool.config** defines the XMP-AnalogExif and XMP-AnnotateFilmScans namespaces and is passed to every exiftool call with `-config`; `schema/AnnotateFilmScans.rdf` documents our namespace.

## Key Conventions

- Version is defined solely in `pyproject.toml`; `__version__.py` reads it via `importlib.metadata`.
- Each source file has a header comment block with filename, function summary, copyright reference (MIT, Terrill Moore -- see LICENSE.md), and author.
- EXIF/XMP tags use exiftool's group:tag notation: `EXIF:`, `ExifIFD:`, `IFD0:`, `XMP-aux:`, `XMP-dc:`, `XMP-AnalogExif:`, `XMP-AnnotateFilmScans:`, `Composite:`, `System:`.
- CSV shot info: blank cells inherit from the row above; `-` clears Aperture/Exposure/Filter/Roll and repeats the previous Comment (it is not valid for settings-entry columns); `skip` in Exposure skips a frame (it still takes up time); `Frame2 < Frame` is a descending range (frames in that order, time moving forward). All columns but Frame are optional. Header (`--`) options override the command line. The README's "Shot-info file" section is the reference; keep it in sync.
- Output files are named `NNN-{original_name}`, where NNN is the frame number.
- `--forward` controls whether input file order is preserved or reversed (default: reversed, matching how many labs scan negatives).
- Dates: `ExifIFD:DateTimeOriginal`/`CreateDate` and the XMP capture dates (`XMP-photoshop:DateCreated`, `XMP-exif:DateTimeOriginal`) are the time the photo was taken. `ExifIFD:CreateDate` must stay the capture time, because some Adobe tool relies on it. `XMP-exif:DateTimeDigitized` is the scan time.
- Raw files (RW2, ARW, Sony DNG): never change IFD0 Make/Model, because vendor maker notes depend on them. The film camera goes in `XMP-AnnotateFilmScans:Make`/`Model` instead.
- Pass everything to exiftool as JSON on stdin (`-json=-`) with no other tag arguments: since exiftool 13.41, tag arguments next to `-json=` restrict the import. Every exiftool call goes through `App._exiftool()`, which puts `-config` first.
- New XMP-AnnotateFilmScans tags must be added to `exiftool.config` (or exiftool silently drops them) and documented in `schema/AnnotateFilmScans.rdf`. Prefer an existing AnalogExif tag when there is one.
- The "Photo information" free-text comment (`XPComment`/`UserComment`) repeats the metadata where no tool can misinterpret it; keep it.

## Releasing

1. Bump `version` in `pyproject.toml`, run `uv lock`, and commit as "This is version vX.Y.Z".
2. Annotated tag `vX.Y.Z`, with a message like "YYYY-MM-DD: vX.Y.Z: summary".
3. `uv build --wheel`, install the wheel into a scratch venv and smoke-test it (`--version`, `--check-settings`), and check that its `settings.json` has no personal entries.
4. `gh release create vX.Y.Z <wheel> --verify-tag`, with notes grouped as breaking changes, fixes, new, and known issues.

Betas are `X.Y.ZbN` (uv won't accept `-preN`).
