##############################################################################
#
# Name: __main__.py
#
# Function:
#       Entry point for main command
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

#### imports ####
import sys

from . import app as app
from .constants import Constants

##############################################################################
#
# The main program
#
##############################################################################

def main_inner() -> int:
    global gApp

    # create an app object
    try:
        gApp = app.App()
    except:
        print("app creation failed!")
        raise

    gApp.log.debug("launching app")
    return gApp.run()

def main() -> int:
    try:
        return main_inner()
    except KeyboardInterrupt:
        print("Exited due to keyboard interrupt")

if __name__ == '__main__':
    sys.exit(main())
