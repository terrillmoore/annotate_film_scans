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

def read_shots(tmp_path, monkeypatch, csv_text: str, nfiles: int = 1, extra_args: list = []) -> dict:
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
    app = App([ "-d", str(out), "-s", str(csv), *extra_args, *files ])
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

#### time propagation (#17) ####

DTO = "Composite:SubSecDateTimeOriginal"

def times(info: dict) -> dict:
    """ frame -> capture time string, for frames that aren't skipped """
    return { frame: attrs[DTO] for frame, attrs in info.items() if DTO in attrs }

def skipped(info: dict) -> list:
    return sorted(frame for frame, attrs in info.items() if DTO not in attrs)

HEADER = "Frame,Frame2,Exposure,Date,Time\n"

class TestTimePropagation:
    def test_explicit_times(self, tmp_path, monkeypatch):
        info = read_shots(tmp_path, monkeypatch, HEADER +
            "1,,1/125,2026-09-24,09:49-04:00\n"
            "2,,1/125,2026-09-25,10:00-04:00\n",
            nfiles=2)
        assert times(info) == {
            1: "2026:09:24 09:49:00-04:00",
            2: "2026:09:25 10:00:00-04:00" }

    def test_auto_advance_uses_default_delta(self, tmp_path, monkeypatch):
        info = read_shots(tmp_path, monkeypatch, HEADER +
            "1,,1/125,2026-09-24,09:49-04:00\n"
            "2,,1/125,,\n"
            "3,,1/125,,\n",
            nfiles=3)
        assert times(info) == {
            1: "2026:09:24 09:49:00-04:00",
            2: "2026:09:24 09:49:30-04:00",
            3: "2026:09:24 09:50:00-04:00" }

    def test_timedelta_header_option(self, tmp_path, monkeypatch):
        info = read_shots(tmp_path, monkeypatch,
            "--\nTimeDelta: 120\n--\n" + HEADER +
            "1,,1/125,2026-09-24,09:49-04:00\n"
            "2,,1/125,,\n",
            nfiles=2)
        assert times(info)[2] == "2026:09:24 09:51:00-04:00"

    def test_time_delta_command_line(self, tmp_path, monkeypatch):
        info = read_shots(tmp_path, monkeypatch, HEADER +
            "1,,1/125,2026-09-24,09:49-04:00\n"
            "2,,1/125,,\n",
            nfiles=2, extra_args=["-T", "600"])
        assert times(info)[2] == "2026:09:24 09:59:00-04:00"

    def test_header_timedelta_overrides_command_line(self, tmp_path, monkeypatch):
        info = read_shots(tmp_path, monkeypatch,
            "--\nTimeDelta: 120\n--\n" + HEADER +
            "1,,1/125,2026-09-24,09:49-04:00\n"
            "2,,1/125,,\n",
            nfiles=2, extra_args=["-T", "600"])
        assert times(info)[2] == "2026:09:24 09:51:00-04:00"

    def test_frame_range_spaced_by_delta(self, tmp_path, monkeypatch):
        info = read_shots(tmp_path, monkeypatch, HEADER +
            "1,3,1/125,2026-09-24,09:49-04:00\n",
            nfiles=3)
        assert times(info) == {
            1: "2026:09:24 09:49:00-04:00",
            2: "2026:09:24 09:49:30-04:00",
            3: "2026:09:24 09:50:00-04:00" }

    def test_row_after_range_continues(self, tmp_path, monkeypatch):
        info = read_shots(tmp_path, monkeypatch, HEADER +
            "1,3,1/125,2026-09-24,09:49-04:00\n"
            "4,,1/125,,\n",
            nfiles=4)
        assert times(info)[4] == "2026:09:24 09:50:30-04:00"

    def test_skip_range_advances_time(self, tmp_path, monkeypatch):
        # the case from #16: skipped frames still take up time
        info = read_shots(tmp_path, monkeypatch,
            "--\nTimeDelta: 120\n--\n" + HEADER +
            "1,,1/125,2026-09-24,17:30-04:00\n"
            "2,5,skip,,\n"
            "6,,1/125,,\n",
            nfiles=2)
        assert skipped(info) == [2, 3, 4, 5]
        assert times(info) == {
            1: "2026:09:24 17:30:00-04:00",
            6: "2026:09:24 17:40:00-04:00" }

    def test_skip_does_not_consume_files(self, tmp_path, monkeypatch):
        info = read_shots(tmp_path, monkeypatch, HEADER +
            "1,,1/125,2026-09-24,09:49-04:00\n"
            "2,,skip,,\n"
            "3,,1/125,,\n",
            nfiles=2)
        assert info[1]["file"] == 1
        assert info[3]["file"] == 2

    def test_explicit_time_overrides_auto(self, tmp_path, monkeypatch):
        info = read_shots(tmp_path, monkeypatch, HEADER +
            "1,,1/125,2026-09-24,09:49-04:00\n"
            "2,4,skip,,\n"
            "5,,1/125,2026-09-24,12:00-04:00\n"
            "6,,1/125,,\n",
            nfiles=3)
        assert times(info) == {
            1: "2026:09:24 09:49:00-04:00",
            5: "2026:09:24 12:00:00-04:00",
            6: "2026:09:24 12:00:30-04:00" }

    def test_mixed_skip_groups_with_different_base_times(self, tmp_path, monkeypatch):
        info = read_shots(tmp_path, monkeypatch,
            "--\nTimeDelta: 60\n--\n" + HEADER +
            "1,3,skip,2026-09-24,08:00-04:00\n"
            "4,,1/125,,\n"
            "5,6,skip,2026-09-25,14:00-04:00\n"
            "7,,1/125,,\n"
            "8,,1/125,,\n",
            nfiles=3)
        assert skipped(info) == [1, 2, 3, 5, 6]
        assert times(info) == {
            4: "2026:09:24 08:03:00-04:00",
            7: "2026:09:25 14:02:00-04:00",
            8: "2026:09:25 14:03:00-04:00" }

    def test_time_without_date_keeps_previous_date(self, tmp_path, monkeypatch):
        info = read_shots(tmp_path, monkeypatch, HEADER +
            "1,,1/125,2026-09-24,09:49-04:00\n"
            "2,,1/125,,15:00\n",
            nfiles=2)
        assert times(info)[2] == "2026:09:24 15:00:00-04:00"

    def test_timezone_inherited_from_previous_row(self, tmp_path, monkeypatch):
        info = read_shots(tmp_path, monkeypatch, HEADER +
            "1,,1/125,2026-09-24,09:49-07:00\n"
            "2,,1/125,2026-09-25,10:00\n",
            nfiles=2)
        assert times(info)[2] == "2026:09:25 10:00:00-07:00"

    def test_timezone_change_is_kept(self, tmp_path, monkeypatch):
        info = read_shots(tmp_path, monkeypatch, HEADER +
            "1,,1/125,2026-09-24,09:49-07:00\n"
            "2,,1/125,2026-09-25,10:00-04:00\n"
            "3,,1/125,,\n",
            nfiles=3)
        assert times(info)[2] == "2026:09:25 10:00:00-04:00"
        assert times(info)[3] == "2026:09:25 10:00:30-04:00"

    def test_compact_timezone(self, tmp_path, monkeypatch):
        info = read_shots(tmp_path, monkeypatch, HEADER +
            "1,,1/125,2026-09-24,09:49-0400\n"
            "2,,1/125,2026-09-24,09:50+0530\n",
            nfiles=2)
        assert times(info) == {
            1: "2026:09:24 09:49:00-04:00",
            2: "2026:09:24 09:50:00+05:30" }

    def test_first_time_needs_timezone(self, tmp_path, monkeypatch):
        with pytest.raises(ShotInfoFile.Error, match="timezone"):
            read_shots(tmp_path, monkeypatch, HEADER +
                "1,,1/125,2026-09-24,09:49\n")

    def test_timezone_from_date_option(self, tmp_path, monkeypatch):
        info = read_shots(tmp_path, monkeypatch, HEADER +
            "1,,1/125,,09:49\n",
            extra_args=["--date", "2026-09-24T08:00-04:00"])
        assert times(info)[1] == "2026:09:24 09:49:00-04:00"

    def test_date_option_as_base_time(self, tmp_path, monkeypatch):
        info = read_shots(tmp_path, monkeypatch, HEADER +
            "1,,1/125,,\n"
            "2,,1/125,,\n",
            nfiles=2, extra_args=["--date", "2026-09-24T08:00-04:00"])
        assert times(info) == {
            1: "2026:09:24 08:00:00-04:00",
            2: "2026:09:24 08:00:30-04:00" }

    def test_advance_past_midnight(self, tmp_path, monkeypatch):
        info = read_shots(tmp_path, monkeypatch, HEADER +
            "1,,1/125,2026-09-24,23:59:45-04:00\n"
            "2,,1/125,,\n",
            nfiles=2)
        assert times(info)[2] == "2026:09:25 00:00:15-04:00"

    def test_descending_range(self, tmp_path, monkeypatch):
        # frames 4, 3, 2 shot in that order; time moves forward
        info = read_shots(tmp_path, monkeypatch, HEADER +
            "4,2,1/125,2026-09-24,09:49-04:00\n"
            "5,,1/125,,\n",
            nfiles=4)
        assert times(info) == {
            4: "2026:09:24 09:49:00-04:00",
            3: "2026:09:24 09:49:30-04:00",
            2: "2026:09:24 09:50:00-04:00",
            5: "2026:09:24 09:50:30-04:00" }
