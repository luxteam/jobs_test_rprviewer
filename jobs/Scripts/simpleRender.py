import argparse
import sys
import os
import subprocess
import psutil
import ctypes
import json
import shutil
import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from jobs_launcher.core.config import main_logger, RENDER_REPORT_BASE
import datetime


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


def create_args_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tests_list', required=True, metavar="<path>")
    parser.add_argument('--output_dir', required=True)
    parser.add_argument('--render_engine', required=True)
    parser.add_argument('--scene_path', required=True)
    parser.add_argument('--render_path', required=True, metavar="<path>")
    parser.add_argument('--test_group', required=True)
    return parser.parse_args()


def update_viewer_config(test, engine, scene_path, render_path, tmp, frame_exit_after=3, iterations_per_frame=10, save_frames='yes'):
    # Refresh Viewer config for test case
    tmp.update(test['config_parameters'])
    tmp['engine'] = engine
    tmp['iterations_per_frame'] = iterations_per_frame
    tmp['save_frames'] = save_frames
    tmp['frame_exit_after'] = frame_exit_after
    tmp['scene']['path'] = os.path.normpath(os.path.join(scene_path, test['scene_sub_path']))

    with open(os.path.join(render_path, "config.json"), 'w') as file:
        json.dump(tmp, file, indent=4)

    return frame_exit_after


def pre_render(test, args, render_device, suite=None):
    ''' function make json report with '''
    status, r = ("skipped", True) if test["status"] == "skipped" else ("failed", False)

    # Create IMG in /Color
    main_logger.info(args.output_dir)
    shutil.copyfile(os.path.join(args.output_dir, '../../../../../jobs/Tests/{0}.jpg'.format(status)), os.path.join(args.output_dir, 'Color/{0}.png'.format(test["name"])))

    # Create JSON
    template_report = RENDER_REPORT_BASE
    template_report["test_status"] = status
    template_report["test_case"] = test["name"]
    template_report["scene_name"] = test["scene_sub_path"]
    template_report["render_device"] = render_device
    template_report['tool'] = args.render_engine
    template_report['file_name'] = test['name'] + test['file_ext']
    template_report['date_time'] = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")

    # TODO: Add script info in json
    template_report["script_info"] = test["script_info"]
    # TODO: Add group name
    template_report["test_group"] = suite

    with open(os.path.join(args.output_dir, '{0}_RPR.json'.format(test["name"])), "w") as file:
        json.dump([template_report], file, indent=4)

    return r


# TODO: add logger
def main():
    args = create_args_parser()
    
    try:
        s = subprocess.Popen("wmic path win32_VideoController get name", stdout=subprocess.PIPE)
        stdout = s.communicate()
        render_device = stdout[0].decode("utf-8").split('\n')[1].replace('\r', '').strip(' ')
    except:
        render_device = "undefined"

    tests_list = {}
    with open(args.tests_list, 'r') as file:
        tests_list = json.loads(file.read())

    if not os.path.exists(os.path.join(args.output_dir, "Color")):
        os.makedirs(os.path.join(args.output_dir, "Color"))

    if not os.path.exists(os.path.join(args.render_path, 'config.original.json')):
        shutil.copyfile(os.path.join(args.render_path, 'config.json'), os.path.join(args.render_path, 'config.original.json'))
    with open(os.path.join(args.render_path, 'config.original.json'), 'r') as file:
        config_tmp = json.loads(file.read())

    # imgui_ini = os.path.join(args.render_path, 'imgui.ini')
    # if os.path.exists(imgui_ini):
    #     os.remove(imgui_ini)
    #     shutil.copyfile(os.path.join(os.path.dirname(__file__), 'imgui.ini'), imgui_ini)

    for test in tests_list:
        # if function pre_render return true, then test case has skipped status
        if pre_render(test, args, render_device, suite=args.test_group):
            continue

        main_logger.info("Processing test: {}".format(test['name']))

        frame_ae = str(update_viewer_config(
                    test=test,
                    engine=args.render_engine,
                    render_path=args.render_path,
                    scene_path=args.scene_path,
                    tmp=config_tmp
                ))

        # Run RPRViewer
        os.chdir(args.render_path)
        p = psutil.Popen([os.path.normpath(os.path.join(args.render_path, "RadeonProViewer.exe"))],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        stdout, stderr = b"", b""
        start_time = time.time()
        try:
            stdout, stderr = p.communicate(timeout=test['render_time'])
        except subprocess.TimeoutExpired:
            # if app works during 'render_time' - mark test as passed
            try:
                test_case_status = 'error'
            except Exception:
                pass

            for child in reversed(p.children(recursive=True)):
                child.terminate()
            p.terminate()
        else:
           test_case_status = 'passed'
        finally:
            render_time = time.time() - start_time
            try:
                shutil.move(os.path.join(args.render_path, 'img{0}.png'.format('0' * (4-len(frame_ae)) + frame_ae)), os.path.join(args.output_dir, 'Color', test['name'] + '.png'))
            except FileNotFoundError:
                main_logger.error("Image not found")
                test_case_status = 'error'

            # with open(os.path.join(args.output_dir, test['name'] + '_app.log'), 'w') as file:
            with open(os.path.join(args.output_dir, 'renderTool.log'), 'w') as file:
                file.write("[STDOUT]\n\n")
                file.write(stdout.decode("UTF-8"))
            # with open(os.path.join(args.output_dir, test['name'] + '_app.log'), 'a') as file:
            with open(os.path.join(args.output_dir, 'renderTool.log'), 'a') as file:
                file.write("\n[STDERR]\n\n")
                file.write(stderr.decode("UTF-8"))

            # Up to date test case status
            # TODO: Add render time
            with open(os.path.join(args.output_dir, test['name'] + '_RPR.json'), 'r') as file:
                test_case_report = json.loads(file.read())[0]
                test_case_report["test_status"] = test_case_status
                test_case_report["render_time"] = render_time
                test_case_report["render_color_path"] = "Color/" + test_case_report["file_name"]
            
            with open(os.path.join(args.output_dir, test['name'] + '_RPR.json'), 'w') as file:
                json.dump([test_case_report], file, indent=4)

    return 0


if __name__ == "__main__":
    exit(main())
