##############################################################################
#
# Name: constants.py
#
# Function:
#       Class for the immutable constants for this app
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

#### imports ####
import re
import uuid

#### The Constants class
class Constants:
        __slots__ = ()  # prevent changes

        shot_fields = {
                "frame",
                "frame2",
                "exposure",
                "aperture",
                "filter",
                "date",
                "time",
                "lens",
                "focallength",
                "comment",
                "camera",
                "film",
                "lab",
                "process",
                "roll",
                "file",
                "developer",
                "devtime",
                "devtemp",
                "devnotes"
        }

        re_fstop = r"f/(\d+(\.\d*)?)"
        re_exposure = r"(\d+)(((/\d+)|(\.\d+))?)"
        re_time_withtz = r"((\d\d?:\d\d)(:\d\d)?)(\+((\d\d)(\d\d)|(\d\d:\d\d)))?"
        re_time_minutes = r"(\d+)(:\d\d)?"
        re_temperature_c = r"(\d+)(\.\d*)?(c?)"
        TAG_SKIP = "XMP-AnnotateFilmScans:Skip"
        TAG_CROP_FACTOR = "XMP-AnnotateFilmScans:CropFactor"
        TAG_DEVELOPER = "XMP=AnnotateFilmScans:Developer"
        TAG_DEVELOP_TIME = "XMP-AnnotateFilmScans:DevelopmentTime"
        TAG_DEVELOP_TEMP = "XMP-AnnotateFilmScans:DevelopmentTemperature"
        TAG_DEVELOP_NOTES = "XMP-AnnotateFilmScans:DevelopmentNotes"