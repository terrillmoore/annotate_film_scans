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
                "comment"
        }