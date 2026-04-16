# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

annotate-film-scans is a CLI tool that batch-annotates film scan images (JPEG, TIFF, PSD, etc.) with EXIF/XMP metadata -- capture date/time, camera, lens, film, exposure, development info, and more. It reads a CSV "shot info" file describing each frame's metadata, then uses `exiftool` to write tags and copy files to an output directory with sequential numbering.

## Build and Run

Requires Python >= 3.13, `uv`, and `exiftool` (installed separately via Homebrew/apt/scoop).

```bash
make venv        # create .venv
make build       # build distribution in dist/
make clean       # remove .venv, egg-info, __pycache__
make distclean   # clean + remove dist/
```

Run directly:
```bash
uv run annotate-film-scans [options] input_files...
```

There is no test suite.

## Architecture

Three source modules in `annotate_film_scans/`:

- **app.py** -- `App` class: argument parsing, settings loading, orchestration. Calls `exiftool` via `subprocess.run()` to read scanner make/model and to write metadata + copy files. Entry point is `App.main()` called from `__main__.py`.
- **shotinfo.py** -- `ShotInfoFile` class: parses CSV files with an optional YAML-like header (delimited by `--`) for file-wide options. Handles property inheritance across rows, frame range expansion (`frame`/`frame2`), time propagation via timedelta, and conversion of shot info fields to EXIF/XMP tag dictionaries (`_expand_attrs()`).
- **constants.py** -- Immutable `Constants` class (uses `__slots__`). Defines shot field names, regex patterns for f-stop/exposure/time/temperature validation, and XMP tag name constants for custom namespaces (XMP-AnalogExif, XMP-AnnotateFilmScans).

**settings.json** holds all known cameras, lenses, films, labs, processes, developers, and authors as dictionaries mapping names to their EXIF/XMP tag values. CLI `--camera`, `--lens`, etc. select entries by name from this file.

## Key Conventions

- Version is defined solely in `pyproject.toml`; `__version__.py` reads it via `importlib.metadata`.
- Each source file has a header comment block with filename, function summary, copyright reference (MIT, Terrill Moore -- see LICENSE.md), and author.
- EXIF/XMP tags use exiftool's group:tag notation: `EXIF:`, `ExifIFD:`, `IFD0:`, `XMP-aux:`, `XMP-dc:`, `XMP-AnalogExif:`, `XMP-AnnotateFilmScans:`, `Composite:`, `System:`.
- CSV shot info supports `-` to cancel/reset a property and `skip` in the exposure field to skip a frame.
- Output files are numbered `NNN-{original_name}` where NNN is the sequential frame index.
- `--forward` controls whether input file order is preserved or reversed (default: reversed, matching how many labs scan negatives).
