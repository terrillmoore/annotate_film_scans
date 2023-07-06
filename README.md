# Annotate Film Scans

`annotate_film_scans` is used for batch annotation of collections of JPEG files created by commercial scanning of rolls of film.

I keep notes (more or less carefully) about exposure, lens used, filters, etc. I use Lightroom, and I'd like the import function to put the images into my image library so that they coherently with the images that originate with my DSLRs or phone.  I'd like the imported images to show up in the right sequence within a given batch; however, scanning services sometimes return JPEGs sequenced in forward order, sometimes in reverse.

I tried various manual approaches, but it was too tedious and error prone (and I don't have enough time).

So I wrote `annotate_film_scans`, which can do all of these things. I confess that I did quite a bit of reverse engineering of existing tools, particularly AnalogExif, to find out how things were being tagged. I did not do deep research into the standards; I did just enough work to get something that works for me. It may work for you, but it's current state I anticipate that some aspects of my workflow are hard coded and may need further abstraction.

One thing you'll definitely need to edit (and that I should refactor) is `settings.json`.  This file is incorporated into the program, effectively, if you run 

## Prerequisite

You'll need to have `exiftool` installed on your system. On Linux, `apt-get install exiftool` will work; on macOS, you can use Brew. On Windows, you may need to resort to google search to find a suitable `.exe`. I believe that `scoop.sh` includes a version in its library. (Happy to accept contributions clarifying tis.)

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

## Using the pogram

Let's say that we have a roll of film that came back from the lab with folder name `00046736`, containing a number of JPEGs. And assume that this folder is in a Dropbox folder. This roll was taken on a Minolta Autocord, using Kodak Portra 800 film, so I name the `.csv` file `shots-minolta-portra800.csv`. As you'll see, I organize the Dropbox folder by lab and date, so the full path is `~/Library/CloudStorage/Dropbox/Photos/Scans/TheDarkroom/2023-06-16/00046736/shots-minolta-portra800.csv`.

In this case, the `.csv` file looked like this:

```csv
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

Once the file is ready, do a dry run as follows:

```bash
python3 -m annotate_film_scans -d /tmp/tagged --shot-info-file ~/Library/CloudStorage/Dropbox/Photos/Scans/TheDarkroom/2023-06-16/00046736/shots-minolta-portra800.csv ~/Library/CloudStorage/Dropbox/Photos/Scans/TheDarkroom/2023-06-16/00046736/*.jpg -vv --forward --dry-run 
```

(If you've installed the script from the `.whl` distribution, you can just run `annotate_film_scans`.)

In this case, the scan was in forward order -- probably because the Minolta arranges the 6x6 images upside down compared to a Rollei or Yashica TLR. I hypothesize that labs always try to get the images in a certain orientation and sequence when scanning.  The tool doesn't know this, so I tell it using the `--forward` switch.  I also say `--dry-run`; that way it will run quickly and find any errors in the `.csv` file.

After I'm satisifed, I run the program again, without `--dry-run`:

```bash
python3 -m annotate_film_scans -d /tmp/tagged --shot-info-file ~/Library/CloudStorage/Dropbox/Photos/Scans/TheDarkroom/2023-06-16/00046736/shots-minolta-portra800.csv ~/Library/CloudStorage/Dropbox/Photos/Scans/TheDarkroom/2023-06-16/00046736/*.jpg -vv --forward
```

Then I move the `/tmp/tagged` directory (and the converted files) to Dropbox as a subdirectory of the scan directory. I do this so I know for sure that I've processed these files.

Finally, I import the `tagged` directory into Lightroom.

## Building a release

Make sure the `build` module is installed:

```bash
pip3 install build
```

Then run the build:

```bash
python3 -m build
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

### Author

Terry Moore

### Status

2023-07-05: This tool is still a work in progress. It works well enough to be useful to others, especially for someone with a functional understanding of Python.

### Future Directions

* Guess the location of the JPEGs from the location of the shot info file.
* Allow the user to specify the serial numbers of their own lenses and cameras without editing `settings.json`.
* Add keywording and subject input, especially if we can validate.
* Add json equivalent to the `.csv` input, so we can use JSON Schemas to pre-validate input in VS Code.

### Prerequisites

Tested on macOS 13.4.1 (arm64, as reported by `sw_vers`) with python3 v3.10.7 and `exiftool` version 12.62 (as reported by `exiftool -ver`).

### License

Released under MIT license.
