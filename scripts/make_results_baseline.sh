#!/bin/bash
DELETE_BASELINES=${1:False}

python ../jobs_launcher/common/scripts/generate_baselines.py --results_root ../Work/Results/RprViewer --baseline_root ../Work/Baseline --remove_old $DELETE_BASELINES
