##############################################################################
#
# Name: app.py
#
# Function:
#       Toplevel App() class
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

#### imports ####
import argparse
import copy
from datetime import datetime, timezone
from importlib.resources import files as importlib_files
import itertools
import json
import jsons
import logging
import pathlib
import re
import subprocess
from typing import Union

from .constants import Constants
from .shotinfo import ShotInfoFile

##############################################################################
#
# The application class
#
##############################################################################

class App():
    def __init__(self):
        # load the constants
        self.constants = Constants()

        # read the JSON settings file -- this is needed for arguments
        settings_file = importlib_files("annotate-film-scans").joinpath("settings.json")
        if not settings_file.is_file():
            raise self.Error(f"Can't find setup JSON file: {settings_file}")

        settings_text = ""
        try:
            settings_text = settings_file.read_text()
        except:
            raise self.Error(f"Can't read: {settings_file}")

        self.settings = jsons.loads(settings_text)

        # now parse the args
        args = self._parse_arguments()
        self.args = args

        # initialize logging
        loglevel = logging.ERROR - 10 * args.verbose
        if loglevel < 0:
            loglevel = 0

        logging.basicConfig(level=loglevel, format='%(relativeCreated)6d %(levelname)-6s %(message)s')
        self.log = logging.getLogger(__name__)
        self.log.debug("Initializing App")
        self._initialize()
        self.log.info("App is initialized")
        return

    def _initialize(self):
        self.log.debug("App.initialize called")
        self.outputDir = self.args.dir
        if not self.outputDir.exists():
            raise self.Error("Output directory does not exist: " + str(self.outputDir) + " -- either create it or use the -d switch to select a different one")

    #######################
    # parse the arguments #
    #######################
    def _parse_arguments(self):
        constants = self.constants
        settings = self.settings
        parser = argparse.ArgumentParser(
            prog="annotate-film-scans",
            description="Annotate film scans, coping and numbering appropriately",
            # do not allow abbreviations -- you might break batch files
            allow_abbrev=False
            )
        parser.add_argument(
            "--verbose", "-v",
            action='count', default=0,
            help="increase verbosity, once for each use"
            )
        parser.add_argument(
            "--dir", "-d",
            default=pathlib.Path("./tmp"),
            type=pathlib.Path,
            help="where to put data files (default: %(default)s)"
            )
        parser.add_argument(
            "--forward", "-f",
            action='store_true',
            help="number files in ascending order, rather than reversing; many scans are in reverse order compared to the film"
            )
        parser.add_argument(
            "--camera",
            default=list(settings["camera"])[0],
            choices=settings['camera'],
            help="camera that took image (default: %(default)s)"
            )
        parser.add_argument(
            "--lens",
            default=list(settings["lens"])[0],
            choices=settings['lens'],
            help="lens used for image (default: %(default)s)"
        )
        parser.add_argument(
            "--film",
            # default=list(settings["lens"])[0],
            choices=settings['film'],
            help="film used for image"
        )
        parser.add_argument(
            "--lab",
            # default=list(settings["lens"])[0],
            choices=settings['lab'],
            help="lab used for image"
        )
        parser.add_argument(
            "--process",
            # default=list(settings["lens"])[0],
            choices=settings['process'],
            help="process used for image"
        )
        parser.add_argument(
            "--author",
            default=list(settings["author"])[0],
            choices=settings['author'],
            help="author/rights for image (default: %(default)s)"
        )
        parser.add_argument(
            "--roll",
            help="Roll ID"
        )
        parser.add_argument(
            "--shot-info-file", "-s",
            metavar="{shot-info-csv}",
            type=pathlib.Path,
            help="name of per-shot info file (as a .csv or .txt file; first line is header)"
        )
        parser.add_argument(
            "--date",
            metavar="{date-iso-8601}",
            type=datetime.fromisoformat,
            help="base capture date/time for all images in this run; can be overridden on a shot-by-shot bases in the shot info file"
        )
        parser.add_argument(
            "input_files",
            metavar="{InputFile}",
            nargs="+",
            help="Name of an input file, generally a pattern ending in .jpg"
            )
        parser.add_argument(
            "--dry-run", "-n",
            action="store_true",
            help="go through the motions, but don't write files"
        )
        # parse the args, and return
        args = parser.parse_args()
        args.input_files = [ pathlib.Path(iArg).expanduser() for iArg in args.input_files ]
        args.dir = pathlib.Path(args.dir).expanduser()
        return args

    class Error(Exception):
        """ this is the Exception thrown for application errors """
        pass

    #################################
    # Run the app and return status #
    #################################
    def run(self) -> int:
        args = self.args
        input_files = sorted(args.input_files, reverse=not args.forward)
        self.log.debug(f"{input_files=}")
        self.log.debug(f"{len(input_files)=}")

        # read the shot-info file
        info = []
        shot_info_object = ShotInfoFile(self)
        info = shot_info_object.read_from_path(args.shot_info_file)

        # build the attributes
        attributes = dict()
        for item in {
                        "camera": args.camera,
                        "lens": args.lens,
                        "film": args.film,
                        "process": args.process,
                        "lab": args.lab,
                        "author": args.author
                    }.items():
            if item[1] != None:
                setting = self.settings[item[0]][item[1]]
                self.log.debug("update: %s -> %s: %s", item[0], item[1], setting)
                attributes.update(setting)

        self.log.debug("attributes: %s", attributes)

        # copy files, renaming
        for i in range(len(input_files)):
            inpath = input_files[i]
            base_inpath = inpath.name
            outpath = self.outputDir / f"{(i + 1):03d}-{base_inpath}"
            self.log.debug("%d: %s -> %s", i, str(inpath), str(outpath) )

            # copy the file
            frame_info = None
            if i + 1 in info:
                frame_info = info[i + 1]

            self._copy(inpath, outpath, copy.copy(attributes), frame_info)
            # self.log.info("/bin/cp -p %s %s", str(inpath), str(outpath) )
            # subprocess.run([ "/bin/cp", "-p", str(inpath), str(outpath)], check=True)

        return 0

    def _copy(self, inpath: pathlib.Path, outpath: pathlib.Path, settings, frame_settings):
        if frame_settings != None:
            settings.update(frame_settings)
        
        scanner_json = self._read_make_model(inpath)
        settings["XMP-AnalogExif:ScannerMaker"] = scanner_json["Make"]
        settings["XMP-AnalogExif:Scanner"] = scanner_json["Model"]

        self._analogexif_to_comment(settings)

        json_settings_str = json.dumps(settings, indent=2)
        args = [ 
                "exiftool",
                "-unsafe",
                "-XMP-exif:DateTimeDigitized<XMP:CreateDate",
                "-json=-",
                "-o", str(outpath),
                str(inpath)
                ]

        self.log.info(" ".join(args))
        self.log.debug("_copy: json_settings: %s", json_settings_str)
        if not self.args.dry_run:
            subprocess.run(args, input=json_settings_str, check=True, text=True)
        else:
            self.log.info("(skipping copy due to --dry-run)")

    def _analogexif_to_comment(self, settings: dict) -> dict:
        pattern = re.compile(r"XMP-AnalogExif:(.*)", flags=re.IGNORECASE)
        comment = None
        for item in settings.items():
            key = item[0]
            match = re.fullmatch(pattern, key)
            if match != None:
                # add to the comment
                if comment == None:
                    comment = "Photo information: \n"
                comment += f"\t{match.group(1)}: {item[1]}. \n"
        settings["IFD0:XPComment"] = comment
        settings["ExifIFD:UserComment"] = comment
        return settings

    def _read_make_model(self, inpath):
        args = [ "exiftool", "-json", "-s", "-make", "-model", str(inpath) ]

        self.log.info(" ".join(args))
        subprocess_result = subprocess.run(args, capture_output=True, check=True, text=True)
        result = json.loads(subprocess_result.stdout)[0]
        self.log.debug("_read_make_model: %s", result)
        return result
