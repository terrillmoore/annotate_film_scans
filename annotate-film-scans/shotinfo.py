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
from io import TextIOWrapper
import itertools
import pathlib
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

    def read_path(self, ipath: Union[ pathlib.Path, str ] ) -> list:
        path = pathlib.Path(ipath)
        if path.match("*.csv"):
            return self.read_path_csv(path)
        else:
            raise self.Error(f"Unknown file type: {path}")

    def read_path_csv(self, ipath: pathlib.Path) -> list:
        """ read a CSV file given path """
        # open the file and read it.
        with open(ipath, "r", newline='') as f:
            return self.read_file_csv(f)
    
    def read_file_csv(self, f: TextIOWrapper) -> list:
        """ read a CSV stream: first line is header, rest are contents. Retuns a list of dicts """

        # create csv stream from stream -- use excel (default) delimiters
        filereader = csv.reader(f, dialect='excel', skipinitialspace=True)

        # read the header and confirm it
        csv_dict = self._read_first_line(filereader)

        # read list of dict entries
        result = self._read_body(filereader, csv_dict)

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
            self.app.log.debug(f"_read_body: line %d: %s", filereader.line_num, row_result )
            result += row_result

        return result
