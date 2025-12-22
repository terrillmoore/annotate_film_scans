##############################################################################
#
# Name: __version__.py
#
# Function:
#       Contains the package version (only)
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

# use the version from pyproject.toml:
from importlib.metadata import version as _version
__version__ = _version("annotate_film_scans")
