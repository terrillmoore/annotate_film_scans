##############################################################################
#
# Name: shotinfo.py
#
# Function:
#       Class for the shot information files
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

import configparser
import csv
from datetime import date, datetime, time, timezone, timedelta
from io import TextIOWrapper, StringIO
import itertools
import pathlib
import re
from typing import Union, List
from .__version__ import __version__
from .constants import Constants

#### The ShotInfoFile class
class ShotInfoFile:
    def __init__(self, app):
        self.app = app
        self.shot_fields = app.constants.shot_fields
        pass

    class Error(Exception):
        """ this is the Exception thrown for ShotInfo errors """
        pass

    def read_from_path(self, ipath: Union[ pathlib.Path, str ] ) -> list:
        path = pathlib.Path(ipath)
        if path.match("*.csv"):
            return self.read_csv_from_path(path)
        else:
            raise self.Error(f"Unknown file type: {path}")

    def read_csv_from_path(self, ipath: pathlib.Path) -> list:
        """ read a CSV file given path """
        # open the file and read it.
        with open(ipath, "r", newline='') as f:
            return self.read_csv_from_stream(f)

    def read_csv_from_stream(self, f: TextIOWrapper) -> list:
        """ read a CSV stream: first line is header, rest are contents. Retuns a list of dicts """

        # scan options from front of file.
        options = ""
        firstline = f.readline().splitlines()[0]
        if firstline == "--":
            self.app.log.debug("_read_csv_from_stream: process '--' options")
            for optionline in f:
                self.app.log.debug("_read_csv_from_stream: option line: %s", optionline)
                if optionline.splitlines()[0] == "--":
                    break
                options += optionline
        else:
            self.app.log.debug("_read_csv_from_stream: no option tag: %s", firstline)
            f.seek(0)

        if options != "":
            p = configparser.ConfigParser()
            p.read_string("[Options]\n" + options)
            if p.has_option("Options", "roll"):
                self.app.args.roll = p["Options"]["roll"]
                self.app.log.debug("_read_csv_from_stream: set roll: %s", self.app.args.roll)
            if p.has_option("Options", "forward"):
                self.app.args.forward = p.getboolean("Options", "forward", raw=True)
                self.app.log.debug("_read_csv_from_stream: set forward: %d", self.app.args.forward)
            if p.has_option("Options", "timedelta"):
                self.app.args.timedelta = p.getint("Options", "timedelta",raw=True)
                self.app.log.debug("_read_csv_from_stream: set timedelta: %d", self.app.args.timedelta)
            if p.has_option("Options", "camera"):
                self.app.args.camera = p.get("Options", "camera", raw=True)
                self.app.log.debug("_read_csv_from_stream: set camera: %s", self.app.args.camera)
            if p.has_option("Options", "lens"):
                self.app.args.lens = p.get("Options", "lens", raw=True)
                self.app.log.debug("_read_csv_from_stream: set lens: %s", self.app.args.lens)
            if p.has_option("Options", "film"):
                self.app.args.film = p.get("Options", "film", raw=True)
                self.app.log.debug("_read_csv_from_stream: set film: %s", self.app.args.film)
            if p.has_option("Options", "process"):
                self.app.args.process = p.get("Options", "process", raw=True)
                self.app.log.debug("_read_csv_from_stream: set process: %s", self.app.args.process)
            if p.has_option("Options", "lab"):
                self.app.args.lab = p.get("Options", "lab", raw=True)
                self.app.log.debug("_read_csv_from_stream: set lab: %s", self.app.args.lab)
            if p.has_option("Options", "developer"):
                self.app.args.developer = p.get("Options", "developer", raw=True)
                self.app.log.debug("_read_csv_from_stream: set developer: %s", self.app.args.developer)
            if p.has_option("Options", "devtime"):
                self.app.args.devtime = p.get("Options", "devtime", raw=True)
                self.app.log.debug("_read_csv_from_stream: set devtime: %s", self.app.args.devtime)
            if p.has_option("Options", "devtemp"):
                self.app.args.devtemp = p.get("Options", "devtemp", raw=True)
                self.app.log.debug("_read_csv_from_stream: set devtemp: %s", self.app.args.devtemp)
            if p.has_option("Options", "devnotes"):
                self.app.args.devnotes = p.get("Options", "devnotes", raw=True)
                self.app.log.debug("_read_csv_from_stream: set devnotes: %s", self.app.args.devnotes)

        # read rest of file into a string object
        sBody = f.read()
        sBodyNoTabs = sBody.replace('\t', ' ')

        # create csv stream from stream -- use excel (default) delimiters
        filereader = csv.reader(StringIO(sBodyNoTabs), dialect='excel', skipinitialspace=True)

        # read the header and confirm it
        csv_dict = self._read_first_line(filereader)

        # read list of dict entries
        result = self._read_body(filereader, csv_dict)

        self._extend_datetime(result)
        self._extend_simple_properties(result)
        self._extend_camera_and_lens_info(result)
        result = self._flatten_and_expand(result)
        self.app.log.debug("read_csv_from_stream: result=%s", result)
        return result

    def _read_first_line(self, filereader) -> list:
        # read the first line and parse per CSV
        header = next(filereader)
        self.app.log.debug("_read_first_line: header: %s", header)
        result = []
        seen_fields = dict()

        for field in header:
            canonical_field = field.lower().strip()
            if not canonical_field in self.shot_fields:
                raise self.Error(f"Unknown CSV field name: {field}")
            if canonical_field in seen_fields:
                raise self.Error(f"Duplicate field {field} already seen at index {seen_fields[canonical_field]}")
            seen_fields[canonical_field] = len(result)
            result.append(canonical_field)

        self.app.log.debug("_read_first_line: result: %s", [ result ])
        return result

    def _read_body(self, filereader, headers: list) -> list:
        # it's hard to switch back and forth from a normal reader to a dict reader,
        # so we just sort of duplicate dict reader
        result = []

        thisline = filereader.line_num + 1
        for row in filereader:
            self.app.log.debug("_read_next_line: row %d: %s", thisline, row)
            row_result = dict()
            for column in itertools.zip_longest(headers, row):
                name = column[0]
                if name == None:
                    raise self.Error(f"Extra field value at line {filereader.line_num}: {column[1]}")
                if column[1] == None or column[1].strip() == "":
                    row_result[name] = None
                else:
                    row_result[name] = column[1].strip()
            self.app.log.debug(f"_read_body: line %d: %s", thisline, row_result )
            row_result["line_num"] = thisline
            thisline = filereader.line_num + 1
            result.append(row_result)

        return result

    #
    # Propagate date/time through the file; update in place
    # This runs before flattening.
    #
    def _extend_datetime(self, rows: list) -> list:
        def datetime_fromiso(row: dict, field: str) -> datetime:
            result = None
            if row.get(field) == None:
                raise self.Error("datetime_fromiso: no '%s' in row", field)
            try:
                result = datetime.fromisoformat(row[field])
            except Exception as e:
                raise self.Error(f"error converting date({field}) at line {row['line_num']}: {row[field]}: {e}")
            return result

        def time_fromiso(row: dict, field: str, baseTzInfo=None) -> time:
            result = None
            timestr = row.get(field)
            if timestr == None:
                raise self.Error("time_fromiso: no '%s' in row", field)

            # fix up missing colon in timezone
            timematch = re.fullmatch(self.app.constants.re_time_withtz, timestr)
            if timematch and timematch.group(4) and not timematch.group(8):
                # we have nnnn; convert to nn:nn
                timestr = timematch.group(1) + "+" + timematch.group(6) + ":" + timematch.group(7)

            try:
                result = time.fromisoformat(timestr)
            except Exception as e:
                raise self.Error(f"error converting time({field}) at line {row['line_num']}: {row[field]} => {timestr}: {e}")

            # if timezone given, return
            if result.tzinfo != None and result.tzinfo.utcoffset(None) != None:
                return result

            if baseTzInfo == None:
                raise self.Error(f"no timezone in time({field}), and base timezone not known: at line {row['line_num']}: {row[field]}")
            return result.replace(tzinfo=baseTzInfo)

        basedatetime = self.app.args.date

        nextdatetime = None
        lasttzinfo = None
        delta = timedelta(seconds = self.app.args.timedelta)

        for row in rows:
            if ("time" in row and row["time"] != None):
                if not ("date" in row and row["date"] != None):
                    # time set without date.
                    if basedatetime == None:
                        raise self.Error(f"Time set, but base date not known: {row['time']}")
                    # make the datetime from the basedate
                    thistime = time_fromiso(row, "time", lasttzinfo)
                    # overwrite the time part
                    basedatetime = datetime.combine(basedatetime, thistime)
                    row["datetime"] = basedatetime
                else:
                    # time and date set
                    basedatetime = datetime.combine(
                                        datetime_fromiso(row, "date"),
                                        time_fromiso(row, "time", lasttzinfo)
                                        )
                    row["datetime"] = basedatetime
            else:
                # time is blank

                # if date was set, update the base date/time from that.
                if "date" in row and row["date"] != None:
                    raise self.Error("it makes no sense to have date and not time")

                if nextdatetime != None:
                    # time not specified, so we compute based on last frame in prev row.
                    basedatetime = nextdatetime
                else:
                    raise self.Error(f"Base time is not set: at line {row['line_num']}: {row['time']}")

                thistime = basedatetime.timetz()

                row["datetime"] = basedatetime

            # now remember last time, which must be the time of the *last*
            # shot in the row.
            if row.get("frame2") != None and row.get("frame") != None:
                try:
                    nextdatetime = basedatetime + (int(row["frame2"]) - int(row["frame"]) + 1) * delta
                except Exception as e:
                    raise self.Error("frame and frame2 not ints: %s", e)
            else:
                nextdatetime = basedatetime + delta
            lasttzinfo = nextdatetime.tzinfo

        self.app.log.debug("_extend_datetime: result: %s", rows)
        return rows

    #
    # helper for extending a setting, used several places
    #
    def _extend_setting(self, row, fieldname: str, currentvalue, setting):
        if fieldname in row and row[fieldname] != None:
            currentvalue = row[fieldname]
            if not currentvalue in self.app.settings[setting]:
                raise self.Error(f"Not a known {setting}: {currentvalue} line={row['line_num']}")
        row[fieldname] = currentvalue
        return currentvalue

    #
    # propagate camera, lens, focallength, aperture, exposure, filter
    #
    def _extend_camera_and_lens_info(self, rows: list) -> list:
        def to_float(row: dict, field: str) -> float:
            result = None
            try:
                result = float(row[field])
            except Exception as e:
                raise self.Error(f"Not an float: {field=} line={row['line_num']}: {e}")
            return result

        currentlens = self.app.args.lens
        currentfocal = None
        currentcamera = self.app.args.camera
        currentaperture = None
        currentexposure = None
        currentfilter = None
        currentroll = self.app.args.roll
        currentdevtime = None
        currentdevtemp = None
        currentcomment = None

        for row in rows:
            newcamera = self._extend_setting(row, "camera", currentcamera, "camera")
            if newcamera != currentcamera:
                currentcamera = newcamera
                currentlens = None
                currentfocal = None

            newlens = self._extend_setting(row, "lens", currentlens, "lens")
            if newlens != currentlens:
                currentlens = newlens
                currentfocal = None

            if "focallength" in row and row["focallength"] != None:
                currentfocal = to_float(row, "focallength")
            else:
                row["focallength"] = currentfocal

            if "aperture" in row and row["aperture"] != None:
                if row["aperture"] == "-":
                    currentaperture = None
                    row["aperture"] = None
                else:
                    currentaperture = row["aperture"]
            else:
                row["aperture"] = currentaperture

            if "exposure" in row and row["exposure"] != None:
                if row["exposure"] == "-":
                    currentexposure = None
                    row["exposure"] = None
                else:
                    currentexposure = row["exposure"]
            else:
                row["exposure"] = currentexposure

            # '-' cancels filter explicitly; empty inherits from default,
            # other non-empty sets the default.
            if "filter" in row and row["filter"] != None:
                if row["filter"] == "-":
                    currentfilter = None
                    row["filter"] = None
                else:
                    currentfilter = row["filter"]
            else:
                row["filter"] = currentfilter

            # '-' cancels roll explicitly; empty inherits from default,
            # other non-empty sets the default.
            if "roll" in row and row["roll"] != None:
                if row["roll"] == "-":
                    currentroll = None
                    row["roll"] = None
                else:
                    currentroll = row["roll"]
            else:
                row["roll"] = currentroll

            # '-' copies previous comment; empty,
            # other non-empty sets the default.
            if "comment" in row and row["comment"] != None:
                if row["comment"] == "-":
                    row["comment"] = currentcomment
                else:
                    currentcomment = row["comment"]
            else:
                currentcomment = None
                row["comment"] = None

            if "devtime" in row and row["devtime"] != None:
                currentdevtime = row["devtime"]
            else:
                row["devtime"] = currentdevtime

            if "devtemp" in row and row["devtemp"] != None:
                currentdevtemp = row["devtemp"]
            else:
                row["devtemp"] = currentdevtemp

        return rows

    #
    # propagate lab, film, process
    #
    def _extend_simple_properties(self, rows: list) -> list:
        currentlab = self.app.args.lab
        currentfilm = self.app.args.film
        self.app.log.debug("_extend_simple_properties: initial film: %s", currentfilm)
        currentprocess = self.app.args.process
        currentdeveloper = self.app.args.developer
        currentdevtime = self.app.args.devtime
        currentdevtemp = self.app.args.devtemp
        currentdevnotes = self.app.args.devnotes

        for row in rows:
            currentlab = self._extend_setting(row, "lab", currentlab, "lab")
            currentfilm = self._extend_setting(row, "film", currentfilm, "film")
            self.app.log.debug("_extend_simple_properties: extend film: %s", currentfilm)
            currentprocess = self._extend_setting(row, "process", currentprocess, "process")
            currentdeveloper = self._extend_setting(row, "developer", currentdeveloper, "developer")
            currentdevtime = self._extend_setting(row, "devtime", currentdevtime, "devtime")
            currentdevtemp = self._extend_setting(row, "devtemp", currentdevtemp, "devtemp")
            currentdevnotes = self._extend_setting(row, "devnotes", currentdevnotes, "devnotes")
        return rows

    #
    # flatten ranges and create per-image attributes
    #
    def _flatten_and_expand(self, rows: list) -> dict:
        def to_int(row: dict, field: str) -> int:
            result = None
            try:
                result = int(row[field])
            except Exception as e:
                raise self.Error(f"Not an int: {field=}[{row[field]}] line={row['line_num']}: {e}")
            return result

        result = dict()

        for row in rows:
            firstrow = to_int(row, "frame")
            lastrow = firstrow
            if row["frame2"] != None:
                lastrow = to_int(row, "frame2")
            rowseq = range(firstrow, lastrow+1)

            firstfile = None
            if "file" in row:
                firstfile = to_int(row, "file")

            thisfile = firstfile
            for iFrame in rowseq:
                attrs = self._expand_attrs(row, thisfile, iFrame - firstrow)

                if thisfile != None:
                    if not self.app.args.forward:
                        --thisfile
                    else:
                        ++thisfile

                if iFrame in result:
                    result[iFrame].update(attrs)
                else:
                    result[iFrame] = attrs

        self.app.log.debug("_flatten_and_expand: result=%s", result)
        return result

    #
    # convert key elements of a shot info row into equivalent attribute fields
    #
    def _expand_attrs(self, row: dict, file, duplicateIndex: int) -> dict:
        constants : Constants = self.app.constants

        def get_fnumber(row, field):
            if row[field] == None:
                return None
            value = row[field].strip()
            if value == "":
                return None
            if value == "?":
                return "not recorded"
            result = re.fullmatch(self.app.constants.re_fstop, value, flags=re.IGNORECASE)
            if result == None:
                    raise self.Error(f"invalid f-stop: {value}")
            return float(result.group(1))

        def get_exposure(row, field):
            if row[field] == None:
                return None
            value = row[field].strip()
            if value == "":
                return None
            if value == "?":
                return "not recorded"
            result = re.fullmatch(constants.re_exposure, value, flags=re.IGNORECASE)
            if result == None:
                raise self.Error(f"invalid exposure: {value}")
            return value

        def get_time_minutes(row, field):
            if row[field] == None:
                return None
            value = row[field].strip()
            if value == "":
                return None
            if value == "?":
                return "not recorded"
            result = re.fullmatch(constants.re_time_minutes, value, flags=re.IGNORECASE)
            if result == None:
                raise self.Error(f"invalid time duration (minutes): {value}")
            return value

        def get_temperature_c(row, field):
            if row[field] == None:
                return None
            value = row[field].strip()
            if value == "":
                return None
            if value == "?":
                return "not recorded"
            result = re.fullmatch(constants.re_temperature_c, value, flags=re.IGNORECASE)
            if result == None:
                raise self.Error(f"invalid temperature (minutes): {value}")
            if result.group(2) != None:
                return float(result.group(1) + result.group(2))
            else:
                return float(result.group(1))

        result = {}
        def put_value(name: str, value):
            if value != None:
                result[name] = value
        def update_from_settings(result: dict, row: dict, fieldname: str, setting: str):
            if row[fieldname] != None:
                result.update(self.app.settings[setting][row[fieldname]])
            return result

        # annotate the file number if provided.
        if file != None:
            result["file"] = file

        if row["exposure"] == "skip":
            put_value(constants.TAG_SKIP, True)
        else:
            put_value("ExifIFD:ExposureTime", get_exposure(row, "exposure"))
            put_value("ExifIFD:FNumber", get_fnumber(row, "aperture"))

            if "filter" in row:
                put_value("XMP-AnalogExif:Filter", row["filter"])

            if "roll" in row:
                put_value("XMP-AnalogExif:RollId", row["roll"])

            if "timedelta" in row:
                try:
                    deltaTime = int(row["timedelta"])
                except Exception as e:
                    raise self.Error(f'invalid timedelta: {row["timedelta"]}: {e}')
            else:
                deltaTime = self.app.args.timedelta

            deltaTime = deltaTime * duplicateIndex
            if row["datetime"] != None:
                datevalue = row["datetime"]
                datevalue += timedelta(seconds = deltaTime)
                datestring = datevalue.isoformat(sep=' ').replace('-', ':', 2)
                put_value("Composite:SubSecDateTimeOriginal", datestring)
                # set the CreateDate from the everything but the timezone.
                put_value("ExifIFD:CreateDate", datestring[0:19])
                put_value("System:FileModifyDate", datestring)
            update_from_settings(result, row, "lens", "lens")
            update_from_settings(result, row, "camera", "camera")
            update_from_settings(result, row, "lab", "lab")
            update_from_settings(result, row, "process", "process")
            update_from_settings(result, row, "film", "film")
            update_from_settings(result, row, "developer", "developer")
            #update_from_settings(result, row, "devtime", "devtime")
            #update_from_settings(result, row, "devtemp", "devtemp")
            #update_from_settings(result, row, "devnotes", "devnotes")

            put_value(constants.TAG_DEVELOP_TIME, get_time_minutes(row, "devtime"))
            put_value(constants.TAG_DEVELOP_TEMP, get_temperature_c(row, "devtemp"))

            if row.get("devnotes") != None:
                put_value(constants.TAG_DEVELOP_NOTES, row["devnotes"].strip())

            if row["focallength"] != None:
                focallength = float(row["focallength"])
                TAG_CROP_FACTOR = constants.TAG_CROP_FACTOR
                crop_factor = 1.0
                if TAG_CROP_FACTOR in result:
                    crop_factor = result[TAG_CROP_FACTOR]
                focallength_35mm = focallength * crop_factor
                put_value("ExifIFD:FocalLength", f"{focallength} mm")
                put_value("ExifIFD:FocalLengthIn35mmFormat", f"{focallength_35mm} mm")

            if "comment" in row and row["comment"] != None:
                put_value("XMP-AnnotateFilmScans:ImageNote", row["comment"].strip())

            put_value("XMP-AnnotateFilmScans:AnnotateFilmScansVersion", __version__)
        self.app.log.debug("_expand_attrs: row=%s result=%s", row, result)
        return result
