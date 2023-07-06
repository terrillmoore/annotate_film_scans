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
                "process"
        }

        re_fstop = r"f/(\d+(\.\d*)?)"

        TAG_SKIP = "XMP-AnnotateFilmScans:Skip"
        TAG_CROP_FACTOR = "XMP-AnnocateFilmScans:CropFactor"