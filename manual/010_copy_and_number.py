#!/usr/bin/env python3

import argparse
import pathlib
import subprocess
import sys

##############################################################################
#
# The argument parser
#
##############################################################################

def ParseArguments():
    parser = argparse.ArgumentParser(
        prog="010_copy_and_number",
        description="Copy and number exposure scans appropriately",
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
        "input_files",
        metavar="{InputFile}",
        nargs="+",
        help="Name of an input file, generally a pattern ending in .jpg"
        )

    # parse the args, and return
    args = parser.parse_args()
    args.input_files = [ pathlib.Path(iArg).expanduser() for iArg in args.input_files ]
    args.dir = pathlib.Path(args.dir).expanduser()
    return args

def main_inner() -> int:
    args = ParseArguments()
    verbose = args.verbose
    input_files = sorted(args.input_files, reverse=not args.forward)
    if verbose > 1:
        print(input_files)
        print(f"{len(input_files)=}")

    # check output directory
    if not args.dir.is_dir():
        print(f"Not a directory: {str(args.dir)}")
        return 1

    # copy files, renaming
    for i in range(len(input_files)):
        inpath = input_files[i]
        base_inpath = inpath.name
        outpath = args.dir / f"{(i + 1):03d}-{base_inpath}"
        if verbose > 1:
            print(i, str(inpath), str(outpath))

        # copy the file
        if verbose > 0:
            print(f"/bin/cp -p {str(inpath)} {str(outpath)}")
        subprocess.run([ "/bin/cp", "-p", str(inpath), str(outpath)], check=True)

    return 0

def main() -> int:
    try:
        return main_inner()
    except KeyboardInterrupt:
        print("Exited due to keyboard interrupt")

if __name__ == '__main__':
    sys.exit(main())
