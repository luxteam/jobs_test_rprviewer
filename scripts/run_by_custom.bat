set PATH=c:\python35\;c:\python35\scripts\;%PATH%
python -m pip install -r ..\jobs_launcher\install\requirements.txt

python ..\jobs_launcher\executeTests.py --tests_root ..\jobs --file_filter "" --test_filter "Resolution" --work_root ..\Work\Results --work_dir RprViewer --cmd_variables Tool "D:\\Galkin\\Projects\\RprViewer\\RadeonProViewer.exe" ResPath "C:\\TestResources\\RprViewer"
