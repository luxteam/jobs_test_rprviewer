#!/bin/bash
python3 -m pip install -r ../jobs_launcher/install/requirements.txt

RETRIES=${3:-2}

python3 ../jobs_launcher/executeTests.py --test_filter $2 --file_filter $1 --tests_root ../jobs --work_root ../Work/Results --work_dir RprViewer --cmd_variables Tool "../RprViewer/RprViewer" ResPath "$CIS_TOOLS/../TestResources/RprViewer" retries $RETRIES