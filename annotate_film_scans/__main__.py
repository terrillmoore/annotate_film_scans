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
import re
import sys
import traceback

from . import app as app
from .constants import Constants
from .shotinfo import ShotInfoFile

PROGNAME = "annotate-film-scans"

##############################################################################
#
# The main program
#
##############################################################################

#
# Count -v/--verbose in the raw argv. We need to know whether the user
# asked for debug output before the App (and hence argparse) exists, so
# that failures during startup can be reported the same way as failures
# later on.
#
def _argv_verbosity(argv: list) -> int:
    result = 0
    for arg in argv:
        if arg == "--":
            break
        if arg == "--verbose":
            result += 1
        elif re.fullmatch(r"-v+", arg):
            result += len(arg) - 1
    return result

def main_inner() -> int:
    global gApp

    # create an app object
    gApp = app.App()

    gApp.log.debug("launching app")
    return gApp.run()

def main() -> int:
    want_traceback = _argv_verbosity(sys.argv[1:]) >= 3

    try:
        return main_inner()
    except KeyboardInterrupt:
        print("Exited due to keyboard interrupt", file=sys.stderr)
        return 130
    except (app.App.Error, ShotInfoFile.Error) as e:
        # these are user errors, not bugs: report them plainly. Dump the
        # traceback as well (first, so the message stays last) if the user
        # asked for debug-level verbosity.
        if want_traceback:
            traceback.print_exc()
        print(f"{PROGNAME}: error: {e}", file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
