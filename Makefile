##############################################################################
#
# File: Makefile
#
# Purpose:
#	Various automated procedures for this directory
#
# Copyright notice and license:
#	See LICENSE.md in this directory.
#
# Author:
#	Terry Moore, MCCI Corporation   July 2024
#
# Notes:
#	This makefile is written for Gnu Make, and has been tested on
#	macOS and on Windows (using git bash and Gnu Make installed using
#	scoop.sh).
#
##############################################################################

# find the address of this makefile
THIS_MAKEFILE_PATH := $(realpath $(dir $(lastword $(MAKEFILE_LIST))))

# figure out where Python virtual env executable artifacts live on this system
ifeq ($(OS),Windows_NT)
 VENV_SCRIPTS=Scripts
else
 VENV_SCRIPTS=bin
endif

# based on this, set the path to the bash activate script.
ACTIVATE=${VENV_SCRIPTS}/activate

# the default python
PYTHON=python3

# the python for VENVs
PYTHON_VENV=python

# names of the uv executable, in case we need to override.
UV=uv
UVX=uvx

ifeq ($(MAKE_VERSION),)
 $(error This makefile requires GNU make v4.4.1 or later)
endif

ifneq (4.4.1, $(firstword $(sort ${MAKE_VERSION} 4.4.1)))
 $(error $(shell printf "%s\n" 'This makefile requires a newer version of GNU make than ${MAKE_VERSION}.' \
						'If using macOS, the default make is quite old, and should be ugraded using' \
						'"brew install make", which will install a newer make as "gmake"' | fmt))
endif

# figure out our project name
THIS_PROJECT != $(UVX) --from toml-cli toml.exe get --toml-path ${THIS_MAKEFILE_PATH}/pyproject.toml project.name

#
# Default target: print help.
#
help:
	@printf "%s\n" \
		"This Makefile contains the following targets for ${THIS_PROJECT}:" \
		"" \
		"* make help      -- prints this message" \
		"* make build     -- builds the app (in dist) using uv" \
		"* make venv      -- sets up the virtual env for development (optional)" \
		"* make clean     -- get rid of build artifacts" \
		"* make distclean -- like clean, but also removes distribution directory" \
		"" \
		"On this system, virtual env scripts are in {envpath}/${VENV_SCRIPTS}" \
		"" \
		"We are using uv, so you don't need to activate a venv to run the tool:" \
		"   ${UV} run ${THIS_PROJECT} {args}" \
		"or (original style):" \
		"   ${UV} run python ${subst -,_,${THIS_PROJECT}} {args}" \
		"will do the job."

build:
	$(UV) build
	@# deliberately don't add `|| true` at the end because printf and ls failures
	@# indicate a serious problem.
	@printf "%s\n" "distribution files are in the dist directory:" && ls dist

#
# targets for local development:
#    .venv creates the virtual environment and installs requirements
#    venv does the same, but tells you how to use the venv.
#
#    We're using uv, so this is all optional.
#
.venv:
	$(UV) venv .venv

venv:	.venv
	@printf "%s\n" \
		"Virtual environment created in .venv." \
		"" \
		"To activate in bash, say:" \
		"    source .venv/${ACTIVATE}" \
		"" \
		"Or simply run without activation:" \
		"    $(UV) run ${THIS_PROJECT} {args}"
	@if [ "${PYTHON_VENV}" != "${PYTHON}" ]; then \
		printf "%s\n" \
			"If running without ${UV}, be sure to run the app using ${PYTHON_VENV} (not ${PYTHON})" \
			"" \
		; \
	fi

clean:
	rm -rf .venv *.egg-info */__pycache__

distclean:	clean
	rm -rf dist

#### end of file ####
