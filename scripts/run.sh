#!/bin/bash
python3.9 -m pip install --user -r ../jobs_launcher/install/requirements.txt

RETRIES=${3:-2}
UPDATE_REFS=${4:-No}

python3.9 ../jobs_launcher/executeTests.py --test_filter $2 --file_filter $1 --tests_root ../jobs --work_root ../Work/Results --work_dir RprViewer --cmd_variables Tool "../RprViewer/RprViewer" ResPath "$CIS_TOOLS/../TestResources/rpr_viewer_autotests_assets" retries $RETRIES UpdateRefs $UPDATE_REFS