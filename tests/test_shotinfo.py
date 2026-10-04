##############################################################################
#
# Name: test_shotinfo.py
#
# Function:
#       Tests for annotate_film_scans.shotinfo
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

import json
import pathlib

import pytest

from annotate_film_scans.app import App
from annotate_film_scans.shotinfo import ShotInfoFile
from annotate_film_scans import settings as S

SETTINGS = {
    "camera": { "Cam": { "IFD0:Make": "Maker", "IFD0:Model": "Model" } },
    }

def read_shots(tmp_path, monkeypatch, csv_text: str, nfiles: int = 1) -> dict:
    """ run csv_text through ShotInfoFile, with nfiles input files """
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "settings.json").write_text(json.dumps(SETTINGS))
    monkeypatch.setenv(S.ENV_SETTINGS_DIR, str(cfg))
    out = tmp_path / "out"
    out.mkdir()
    files = []
    for i in range(nfiles):
        f = tmp_path / f"img{i}.jpg"
        f.write_bytes(b"")
        files.append(str(f))
    csv = tmp_path / "shots.csv"
    csv.write_text(csv_text)
    app = App([ "-d", str(out), "-s", str(csv), *files ])
    return ShotInfoFile(app).read_from_path(csv)

class TestColumns:
    def test_frame2_column_optional(self, tmp_path, monkeypatch):
        info = read_shots(tmp_path, monkeypatch,
            "Frame,Exposure,Aperture,Date,Time,Camera\n"
            "1,1/125,f/8,2026-09-24,09:49-04:00,Cam\n"
            )
        assert list(info) == [1]
        assert info[1]["ExifIFD:ExposureTime"] == "1/125"
        assert info[1]["IFD0:Make"] == "Maker"

    def test_minimal_columns(self, tmp_path, monkeypatch):
        info = read_shots(tmp_path, monkeypatch,
            "Frame,Exposure,Date,Time\n"
            "1,1/125,2026-09-24,09:49-04:00\n"
            "2,1/60,,\n",
            nfiles=2
            )
        assert sorted(info) == [1, 2]
        assert info[2]["ExifIFD:ExposureTime"] == "1/60"

    def test_frame_column_required(self, tmp_path, monkeypatch):
        with pytest.raises(ShotInfoFile.Error, match="Frame"):
            read_shots(tmp_path, monkeypatch,
                "Exposure,Aperture\n"
                "1/125,f/8\n"
                )
