set PATH=c:\python35\;c:\python35\scripts\;%PATH%

set RBS_BUILD_ID=%3
set RBS_JOB_ID=%4
set RBS_URL=%5
set RBS_ENV_LABEL=%6
set IMAGE_SERVICE_URL=%7
set RBS_USE=%8

python -m pip install -r ..\jobs_launcher\install\requirements.txt

python ..\jobs_launcher\executeTests.py --tests_root ..\jobs --file_filter %1 --test_filter "%2" --work_root ..\Work\Results --work_dir RprViewer --cmd_variables Tool "..\\RprViewer\\RprViewer.exe" ResPath "C:\\TestResources\\RprViewer"
