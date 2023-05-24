# Annotate Film Scans

## Manual

### For Prause

Reverse pictures to match notes into the `tagged` directory. After that, we'll update in place. Names are nnn-origname.jpg

```bash

```bash
CAPTURE_TIME="2023-05-02t08:00
exiftool \
    '-DateTimeDigitized<ModifyDate' \
    -SubSecCreateDate=2023:04:28 06:00:00-04:00' \
    '-SubSecDateTimeOriginal=2023:04:28 06:00:00-04:00' \
    $(jot 17 22 | xargs printf "0007229200%02d*.jpg\n")
```