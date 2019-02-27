import argparse
import sys
import os
import subprocess
import psutil
import ctypes
import json
import shutil
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from jobs_launcher.core.config import main_logger
import report_sceleton
import datetime
import pyautogui


def get_windows_titles():
    EnumWindows = ctypes.windll.user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
    GetWindowText = ctypes.windll.user32.GetWindowTextW
    GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
    IsWindowVisible = ctypes.windll.user32.IsWindowVisible

    titles = []

    def foreach_window(hwnd, lParam):
        if IsWindowVisible(hwnd):
            length = GetWindowTextLength(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            GetWindowText(hwnd, buff, length + 1)
            titles.append(buff.value)
        return True

    EnumWindows(EnumWindowsProc(foreach_window), 0)

    return titles


def createArgsParser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tests_list', required=True, metavar="<path>")
    parser.add_argument('--output_dir', required=True)
    parser.add_argument('--render_engine', required=True)
    parser.add_argument('--scene_path', required=True)
    parser.add_argument('--render_path', required=True, metavar="<path>")
    return parser.parse_args()


# TODO: add logger
def main():
    args = createArgsParser()

    tests_list = {}
    with open(args.tests_list, 'r') as file:
        tests_list = json.loads(file.read())

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    with open(os.path.join(os.path.dirname(__file__), 'config.json'), 'r') as file:
        config_template = json.loads(file.read())

    imgui_ini = os.path.join(args.render_path, 'imgui.ini')
    if os.path.exists(imgui_ini):
        os.remove(imgui_ini)
        shutil.copyfile(os.path.join(os.path.dirname(__file__), 'imgui.ini'), imgui_ini)

    for test in tests_list:
        if test['status'] == 'active':
            main_logger.info("Processing test: {}".format(test['name']))

            test_report = report_sceleton.report
            test_report['tool'] = args.render_engine
            test_report['test_case'] = test['name']
            test_report['render_color_path'] = test['name'] + test['file_ext']
            try:
                s = subprocess.Popen("wmic path win32_VideoController get name", stdout=subprocess.PIPE)
                stdout = s.communicate()
                test_report['render_device'] = stdout[0].decode("utf-8").split('\n')[1].replace('\r', '').strip(' ')
            except:
                pass
            test_report['render_time'] = 1
            test_report['test_status'] = 'failed'
            test_report['date_time'] = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")

            config_template['engine'] = args.render_engine
            config_template['scene']['path'] = os.path.normpath(os.path.join(args.scene_path, test['scene_sub_path']))
            config_template['animation'] = test['animation']

            with open(os.path.join(args.render_path, "config.json"), 'w') as file:
                json.dump(config_template, file)

            os.chdir(args.render_path)
            p = psutil.Popen([os.path.normpath(os.path.join(args.render_path, "RadeonProViewer.exe"))],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            stdout, stderr = b"", b""
            try:
                stdout, stderr = p.communicate(timeout=test['render_time'])
            except subprocess.TimeoutExpired:
                # if app works during 'render_time' - mark test as passed
                try:
                    test_report['test_status'] = 'passed'
                    # FIX: region coordinates
                    app_image = pyautogui.screenshot(os.path.normpath(os.path.join(args.output_dir, test['name'] + test['file_ext'])),
                                                     region=(50, 50, 1580, 1068))
                except Exception:
                    pass

                for child in reversed(p.children(recursive=True)):
                    child.terminate()
                p.terminate()
            else:
                test_report['test_status'] = 'error'
            finally:
                with open(os.path.join(args.output_dir, test['name'] + '_app.log'), 'w') as file:
                    file.write("[STDOUT]\n\n")
                    file.write(stdout.decode("UTF-8"))
                with open(os.path.join(args.output_dir, test['name'] + '_app.log'), 'a') as file:
                    file.write("\n[STDERR]\n\n")
                    file.write(stderr.decode("UTF-8"))

            with open(os.path.join(args.output_dir, test['name'] + '_RPR.json'), 'w') as file:
                json.dump([test_report], file, indent=4)

    return 0


if __name__ == "__main__":
    exit(main())
