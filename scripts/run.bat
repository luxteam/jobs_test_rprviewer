set PATH=c:\python35\;c:\python35\scripts\;%PATH%
python -m pip install -r ..\jobs_launcher\install\requirements.txt

set RETRIES=%1
if not defined RETRIES set RETRIES=2

python ..\jobs_launcher\executeTests.py --tests_root ..\jobs --file_filter %1 --test_filter "%2" --work_root ..\Work\Results --work_dir RprViewer --cmd_variables Tool "..\\RprViewer\\RprViewer.exe" ResPath "C:\\TestResources\\RprViewer" retries %RETRIES%
