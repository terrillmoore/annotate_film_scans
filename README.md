# Annotate Film Scans

## Manual

### For Prause

Reverse pictures to match notes into the `tagged` directory. After that, we'll update in place. Names are `nnn-origname.jpg`

```bash
mkdir tmp
python3 010_copy_and_number.py /Users/tmm/Dropbox/Photos/Scans/Praus\ Productions/00008285/*.jpg
```

Use `AnalogExif` to set camera data and processing for all shots in `tmp`.

Use `exiftran` to rotate images that are vertical.

```bash
cd tmp
exiftran -2 -i 007-000082850030.jpg 008-000082850029.jpg 015-000082850022.jpg 016-000082850021.jpg 017-000082850020.jpg 018-000082850019.jpg 019-000082850018.jpg 020-000082850017.jpg 021-000082850016.jpg 022-000082850015.jpg 023-000082850014.jpg 036-000082850001.jpg
```

Use exiftool to set the capture time.

```bash
# set date for files 1-8
exiftool '-DateTimeDigitized=2023:05:15 12:00:00-04:00' '-SubSecCreateDate=2023:05:02 08:00:00-04:00' '-SubSecDateTimeOriginal=2023:05:02 08:00:00-04:00' $(jot 8 | xargs printf "%03d-*.jpg\n")
# set date for files 9-36
exiftool '-DateTimeDigitized=2023:05:15 12:00:00-04:00' '-SubSecCreateDate=2023:05:07 08:00:00-04:00' '-SubSecDateTimeOriginal=2023:05:07 08:00:00-04:00' $(jot 28 9 | xargs printf "%03d-*.jpg\n")
```

Now you can import into Lightroom (or whatever).
