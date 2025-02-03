# Annotate Film Scans

`annotate_film_scans` is used for batch annotation of collections of JPEG, TFF, PSD, etc. files created by commercial scanning of rolls of film.

<!-- TOC depthFrom:2 updateOnSave:true -->

- [Introduction](#introduction)
- [Prerequisite](#prerequisite)
- [Intended Work Flow](#intended-work-flow)
- [Setting up a virtual environment](#setting-up-a-virtual-environment)
- [Using the Program](#using-the-program)
- [Reference](#reference)
    - [Command line options](#command-line-options)
- [Things you'll want to change before using the program](#things-youll-want-to-change-before-using-the-program)
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

One thing you'll definitely need to edit (and that I should refactor) is `settings.json`.  This file is incorporated into the program, effectively, if you [build a release](#building-a-release), so it is really a botch -- releases are not a good idea as there's no way to override settings with a local file.

## Prerequisite

You'll need to have `exiftool` installed on your system. On Linux, `apt-get install exiftool` will work; on macOS, you can use Brew. On Windows, you may need to resort to google search to find a suitable `.exe`. I believe that `scoop.sh` includes a version in its library. (Happy to accept contributions clarifying this.)

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

## Setting up a virtual environment

The best way to setup to run the tool (if you've not installed from a `.whl`) is to use the `Makefile`:

```bash
make clean # <== get rid of any old .venv stuf
make venv # <== create the venv
```

`make venv` will print out the command you need to use to activate the virtual envirnment; the command differs base on your operating system.

Run that command in a shell/terminal window to get a suitably set up environment.

## Using the Program

Let's say that we have a roll of film that came back from the lab with folder name `00046736`, containing a number of JPEGs. And assume that this folder is in a Dropbox folder. This roll was taken on a Minolta Autocord, using Kodak Portra 800 film, so I name the `.csv` file `shots-minolta-portra800.csv`. As you'll see, I organize the Dropbox folder by lab and date, so the full path is `~/Library/CloudStorage/Dropbox/Photos/Scans/TheDarkroom/2023-06-16/00046736/shots-minolta-portra800.csv`.

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

Also, I only need to state the date and time on first shot in a series; the dates and times are carried forward. (This means that the shots are all tagged with the same time, but that doesn't bother me.)

The filter uses a special notation, `-`, to designate a shot with no filter. Otherwise (if left blank) the attributes of the previous shot apply.

Shots 4-6, and 9-10 are explicitly coded as identical.

Shot 11 is skipped, meaning that there's no JPEG.  The program counts through JPEGs and names the output JPEGs `01_`..., `02_`..., etc; it doesn't ever skip JPEGs, but it will skip sequence numbers.

In this case, the scan was in forward order -- probably because the Minolta arranges the 6x6 images upside down compared to a Rollei or Yashica TLR. I hypothesize that labs always try to get the images in a certain orientation and sequence when scanning.  The tool doesn't know this, so I tell it using the `--forward` switch.

Once the file is ready, do a dry run as follows:

```bash
python -m annotate_film_scans -d /tmp/tagged --shot-info-file ~/Library/CloudStorage/Dropbox/Photos/Scans/TheDarkroom/2023-06-16/00046736/shots-minolta-portra800.csv ~/Library/CloudStorage/Dropbox/Photos/Scans/TheDarkroom/2023-06-16/00046736/*.jpg -vv --dry-run
```

Notes:
1. If you've installed the script from the `.whl` distribution, you can just run `annotate_film_scans`.
2. If you're running a virtual environment, **always** use `python` rather than `python3`; otherwise you may get the wrong interpreter and strange results.

I start by saying `--dry-run`; that way the program will run quickly and find any errors in the `.csv` file. I use `-vv` (or even `-vvv`), which allows me to review what the program is going to do.

After I'm satisifed, I run the program again, without `--dry-run`:

```bash
python3 -m annotate_film_scans -d /tmp/tagged --shot-info-file ~/Library/CloudStorage/Dropbox/Photos/Scans/TheDarkroom/2023-06-16/00046736/shots-minolta-portra800.csv ~/Library/CloudStorage/Dropbox/Photos/Scans/TheDarkroom/2023-06-16/00046736/*.jpg -vv
```

Then I move the `/tmp/tagged` directory (and the converted files) to Dropbox as a subdirectory of the scan directory. I do this so I know for sure that I've processed these files.

Finally, I import the `tagged` directory into Lightroom.

## Reference

### Command line options

```
usage: annotate_film_scans [-h] [--verbose] [--version] [--dir DIR] [--forward] [--camera {Autocord,Canonflex,Canon FTb,Canon FTbQL-N,Baldalux,Leotax,Leotax #1,Leotax #2,Pentax ME Super (Judy),Pocket View 6x9,Pocket View,Crown Graphic,Calumet CC-400,Gowland 8x10}]
                           [--lens {fixed,R 50mm f/1.8 #30119,R 50mm f/1.8,R 58mm f/1.2,R 35mm f/2.5,Macro FL 50mm f/3.5,FL 35mm f/2.5,FL 55-135mm f/3.5,FD 50mm f/1.4,FD 300mm f/4,FD 70~150 f/4.5,SMC Pentax 50 mm f/1.7,SMC Pentax 28 mm f/2.8,Caltar II-N 90mm,Caltar II-N 90mm 6x9,135mm Optar,150mm Rodenstock,180mm Rodenstock,270mm Tele-Arton,75mm Fujinon,210mm Fujinon,159mm Wollensak,300mm Fujinon C,300mm Fujinon C on 4x5}]
                           [--film {CineStill 400,Delta 100,Delta 400,Delta 3200,Tri-X 400,Tri-X 320,Portra 160,Portra 800,Portra 800+1,Superia 400,Ektar 100,Kodak Gold 200,Pancro 400,Ektachrome 100,Fomapan 100,Catlabs 100,Rollei Ortho 25,T-Max 100,Arista EDU 400,Portra 400,BWXX,BWXX @ 260,BWXX @ 400}]
                           [--lab {Praus,The Darkroom,Scotts,Head's,Icon,Gowanus}] [--process {C-41,E-6,B&W,B&W - 10%,B&W - 20%,B&W + 10%,B&W + 20%}] [--author {Terrill Moore}] [--roll ROLL] [--time-delta {time-delta}] [--shot-info-file {shot-info-csv}] [--date {date-iso-8601}] [--dry-run]
                           {InputFile} [{InputFile} ...]
```

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
|  `--version`          |   Print version and exit
|  `--dir` _DIR_,<br/>`-d` _DIR_ |     where to put data files (default: `tmp`)
|  <code>&#8209;&#8209;forward</code>, `-f`      |  number files in ascending order, rather than reversing; many scans are in reverse order compared to the film
|  `--camera` _CAMERA_  | camera that took image(s). The posibilities come from `settings.json`, and are currently one of: `Autocord`, `Canonflex`, `Canon FTb`, `Canon FTbQL-N`, `Baldalux`, `Leotax`, `Leotax #1`, `Leotax #2`, `Pentax ME Super (Judy)`, `Pocket View 6x9`, `Pocket View`, `Crown Graphic`, `Calumet CC-400`, `Gowland 8x10`
| `--lens` _LENS_       | lens used for image (default: `fixed`). The posibilities come from `settings.json` and are currently: `fixed`, `R 50mm f/1.8 #30119`, `R 50mm f/1.8`, `R 58mm f/1.2`, `R 35mm f/2.5`, `Macro FL 50mm f/3.5`, `FL 35mm f/2.5`, `FL 55-135mm f/3.5`, `FD 50mm f/1.4`, `FD 300mm f/4`, `FD 70~150 f/4.5`, `SMC Pentax 50 mm f/1.7`, `SMC Pentax 28 mm f/2.8`, `Caltar II-N 90mm`, `Caltar II-N 90mm 6x9`, `135mm Optar`, `150mm Rodenstock`, `180mm Rodenstock`, `270mm Tele-Arton`, `75mm Fujinon`, `210mm Fujinon`, `159mm Wollensak`, `300mm Fujinon C`, `300mm Fujinon C on 4x5`
| `--film` _FILM_       | film used for image. The possibilities come from `settings.json` and are currently: `CineStill 400`, `Delta 100`, `Delta 400`, `Delta 3200`, `Tri-X 400`, `Tri-X 320`, `Portra 160`, `Portra 800`, `Portra 800+1`, `Superia 400`, `Ektar 100`, `Kodak Gold 200`, `Pancro 400`, `Ektachrome 100`, `Fomapan 100`, `Catlabs 100`, `Rollei Ortho 25`, `T-Max 100`, `Arista EDU 400`, `Portra 400`, `BWXX`, `BWXX @ 260`, `BWXX @ 400`
| `--lab` _LAB_         | lab used for processing image. he possibilities come from `settings.json` and are currently: `Praus`, `The Darkroom`, `Scotts`, `Head's`, `Icon`, `Gowanus`
| `--process` _PROCESS_   | process used for image. The possibilities come from `settings.json` and are currently: `C-41`, `E-6`, `B&W`, `B&W - 10%`, `B&W - 20%`, `B&W + 10%`, `B&W + 20%`
| `--author` _NAME_     | author/rights for image (default: `Terrill Moore`)
| `--roll` _ROLL_       | Roll ID
| <code>&#8209;&#8209;time&#8209;delta</code>&nbsp;_{time&#8209;delta}_,<br/>`-T` _{time-delta}_ | Assumed interval between shots in frame sequences (in seconds) (default 30)
| <code>&#8209;&#8209;shot&#8209;info&#8209;file</code>&nbsp;_{shot&#8209;info&#8209;csv}_,<br/>`-s` _{shot-info-csv}_ | name of per-shot info file as a `.csv` or `.txt` file. The first row is a header defining the fields. The file may begin with file-wide settings using a YAML-like prefix delimited by lines consisting solely of "<code>&#8209;&#8209;</code>".
| `--date` _{date-iso-8601}_ | base capture date/time for all images in this run; can be overridden on a shot-by-shot bases in the shot info file
| `--dry-run`, `-n`     | go through the motions, but don't write files

## Things you'll want to change before using the program

The default author of all the scans is set to `Terrill Moore` -- you'll really want to fix this (see future directions). This is is `settings.json`.

The serial number of the camera bodies is set in `settings.json`. Ditto.

You'll need to add the films and labs you use in `settings.json`.

## Building a release

Use the `Makefile`:

```bash
make build
```

The distribution files show up in the `dist` subdirectory at the top of the repository.

## Notes on EXIF tags and AnalogExif

This section is very brief jotted notes from looking at source code.

The schema used by AnalogExif:

http://sites.google.com/site/c41bytes/analogexif/ns

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
* Allow the user to specify the serial numbers of their own lenses and cameras without editing `settings.json`.
* Add keywording and subject input, especially if we can validate.
* Add json equivalent to the `.csv` input, so we can use JSON Schemas to pre-validate input in VS Code.
* Add an option to output the settings in a file you can edit locally.
* Add an option to generate a template for the CSV file.

### Prerequisites

V2.6.1 was tested on macOS 14.6.1 arm64 (as reported by `sw_vers`) with python3 v3.12.4 and `exiftool` version 12.62 (as reported by `exiftool -ver`).

### License

Released under MIT license.
