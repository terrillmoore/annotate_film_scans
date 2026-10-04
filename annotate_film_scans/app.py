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
import logging
import pathlib
import re
import subprocess
import sys
from typing import Union

from .constants import Constants
from . import settings as settings_module
from .shotinfo import ShotInfoFile
from .__version__ import __version__

##############################################################################
#
# The application class
#
##############################################################################

class App():
    def __init__(self, argv: list[str] | None = None):
        # load the constants
        self.constants = Constants()
        if argv is None:
            argv = sys.argv[1:]

        # The settings options have to be parsed first: the settings
        # supply the choices and defaults for the main parser.
        settings_parser = self._settings_arg_parser()
        pre_args, _ = settings_parser.parse_known_args(argv)

        # initialize logging
        loglevel = logging.ERROR - 10 * pre_args.verbose
        if loglevel < 0:
            loglevel = 0

        logging.basicConfig(level=loglevel, format='%(relativeCreated)6d %(levelname)-6s %(message)s')
        self.log = logging.getLogger(__name__)

        # verbose: report the version.
        self.log.info("annotate_film_scans v%s", __version__)

        # exiftool needs this to know about our custom XMP namespaces
        self.exiftool_config = importlib_files("annotate_film_scans").joinpath("exiftool.config")
        if not self.exiftool_config.is_file():
            raise self.Error(f"Can't find exiftool config file: {self.exiftool_config}")

        self.settings_args = pre_args
        if pre_args.settings_dir is not None:
            self.settings_dir = pre_args.settings_dir.expanduser()
        else:
            self.settings_dir = settings_module.user_settings_dir()

        # --init-settings doesn't need (and mustn't require valid) settings
        if pre_args.init_settings is not None:
            self.command = self._run_init_settings
            return

        self.settings = self._load_settings(pre_args)

        if pre_args.check_settings:
            self.command = self._run_check_settings
            return

        # now parse the args
        self.args = self._parse_arguments(settings_parser, argv)
        self.command = self._run_annotate

        self._initialize()
        self.log.info("App is initialized")
        return

    ############################################
    # settings: options, loading, init & check #
    ############################################
    def _settings_arg_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
        parser.add_argument(
            "--verbose", "-v",
            action='count', default=0,
            help="increase verbosity, once for each use"
            )
        parser.add_argument(
            "--settings-dir",
            metavar="{dir}",
            type=pathlib.Path,
            help=f"directory holding your settings files (default: ${settings_module.ENV_SETTINGS_DIR} if set, else {settings_module.user_settings_dir()})"
            )
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--builtin-settings",
            metavar="{file}",
            type=pathlib.Path,
            help="use this file instead of the built-in settings (for testing)"
            )
        group.add_argument(
            "--no-builtin-settings",
            action="store_true",
            help="don't load the built-in settings"
            )
        parser.add_argument(
            "--no-user-settings",
            action="store_true",
            help="don't load the settings directory"
            )
        parser.add_argument(
            "--init-settings",
            metavar="{file}",
            nargs="?",
            const="",
            help="create the settings directory with editable templates, and if {file} is given, copy it in as settings.json; then exit"
            )
        parser.add_argument(
            "--check-settings",
            action="store_true",
            help="load and check all settings, list each entry and where it came from, then exit"
            )
        return parser

    def _builtin_settings_path(self, pre_args) -> pathlib.Path | None:
        if pre_args.no_builtin_settings:
            return None
        if pre_args.builtin_settings is not None:
            return pre_args.builtin_settings.expanduser()
        return settings_module.builtin_settings_path()

    def _load_settings(self, pre_args) -> settings_module.Settings:
        user_dir = None
        if not pre_args.no_user_settings:
            user_dir = self.settings_dir
            if pre_args.settings_dir is not None and not user_dir.is_dir():
                raise self.Error(f"settings directory not found: {user_dir}")

        try:
            result = settings_module.load_settings(
                builtin=self._builtin_settings_path(pre_args),
                user_dir=user_dir
                )
        except settings_module.SettingsError as e:
            raise self.Error(str(e))

        for path in result.sources:
            self.log.info("loaded settings: %s", path)
        for problem in result.check():
            self._warn(problem)
        return result

    # warnings the user needs to see whatever the verbosity
    def _warn(self, message: str) -> None:
        print(f"annotate-film-scans: warning: {message}", file=sys.stderr)

    def _run_init_settings(self) -> int:
        source = self.settings_args.init_settings
        source = pathlib.Path(source).expanduser() if source != "" else None
        try:
            created = settings_module.init_settings(
                self.settings_dir,
                source=source,
                templates_dir=settings_module.templates_path()
                )
        except settings_module.SettingsError as e:
            raise self.Error(str(e))

        print(f"settings directory: {self.settings_dir}")
        for path in created:
            print(f"  created {path.relative_to(self.settings_dir)}")
        print("Copy templates up a level (or merge them into settings.json) and edit them;")
        print("files in templates/ are never loaded.")
        return 0

    def _run_check_settings(self) -> int:
        settings = self.settings
        builtin = self._builtin_settings_path(self.settings_args)

        def label(path: pathlib.Path) -> str:
            if path == builtin:
                return "built-in" if self.settings_args.builtin_settings is None else str(path)
            if path.parent == self.settings_dir:
                return path.name
            return str(path)

        print(f"settings directory: {self.settings_dir}")
        print("loaded:")
        for path in settings.sources:
            print(f"  {path}")

        for category in settings_module.CATEGORIES:
            entries = settings[category]
            print(f"{category}: ({len(entries)})")
            if len(entries) == 0:
                continue
            width = max(len(name) for name in entries)
            for name in entries:
                print(f"  {name:<{width}}  {label(settings.origin(category, name))}")

        print("defaults:")
        for category, name in settings.defaults.items():
            print(f"  {category}: {name}")

        problems = settings.check()
        if len(problems) == 0:
            print("no problems found")
            return 0
        print(f"{len(problems)} problem(s):")
        for problem in problems:
            print(f"  {problem}")
        return 1

    def _initialize(self):
        self.log.debug("App.initialize called")
        self.outputDir = self.args.dir
        if not self.outputDir.exists():
            raise self.Error("Output directory does not exist: " + str(self.outputDir) + " -- either create it or use the -d switch to select a different one")
        self._check_input_files()

    #
    # Make sure every file named on the command line actually exists.
    # This catches the common case of a shell glob that matched nothing:
    # the shell hands us the pattern itself, and without this check the
    # problem doesn't surface until frame-to-file assignment fails with
    # a much less obvious complaint.
    #
    def _check_input_files(self):
        missing = [ f for f in self.args.input_files if not f.exists() ]
        if len(missing) == 0:
            return

        lines = [ f"{len(missing)} of {len(self.args.input_files)} input files do not exist:" ]
        lines += [ f"  {f}" for f in missing ]
        if any(c in str(f) for f in missing for c in "*?["):
            lines.append("one or more names still contain shell wildcards, so the pattern")
            lines.append("didn't match anything -- check the directory and the extension")
            lines.append("(.tif vs .tiff, .jpg vs .jpeg, case) before rerunning")
        raise self.Error("\n".join(lines))

    #######################
    # parse the arguments #
    #######################
    def _parse_arguments(self, settings_parser: argparse.ArgumentParser, argv: list[str]):
        constants = self.constants
        settings = self.settings
        defaults = settings.defaults
        parser = argparse.ArgumentParser(
            prog="annotate_film_scans",
            description="Annotate film scans, coping and numbering appropriately",
            parents=[settings_parser],
            # do not allow abbreviations -- you might break batch files
            allow_abbrev=False
            )
        parser.add_argument(
            "--version",
            action='version',
            help="Print version and exit",
            version="%(prog)s v"+__version__
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
            default=defaults.get("camera"),
            choices=settings['camera'],
            help="camera that took image (default: %(default)s)"
            )
        parser.add_argument(
            "--lens",
            default=defaults.get("lens"),
            choices=settings['lens'],
            help="lens used for image (default: %(default)s)"
        )
        parser.add_argument(
            "--film",
            default=defaults.get("film"),
            choices=settings['film'],
            help="film used for image (default: %(default)s)"
        )
        parser.add_argument(
            "--lab",
            default=defaults.get("lab"),
            choices=settings['lab'],
            help="lab used for image (default: %(default)s)"
        )
        parser.add_argument(
            "--process",
            default=defaults.get("process"),
            choices=settings['process'],
            help="process used for image (default: %(default)s)"
        )
        parser.add_argument(
            "--author",
            default=defaults.get("author"),
            choices=settings['author'],
            help="author/rights for image (default: %(default)s)"
        )
        parser.add_argument(
            "--roll",
            help="Roll ID"
        )
        parser.add_argument(
            "--time-delta", "-T",
            metavar="{time-delta}",
            dest = "timedelta",
            help="Assumed interval between shots in frame sequences (in seconds) (default %(default)d)",
            default=30,
            type=int
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
        parser.add_argument(
            "--developer",
            metavar="{developer_name}",
            default=defaults.get("developer"),
            help="developer (if known)"
        )
        parser.add_argument(
            "--development_time",
            dest="devtime",
            metavar="{devtime}",
            help="development time in minutes:seconds"
        )
        parser.add_argument(
            "--development_temperature",
            dest="devtemp",
            metavar="{devtemp}",
            help="development temperature, degrees C"
        )
        parser.add_argument(
            "--development_notes",
            dest="devnotes",
            metavar="{notes}",
            help="Any development notes"
        )

        # parse the args, and return
        args = parser.parse_args(argv)

        # expand the args
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
        return self.command()

    def _run_annotate(self) -> int:
        def to_int(row: dict, field: str) -> int:
            result = None
            try:
                result = int(row[field])
            except Exception as e:
                raise self.Error(f"Not an int: {field=}[{row[field]}] line={row['line_num']}: {e}")
            return result

        args = self.args

        # read the shot-info file
        info = []
        shot_info_object = ShotInfoFile(self)
        info = shot_info_object.read_from_path(pathlib.Path(args.shot_info_file).expanduser())

        input_files = args.input_files
        if not args.forward:
            list.reverse(input_files)

        self.log.debug(f"{input_files=}")
        self.log.debug(f"{len(input_files)=}")

        # build the attributes
        # some of these are built up in the ShotInfoFile processing, so
        # we don't repeat them here.
        attributes = dict()
        for item in {
                        # "camera": args.camera,
                        # "lens": args.lens,
                        # "film": args.film,
                        # "process": args.process,
                        # "lab": args.lab,
                        "author": args.author
                    }.items():
            if item[1] != None:
                setting = self.settings[item[0]][item[1]]
                self.log.debug("update: %s -> %s: %s", item[0], item[1], setting)
                attributes.update(setting)

        # fix author attributes
        if args.author != None:
            self._fix_author(attributes)
        else:
            self._warn("no author set, so no creator or copyright is written; use --author, or set defaults.author in your settings")

        # display what we've done.
        self.log.debug("attributes: %s", attributes)

        # we need to know the first index in the table!
        iFirstFrame,_ = sorted(info.items())[0]
        iShot = iFirstFrame - 1

        # copy files, renaming. manually index through the shots
        for i in range(len(input_files)):
            frame_info = None
            # skipping shots requires an explicit entry
            # where exposure is "skip".
            while True:
                iShot = iShot + 1
                if iShot in info:
                    frame_info = info[iShot]
                    self.log.debug("info[%d]=%s", iShot, frame_info)
                    if not (self.constants.TAG_SKIP in frame_info):
                        break
                else:
                    # in case we were looping
                    frame_info = None
                    break

            #
            # input_files[] is the list of input files from the command line, in the order
            # they appear on the command line.
            #
            # If frame_info == info[iShot] has a Files column, use that to get the input file.
            # If not, if forward use `i`; if reverse use len(input_files) - i - 1.
            #
            assert "file" in frame_info
            iFile = to_int(frame_info, "file") - 1

            inpath = input_files[iFile]
            base_inpath = inpath.name
            outpath = self.outputDir / f"{(iShot):03d}-{base_inpath}"
            self.log.debug("%d: %s -> %s", i, str(inpath), str(outpath) )

            # copy the file

            self._copy(inpath, outpath, copy.copy(attributes), frame_info)
            # self.log.info("/bin/cp -p %s %s", str(inpath), str(outpath) )
            # subprocess.run([ "/bin/cp", "-p", str(inpath), str(outpath)], check=True)

        return 0

    #
    # Supply missing author attributes as needed.
    #
    # Sort of unsurprisingly, all kinds of odd fields are treated as the author
    # name, depending on the whim of the photo tool. It's tedious to remember
    # all the places, so we supply them here.
    #
    def _fix_author(self, attributes: dict) -> None:
        def copy_value(key: str, value: str) -> None:
            if key in attributes:
                pass
            else:
                attributes[key] = value

        name = attributes.get("XMP:Creator")
        if name == None:
            raise self.Error('Settings "author" must contain XMP:Creator as author name')
        rights = attributes.get("XMP:Rights")
        if rights == None:
            raise self.Error('Settings "author" must contain XMP:Rights')

        if not "EXIF:Copyright" in attributes:
            attributes["EXIF:Copyright"] = f"Copyright {name}".strip()

        # XMP:Creator and XMP:Rights are already dc:creator and dc:rights;
        # adding XMP-dc: copies duplicates the creator.
        copy_value("IFD0:Artist", name)

    def _copy(self, inpath: pathlib.Path, outpath: pathlib.Path, settings, frame_settings):
        def _replace_settings(name: str, value: str | None = None) -> None:
            if name in settings:
                settings["XMP-AnnotateFilmScans-Scanner-" + name] = settings[name]
                del settings[name]
            if value != None:
                settings[name] = value

        if frame_settings != None:
            settings.update(frame_settings)

        # Unfortunately, for Sony ARW files, we need to keep make/model unchanged.
        # This seems to be true for Panasonic RW2 files.
        #
        # Luckily, this is only true for negatives
        scanner_json = self._read_make_model(inpath)

        keepMake = False
        match inpath.suffix.lower():
            case ".arw":
                keepMake = True
            case ".rw2":
                keepMake = True
            case ".dng":
                # Sony DNGs get squirrely if the Make doesn't say "SONY"
                # This might also be true for Panasonic, haven't tried yet.
                if settings["IFD0:Make"] == "SONY":
                    keepMake = True

        if keepMake:
            settings["XMP-AnnotateFilmScans:Make"] = settings["IFD0:Make"]
            settings["XMP-AnnotateFilmScans:Model"] = settings["IFD0:Model"]
            del settings["IFD0:Make"]
            del settings["IFD0:Model"]
        else:
            if "Make" in scanner_json:
                settings["XMP-AnalogExif:ScannerMaker"] = scanner_json["Make"]
            if "Model" in scanner_json:
                settings["XMP-AnalogExif:Scanner"] = scanner_json["Model"]

        # Preserve the scan time as DateTimeDigitized. This used to be done
        # with a "-XMP-exif:DateTimeDigitized<XMP:CreateDate" redirect, but
        # exiftool 13.41 changed how tag arguments interact with -json=, so
        # put the value in the JSON instead.
        if "CreateDate" in scanner_json:
            settings["XMP-exif:DateTimeDigitized"] = scanner_json["CreateDate"]

        # now, set other settings
        if settings.get("EXIF:FocalLength") != None and settings.get("EXIF:MaxApertureValue") != None:
            _replace_settings("XMP-aux:LensInfo",
                            f"{settings["EXIF:FocalLength"].removesuffix("mm").strip().removesuffix(".00")}mm f/{settings["EXIF:MaxApertureValue"]}"
                            )
        _replace_settings("XMP-aux:Lens",
                          f"{settings["XMP:LensManufacturer"]} {settings["XMP:LensModel"]}"
                          )
        if settings.get("XMP-aux:LensInfo") != None:
            _replace_settings("ExifIFD:LensInfo",
                            settings["XMP-aux:LensInfo"]
                            )
        _replace_settings("ExifIFD:LensModel",
                          settings["XMP-aux:Lens"])

        self._analogexif_to_comment(settings)

        json_settings_str = json.dumps(settings, indent=2)
        args = [
                *self._exiftool(),
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
        pattern = re.compile(r"(XMP-AnalogExif|Exif|XMP|ExifIFD|XMP-AnnotateFilmScans):(.*)", flags=re.IGNORECASE)
        comment_dict = dict()
        for item in settings.items():
            key = item[0]
            match = re.fullmatch(pattern, key)
            if match != None and match.group(2) != "UserComment":
                # add to the comment
                comment_dict[match.group(2)] = str(item[1]).strip()

        comment = "Photo information: \n"
        for key in sorted(comment_dict):
            comment += f"\t{key}: {comment_dict[key]}. \n"

        settings["IFD0:XPComment"] = comment
        settings["ExifIFD:UserComment"] = comment
        return settings

    # exiftool command prefix; -config must be the first argument.
    def _exiftool(self) -> list[str]:
        return [ "exiftool", "-config", str(self.exiftool_config) ]

    def _read_make_model(self, inpath):
        args = [ *self._exiftool(), "-json", "-s", "-make", "-model", "-XMP:CreateDate", str(inpath) ]

        self.log.info(" ".join(args))
        subprocess_result = subprocess.run(args, capture_output=True, check=True, text=True)
        result = json.loads(subprocess_result.stdout)[0]
        self.log.debug("_read_make_model: %s", result)
        return result
