set PATH=c:\python35\;c:\python35\scripts\;%PATH%

python ..\jobs_launcher\executeTests.py --tests_root ..\jobs --work_root ..\Work\Results --work_dir RprViewer --cmd_variables Tool "..\\RprViewer\\RprViewer.exe" ResPath "C:\\TestResources\\RprViewer"
