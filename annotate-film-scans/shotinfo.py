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

import csv
from datetime import date, datetime, time, timezone
from io import TextIOWrapper
import itertools
import pathlib
import re
from typing import Union, List

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

        # create csv stream from stream -- use excel (default) delimiters
        filereader = csv.reader(f, dialect='excel', skipinitialspace=True)

        # read the header and confirm it
        csv_dict = self._read_first_line(filereader)

        # read list of dict entries
        result = self._read_body(filereader, csv_dict)

        self._extend_datetime(result)
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
            row_result = dict()
            for column in itertools.zip_longest(headers, row):
                name = column[0]
                if name == None:
                    raise self.Error(f"Extra field value at line {filereader.line_num()}: {column[1]}")
                if column[1] == None or column[1].strip() == "" or column[1].strip() == "-":
                    row_result[name] = None
                else:
                    row_result[name] = column[1]
            self.app.log.debug(f"_read_body: line %d: %s", thisline, row_result )
            row_result["line_num"] = thisline
            thisline = filereader.line_num + 1
            result.append(row_result)

        return result

    #
    # propagate date/time through the file; update in place
    #
    def _extend_datetime(self, rows: list) -> list:
        def datetime_fromiso(row: dict, field: str):
            result = None
            try:
                result = datetime.fromisoformat(row[field])
            except Exception as e:
                raise self.Error(f"error converting date({field}) at line {row['line_num']}: {row[field]}: {e}")
            return result

        def time_fromiso(row: dict, field: str):
            result = None
            try:
                result = time.fromisoformat(row[field])
            except Exception as e:
                raise self.Error(f"error converting time({field}) at line {row['line_num']}: {row[field]}: {e}")
            return result

        basedate = self.app.args.date
        thistime = None
        if basedate != None:
            thistime = basedate.time()

        for row in rows:
            if "time" in row and not ("date" in row and row["date"] != None):
                if basedate == None:
                    raise self.Error(f"Time set, but base date not knowns: {row['time']}")
                # make the datetime from the basedate
                basedate = datetime.combine(basedate, time_fromiso(row, "time"))
                row["datetime"] = basedate
                thistime = basedate.time()
            else:
                if "date" in row and row["date"] != None:
                    basedate = datetime_fromiso(row, "date")
                if "time" in row and row["time"] != None:
                    thistime = time_fromiso(row, "time")

                if basedate == None:
                    raise self.Error(f"Time set, but base date not knowns: {row['time']}")

                if thistime != None:
                    basedate = datetime.combine(basedate, thistime)
                row["datetime"] = basedate

        self.app.log.debug("_extend_datetime: result: %s", rows)
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
                raise self.Error(f"Not an int: {field=} line={row['line_num']}: {e}")
            return result

        result = dict()

        for row in rows:
            firstrow = to_int(row, "frame")
            lastrow = firstrow
            if row["frame2"] != None:
                lastrow = to_int(row, "frame2")
            rowseq = range(firstrow, lastrow+1)

            for iFrame in rowseq:
                attrs = self._expand_attrs(row)
                if iFrame in result:
                    result[iFrame].update(attrs)
                else:
                    result[iFrame] = attrs

        self.app.log.debug("_flatten_and_expand: result=%s", result)
        return result

    #
    # convert key elements of a shot info row into equivalent attribute fields
    #
    def _expand_attrs(self, row: dict) -> dict:
        def get_fnumber(row, field):
            result = re.fullmatch(self.app.constants.re_fstop, row[field], flags=re.IGNORECASE)
            if result == None:
                    return None
            return int(result.group(1))

        result = {}
        def put_value(name: str, value):
            if value != None:
                result[name] = value


        put_value("ExifIFD:ExposureTime", row["exposure"])
        put_value("ExifIFD:FNumber", get_fnumber(row, "aperture"))
        put_value("XMP-AnalogExif:Filter", row["filter"])
        if row["datetime"] != None:
            put_value("Composite:SubSecDateTimeOriginal", row["datetime"].isoformat(sep=' ').replace('-', ':'))

        self.app.log.debug("_expand_attrs: row=%s result=%s", row, result)
        return result
