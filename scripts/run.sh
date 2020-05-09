#!/bin/bash

RBS_BUILD_ID=$3
RBS_JOB_ID=$4
RBS_URL=$5
RBS_ENV_LABEL=$6
IMAGE_SERVICE_URL=$7
RBS_USE=$8

python3 -m pip install -r ../jobs_launcher/install/requirements.txt

python3 ../jobs_launcher/executeTests.py --test_filter $2 --file_filter $1 --tests_root ../jobs --work_root ../Work/Results --work_dir RprViewer --cmd_variables Tool "../RprViewer/RprViewer" ResPath "$CIS_TOOLS/../TestResources/RprViewer"