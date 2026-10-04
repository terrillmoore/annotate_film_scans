# Annotate Film Scans

`annotate_film_scans` is used for batch annotation of collections of JPEG, TFF, PSD, etc. files created by commercial scanning of rolls of film.

<!-- TOC depthFrom:2 updateOnSave:true -->

- [Introduction](#introduction)
- [Prerequisite](#prerequisite)
- [Getting Started](#getting-started)
- [Intended Work Flow](#intended-work-flow)
- [Running from a clone](#running-from-a-clone)
- [Using the Program](#using-the-program)
- [Reference](#reference)
    - [Command line options](#command-line-options)
    - [Shot-info file](#shot-info-file)
- [Settings](#settings)
    - [Where settings live](#where-settings-live)
    - [Setting up your settings](#setting-up-your-settings)
    - [Settings file format](#settings-file-format)
- [Building a release](#building-a-release)
- [Notes on EXIF tags and AnalogExif](#notes-on-exif-tags-and-analogexif)
- [Meta](#meta)
    - [Git repo (for code and issues)](#git-repo-for-code-and-issues)
    - [Author](#author)
    - [Status](#status)
    - [Future Directions](#future-directions)
    - [Prerequisites](#prerequisites)
    - [License](#license)

<!-- /TOC -->

## Introduction

I keep notes (more or less carefully) about exposure, lens used, filters, etc. I use Lightroom, and I'd like the import function to put the images into my image library so that they coherently with the images that originate with my DSLRs or phone. Lightroom is time sensitive. The capture time in the image must be the time of *capture*, not the time of *scan*. To further complicate things, scanning services sometimes return JPEGs with file names that are sequenced in forward order, sometimes in reverse. (When scanning sheet film, filename order is generally scrambled, compared to the order that they were shot.)  In addition, I'd like the shot information (exposure, etc.) to be put into the image files at the same time that I set the date and time.

I tried various manual approaches, but it was too tedious and error prone (and I don't have enough time to deal with the error-prone part, nor for waiting for mouse clicks).

So I wrote `annotate_film_scans`, which can do all of these things. I confess that I did quite a bit of reverse engineering of existing tools, particularly AnalogExif, to find out how things were being tagged. I did not do deep research into the standards; I did just enough work to get something that works for me. It may work for you, but it's current state I anticipate that some aspects of my workflow are hard coded and may need further abstraction.

Your cameras, lenses, author name, and so forth go in your own [settings](#settings) directory; the program only has general-purpose entries (common films, commercial labs, standard processes and developers) built in.

## Prerequisite

You'll need:

- Python 3.13 or later, and [`uv`](https://docs.astral.sh/uv/) (which can install Python for you).
- `exiftool`, installed separately and on your `PATH`:

  | System | Command
  |--------|--------
  | macOS | `brew install exiftool`, or the `.pkg` installer from [exiftool.org](https://exiftool.org/install.html)
  | Debian, Ubuntu | `sudo apt install libimage-exiftool-perl` (distribution versions can lag well behind; check `exiftool -ver`)
  | Windows | `scoop install exiftool`, or the Windows executable from [exiftool.org](https://exiftool.org/install.html) (rename `exiftool(-k).exe` to `exiftool.exe` and put it, with its `exiftool_files` folder, on your `PATH`)

annotate-film-scans passes its own exiftool configuration file (defining the AnalogExif and AnnotateFilmScans XMP namespaces) to exiftool with `-config`. As a result, a personal `~/.ExifTool_config` is not loaded when annotate-film-scans runs exiftool.

## Getting Started

1. **Install exiftool** (see [Prerequisite](#prerequisite)).

2. **Install annotate-film-scans** from the wheel attached to the [latest release](https://github.com/terrillmoore/annotate_film_scans/releases/latest):

   ```bash
   uv tool install annotate_film_scans-<version>-py3-none-any.whl
   annotate-film-scans --version
   ```

   (To run from a clone instead, see [Running from a clone](#running-from-a-clone).)

3. **Set up your settings.** Create the settings directory and its templates:

   ```bash
   annotate-film-scans --init-settings
   ```

   It prints where the directory is (`~/.config/annotate-film-scans` on macOS and Linux). Copy `templates/author.json` and `templates/camera.json` up one level, into the settings directory itself, and edit them: put your name in the author entry (and in `defaults.author`), and describe your camera. Add `lens.json` (and others) the same way if you need them. Then check the result:

   ```bash
   annotate-film-scans --check-settings
   ```

   See [Settings](#settings) for details.

4. **Write a shot-info file** next to your scans, say `shots.csv`. One row per frame (or range of frames); blank cells repeat the value from the row above. The header lines between `--` set values for the whole roll:

   ```csv
   --
   Camera: Example 35mm SLR
   Film: Tri-X 400
   --
   Frame, Exposure, Aperture, Date,       Time
   1,     1/125,    f/8,      2026-09-24, 09:49-04:00
   2,     1/60,     f/5.6
   3,     1/250,    f/11
   ```

   Frames 2 and 3 get capture times 30 seconds apart after frame 1 (`--time-delta` or `TimeDelta:` changes the interval). The names after `Camera:` and `Film:` are entries from your settings; `--check-settings` lists them. See [Shot-info file](#shot-info-file) for all the columns.

5. **Check the order of your scans.** By default the program assumes the scan files are in the reverse of shooting order (the last file is frame 1), which is how many labs deliver them. If your files are in shooting order, add `Forward: true` to the header, or use `--forward`.

6. **Do a dry run**, which checks everything without writing:

   ```bash
   mkdir -p /tmp/tagged
   annotate-film-scans -n -vv -d /tmp/tagged -s shots.csv *.jpg
   ```

7. **Run it for real**, and look at the result:

   ```bash
   annotate-film-scans -d /tmp/tagged -s shots.csv *.jpg
   exiftool -s -Make -Model -DateTimeOriginal -ExposureTime -FNumber -Film /tmp/tagged/*.jpg
   ```

   Output files are named `NNN-{original name}`, where `NNN` is the frame number. The originals aren't changed.

8. **Import** the output directory into Lightroom (or move it next to the scans first).

## Intended Work Flow

1. Get your JPEGs from a given roll of film into a single directory.
2. List the directory and sort by name.
3. Look at the shots with a previewer, and determine whether the order matches the order of exposure on the film or is reversed. My providers generally reverse rolls.
4. Note whether there are any skipped negatives. For example, on one of my cameras, shot 1 is almost always skipped, because the film window is in the wrong place for modern film. My notes start with 2, and I don't want to have to worry about this; so there's a way to skip 1 (or any other shot index on a roll).
5. Create a .csv file in the same directory that describes each shot. The .csv file describes at least shot per line. In the common case (for me) where several sequential shots are the same, there's an easy way to annotate this.  See the sample files below for examples of how to do this.
6. Create a temporary directory for the output results. On macOS, I use the following command:

   ```bash
   mkdir /tmp/tagged
   ```

   This makes a directory for the "tagged" results.
7. Use the program, possibly several times.
8. Move the tagged JPEGs to their final home.

## Running from a clone

With [`uv`](https://docs.astral.sh/uv/), there's nothing to set up; from the top of the repository:

```bash
uv run annotate-film-scans {args}
```

`uv run` creates the virtual environment on first use. `make test` runs the tests, and `make build` builds the wheel in `dist`.

## Using the Program

Let's say that we have a roll of film that came back from the lab with folder name `00046736`, containing a number of JPEGs. And assume that this folder is in a Dropbox folder. This roll was taken on a Minolta Autocord, using Kodak Portra 800 film, so I name the `.csv` file `shots-minolta-portra800.csv`. (`Autocord` is a camera entry in my own settings; use the names from yours.) As you'll see, I organize the Dropbox folder by lab and date, so the full path is `~/Library/CloudStorage/Dropbox/Photos/Scans/TheDarkroom/2023-06-16/00046736/shots-minolta-portra800.csv`.

In this case, the `.csv` file looked like this:

```csv
--
Forward: true
--
Frame,  Frame2, Exposure,       Aperture,       Filter, Date,           Time,                   Camera,         Lens,           Film,           Lab,            Process
1,      ,       1/100,          f/11,           -,      2023-06-02,     10:00:00-04:00,         Autocord,       ,               Portra 800,     The Darkroom,   C-41
2,      ,       1/50,           f/11,           -
3,      ,       1/200,          f/8,            Proxar 2, 2023-06-03,   18:10:00-04:00
4,      6,      1/200,          f/16,           Proxar 2
7,      ,       1/200,          f/11,           Proxar 2
8,      ,       1/200,          f/8,            Proxar 2
9,      10,     1/400,          f/22,           UV,     2023-06-04,     10:25:00-04:00
11,     ,       skip
12,     ,     1/400,          f/22,           UV,     ,               10:40:00-04:00
```

|Frame|Frame2|Exposure|Aperture|Filter|Date|Time|Camera|Lens|Film|Lab|Process|
|-----|------|--------|--------|------|----|----|------|----|----|---|-------|
1|      |       1/100|          f/11|           -|      2023-06-02|     10:00:00-04:00|         Autocord|       |               Portra 800|     The Darkroom|   C-41
2|      |       1/50|           f/11|           -
3|      |       1/200|          f/8|            Proxar 2| 2023-06-03|   18:10:00-04:00
4|      6|      1/200|          f/16|           Proxar 2
7|      |       1/200|          f/11|           Proxar 2
8|      |       1/200|          f/8|            Proxar 2
9|      10|     1/400|          f/22|           UV|     2023-06-04|     10:25:00-04:00
11|     |     skip
12|     |     1/400|          f/22|           UV|     |               10:40:00-04:00

Some things to observe.  I only need to state the camera, film, lab, and process on the first line; the tool keeps these the same unless you change them in a subequent line.

Also, I only need to state the date and time on the first shot in a series. Later shots without a time are placed after the previous shot, 30 seconds apart by default (set with `--time-delta` or `TimeDelta:` in the header), so they sort in shooting order.

The filter uses a special notation, `-`, to designate a shot with no filter. Otherwise (if left blank) the attributes of the previous shot apply.

Shots 4-6, and 9-10 are explicitly coded as identical.

Shot 11 is skipped, meaning that there's no JPEG.  The program counts through the JPEGs and names each output file after its frame number: `001-`..., `002-`..., and so on. It never skips a JPEG, but it does skip frame numbers.

In this case, the scan was in forward order -- probably because the Minolta arranges the 6x6 images upside down compared to a Rollei or Yashica TLR. I hypothesize that labs always try to get the images in a certain orientation and sequence when scanning.  The tool doesn't know this, so I tell it using the `--forward` switch.

Once the file is ready, do a dry run as follows:

```bash
annotate-film-scans -d /tmp/tagged --shot-info-file ~/Library/CloudStorage/Dropbox/Photos/Scans/TheDarkroom/2023-06-16/00046736/shots-minolta-portra800.csv ~/Library/CloudStorage/Dropbox/Photos/Scans/TheDarkroom/2023-06-16/00046736/*.jpg -vv --dry-run
```

(From a clone, use `uv run annotate-film-scans` instead of `annotate-film-scans`.)

I start by saying `--dry-run`; that way the program will run quickly and find any errors in the `.csv` file. I use `-vv` (or even `-vvv`), which allows me to review what the program is going to do.

After I'm satisifed, I run the program again, without `--dry-run`:

```bash
annotate-film-scans -d /tmp/tagged --shot-info-file ~/Library/CloudStorage/Dropbox/Photos/Scans/TheDarkroom/2023-06-16/00046736/shots-minolta-portra800.csv ~/Library/CloudStorage/Dropbox/Photos/Scans/TheDarkroom/2023-06-16/00046736/*.jpg -vv
```

Then I move the `/tmp/tagged` directory (and the converted files) to Dropbox as a subdirectory of the scan directory. I do this so I know for sure that I've processed these files.

Finally, I import the `tagged` directory into Lightroom.

## Reference

### Command line options

```
usage: annotate_film_scans [-h] [--verbose] [--settings-dir {dir}] [--builtin-settings {file} | --no-builtin-settings]
                           [--no-user-settings] [--init-settings [{file}]] [--check-settings] [--version]
                           [--dir DIR] [--forward] [--camera {...}] [--lens {...}] [--film {...}] [--lab {...}]
                           [--process {...}] [--author {...}] [--roll ROLL] [--time-delta {time-delta}]
                           [--shot-info-file {shot-info-csv}] [--date {date-iso-8601}] [--dry-run]
                           [--developer {developer_name}] [--development_time {devtime}]
                           [--development_temperature {devtemp}] [--development_notes {notes}]
                           {InputFile} [{InputFile} ...]
```

The choices for `--camera`, `--lens`, `--film`, `--lab`, `--process`, and `--author` are the entries in your settings; `annotate-film-scans --check-settings` lists them. Defaults come from the `defaults` section of the settings.

Annotate film scans, coping and numbering appropriately

Positional arguments:

| Name                | Description
|---------------------|------------
|  `{InputFile}`        | Name of input file. Multiple input files may be specified. File

Options:

| Option                | Description
|-----------------------|------------
|  `-h`, `--help`       | show this help message and exit
|  `--verbose`, <br/>`-v` |        increase verbosity, once for each use
|  `--settings-dir` _{dir}_ | directory holding your settings files (default: see [Where settings live](#where-settings-live))
|  `--builtin-settings` _{file}_ | use this file instead of the built-in settings (for testing)
|  `--no-builtin-settings` | don't load the built-in settings
|  `--no-user-settings` | don't load the settings directory
|  `--init-settings` [_{file}_] | create the settings directory with editable templates, and if _{file}_ is given, copy it in as `settings.json`; then exit
|  `--check-settings`   | load and check all settings, list each entry and where it came from, then exit
|  `--version`          |   Print version and exit
|  `--dir` _DIR_,<br/>`-d` _DIR_ |     where to put data files (default: `tmp`)
|  <code>&#8209;&#8209;forward</code>, `-f`      |  number files in ascending order, rather than reversing; many scans are in reverse order compared to the film
|  `--camera` _CAMERA_  | camera that took image(s): a `camera` entry from your settings
| `--lens` _LENS_       | lens used for image: a `lens` entry from your settings (built-in default: `fixed`)
| `--film` _FILM_       | film used for image: a `film` entry from your settings
| `--lab` _LAB_         | lab used for processing image: a `lab` entry from your settings
| `--process` _PROCESS_   | process used for image: a `process` entry from your settings
| `--author` _NAME_     | author/rights for image: an `author` entry from your settings. With no author, no creator or copyright is written.
| `--roll` _ROLL_       | Roll ID
| <code>&#8209;&#8209;time&#8209;delta</code>&nbsp;_{time&#8209;delta}_,<br/>`-T` _{time-delta}_ | Assumed interval between shots in frame sequences (in seconds) (default 30)
| <code>&#8209;&#8209;shot&#8209;info&#8209;file</code>&nbsp;_{shot&#8209;info&#8209;csv}_,<br/>`-s` _{shot-info-csv}_ | name of per-shot info file as a `.csv` or `.txt` file. The first row is a header defining the fields. The file may begin with file-wide settings using a YAML-like prefix delimited by lines consisting solely of "<code>&#8209;&#8209;</code>".
| `--date` _{date-iso-8601}_ | base capture date/time for all images in this run; can be overridden on a shot-by-shot bases in the shot info file
| `--dry-run`, `-n`     | go through the motions, but don't write files

### Shot-info file

The shot-info file is a CSV file (tabs are treated as spaces, and spaces after commas are ignored). It may begin with header options, then has a line of column names, then one row per frame or range of frames.

#### Header options

If the first line is `--`, the lines up to the next `--` are options for the whole roll, one `Name: value` per line (names are case-insensitive). They override the corresponding command-line options.

| Option | Meaning
|--------|--------
| `Forward` | `true` if the scan files are in shooting order (same as `--forward`)
| `Roll` | roll ID
| `TimeDelta` | seconds between shots when times are filled in automatically (same as `--time-delta`)
| `Camera`, `Lens`, `Film`, `Lab`, `Process`, `Developer` | initial entry from your settings
| `DevTime`, `DevTemp`, `DevNotes` | initial development time, temperature, notes

#### Columns

Column names are case-insensitive, may appear in any order, and all but `Frame` are optional. A blank cell takes the value from the row above (except `Comment`, `Frame2`, and `File`).

| Column | Meaning
|--------|--------
| `Frame` | frame number
| `Frame2` | last frame of a range of identical frames (`Frame`..`Frame2`). If `Frame2` is less than `Frame`, the frames were shot in descending order; times still move forward.
| `Exposure` | shutter speed, e.g. `1/125`, `2`, or `0.5`; `skip` means there's no scan for this frame (or range); `-` clears it
| `Aperture` | e.g. `f/8`; `-` clears it
| `Filter` | filter description; `-` means no filter
| `Date` | capture date, `YYYY-MM-DD`; needs `Time` in the same row
| `Time` | capture time, `HH:MM[:SS]` with optional offset (`-04:00` or `-0400`). The first time needs an offset (or one from `--date`); later times without one keep the previous offset. A time without a date keeps the previous date.
| `Camera`, `Lens`, `Film`, `Lab`, `Process`, `Developer` | entry names from your settings. Changing the camera clears the lens; changing the lens clears the focal length.
| `FocalLength` | focal length in mm, for zooms or lenses without one in the settings; the 35mm equivalent uses the camera's or lens's `CropFactor`
| `Roll` | roll ID; `-` clears it
| `Comment` | note for this frame only; `-` repeats the previous row's comment
| `File` | which scan file this row starts with (1 = first file, in the order the program uses); later rows continue from there
| `DevTime` | development time in minutes, `M` or `M:SS`; `?` if not recorded
| `DevTemp` | development temperature in degrees C, e.g. `20.4`; `?` if not recorded
| `DevNotes` | development notes

Rows without a `Time` are given the time of the previous row's last frame plus the time delta. Skipped frames take up time the same way, so times stay the same whether or not you scan every frame. If no row has a time, `--date` gives the base date and time.

Scan files are assigned to frames in order, skipping `skip` frames. Unless `--forward` (or `Forward: true`) is given, the files named on the command line are used in reverse order.

## Settings

Cameras, lenses, films, labs, processes, developers, and authors are named entries in the settings, each giving the EXIF/XMP tags to write when that entry is used. The program loads its built-in settings, then every `*.json` file at the top level of your settings directory, in sorted order.

### Where settings live

| System | Settings directory
|--------|-------------------
| Linux, macOS | `$XDG_CONFIG_HOME/annotate-film-scans`, or `~/.config/annotate-film-scans` if `XDG_CONFIG_HOME` isn't set
| Windows | `%APPDATA%\annotate-film-scans`

Set `ANNOTATE_FILM_SCANS_CONFIG` to use a different directory, or use `--settings-dir` for a single run. The settings directory can be a git repository (or a symlink to one), so you can keep your settings under version control and share them between machines.

### Setting up your settings

```bash
annotate-film-scans --init-settings
```

creates the settings directory and a `templates` subdirectory with one example file per category. Files in `templates` are never loaded: copy the ones you need up a level (or merge them into a single `settings.json`), replace the example entries with your own, and then run

```bash
annotate-film-scans --check-settings
```

to see every entry, which file it came from, and any problems. If you already have a settings file, `annotate-film-scans --init-settings myfile.json` also copies it in as `settings.json`. `--init-settings` never overwrites existing files.

### Settings file format

Each file is a JSON object whose keys are categories (`camera`, `lens`, `film`, `lab`, `process`, `developer`, `author`) and an optional `defaults`:

```json
{
    "camera": {
        "My F-1": {
            "IFD0:Make": "Canon",
            "IFD0:Model": "F-1",
            "XMP-AnalogExif:FilmType": "135",
            "XMP:CameraSerialNumber": "123456"
        }
    },
    "author": {
        "Me": {
            "XMP:Creator": "My Name",
            "XMP:Rights": "All rights reserved"
        }
    },
    "defaults": {
        "author": "Me"
    }
}
```

- Tag names use exiftool's `Group:Tag` notation.
- An entry with the same name as an earlier one (built-in or from an earlier file) replaces it entirely.
- An entry whose value is `null` removes the earlier entry of that name; likewise for a default.
- `defaults` names the entry to use for a category when it isn't given on the command line or in the shot-info file.
- Keys starting with `_` are comments, at any level.
- `author` entries must set `XMP:Creator` and `XMP:Rights`.

## Building a release

Use the `Makefile`:

```bash
make build
```

The distribution files show up in the `dist` subdirectory at the top of the repository.

## Notes on EXIF tags and AnalogExif

This section is very brief jotted notes from looking at source code.

The schema used by AnalogExif is described at https://analogexif.sourceforge.net/help/analogexif-xmp.php; its namespace is `http://analogexif.sourceforge.net/ns/`.

Information that AnalogExif doesn't cover goes in the `AnnotateFilmScans` namespace, `https://github.com/terrillmoore/annotate_film_scans/ns/1.0/`, described by [`schema/AnnotateFilmScans.rdf`](schema/AnnotateFilmScans.rdf).

exiftool doesn't know either namespace by itself; the program passes it `annotate_film_scans/exiftool.config` with `-config`.

Special tags:

| Name                   | Comment
|------------------------|---------------
|`XMP:CameraSerialNumber` | Also copied to `EXIF:CameraSerialNumber`
|`EXIF:FNumber`           | Also copied to `Composite:Aperture`?
|`EXIF:ExposureTime`      | Also copied to `Composite:ShutterSpeed`?

## Meta

### Git repo (for code and issues)

https://github.com/terrillmoore/annotate-film-scans/

### Author

Terry Moore

### Status

2025-01-18: This tool is still a work in progress. It works well enough to be useful to others, especially for someone with a functional understanding of Python.

### Future Directions

* Guess the location of the JPEGs from the location of the shot info file.
* Add keywording and subject input, especially if we can validate.
* Add json equivalent to the `.csv` input, so we can use JSON Schemas to pre-validate input in VS Code.
* Add an option to generate a template for the CSV file.

### Prerequisites

V3.0.0 was tested on macOS 26.5.2 arm64 (as reported by `sw_vers`) with Python 3.14.2 (under `uv`) and `exiftool` 13.55 (as reported by `exiftool -ver`).

V3 has not been run end to end on Linux or Windows. The settings-directory logic for those systems is covered by unit tests (`make test`) only.

### License

Released under MIT license.
