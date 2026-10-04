##############################################################################
#
# Name: test_app_run.py
#
# Function:
#       End-to-end tests: run the app on a tiny JPEG and read the result
#       back with exiftool.
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

import base64
import json
import pathlib
import shutil
import subprocess

import pytest

from annotate_film_scans.app import App
from annotate_film_scans import settings as S

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")

# a valid 1x1 JPEG
TINY_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////"
    "////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBAB"
    "AAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
    )

SETTINGS = {
    "camera": {
        "SLR": { "IFD0:Make": "Canon", "IFD0:Model": "F-1", "XMP-AnalogExif:FilmType": "135" },
        },
    "lens": {
        "FD 50": {
            "XMP:LensManufacturer": "Canon", "XMP:LensModel": "FD 50mm f/1.4",
            "EXIF:FocalLength": "50.0 mm", "EXIF:MaxApertureValue": 1.4,
            },
        },
    "author": { "Me": { "XMP:Creator": "Pat Example", "XMP:Rights": "All rights reserved" } },
    "defaults": { "author": "Me" },
    }

def run_app(tmp_path, monkeypatch, csv_text: str) -> dict:
    """ annotate one tiny JPEG per csv_text; return its tags (-G1) """
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "settings.json").write_text(json.dumps(SETTINGS))
    monkeypatch.setenv(S.ENV_SETTINGS_DIR, str(cfg))
    out = tmp_path / "out"
    out.mkdir()
    img = tmp_path / "scan.jpg"
    img.write_bytes(TINY_JPEG)
    csv = tmp_path / "shots.csv"
    csv.write_text(csv_text)

    app = App([ "-d", str(out), "-s", str(csv), str(img) ])
    assert app.run() == 0

    outputs = list(out.iterdir())
    assert [ p.name for p in outputs ] == [ "001-scan.jpg" ]
    result = subprocess.run(
        [ "exiftool", "-config", str(app.exiftool_config), "-json", "-G1", "-a", str(outputs[0]) ],
        capture_output=True, check=True, text=True
        )
    return json.loads(result.stdout)[0]

CSV = (
    "--\nCamera: SLR\nFilm: Tri-X 400\n--\n"
    "Frame,Exposure,Aperture,Date,Time\n"
    "1,1/125,f/8,2026-09-24,09:49-04:00\n"
    )

class TestRun:
    def test_camera_without_lens(self, tmp_path, monkeypatch):
        # the default "fixed" lens has no tags; this used to crash
        tags = run_app(tmp_path, monkeypatch, CSV)
        assert tags["IFD0:Make"] == "Canon"
        assert "ExifIFD:LensModel" not in tags

    def test_lens(self, tmp_path, monkeypatch):
        tags = run_app(tmp_path, monkeypatch,
            CSV.replace("Camera: SLR\n", "Camera: SLR\nLens: FD 50\n"))
        assert tags["ExifIFD:LensModel"] == "Canon FD 50mm f/1.4"
        assert tags["ExifIFD:LensInfo"] == "50mm f/1.4"

    def test_capture_time_and_exposure(self, tmp_path, monkeypatch):
        tags = run_app(tmp_path, monkeypatch, CSV)
        assert tags["ExifIFD:DateTimeOriginal"] == "2026:09:24 09:49:00"
        assert tags["ExifIFD:OffsetTimeOriginal"] == "-04:00"
        assert tags["XMP-photoshop:DateCreated"] == "2026:09:24 09:49:00-04:00"
        assert tags["ExifIFD:ExposureTime"] == "1/125"
        assert tags["ExifIFD:FNumber"] == 8.0

    def test_custom_namespaces_written(self, tmp_path, monkeypatch):
        tags = run_app(tmp_path, monkeypatch, CSV)
        assert tags["XMP-AnalogExif:Film"] == "Kodak Tri-X 400"
        assert tags["XMP-AnalogExif:FilmType"] == 135
        assert "XMP-AnnotateFilmScans:AnnotateFilmScansVersion" in tags

    def test_author(self, tmp_path, monkeypatch):
        tags = run_app(tmp_path, monkeypatch, CSV)
        assert tags["XMP-dc:Creator"] == "Pat Example"
        assert tags["IFD0:Artist"] == "Pat Example"
        assert tags["IFD0:Copyright"] == "Copyright Pat Example"
