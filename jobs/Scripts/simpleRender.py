import argparse
import sys
import os
import subprocess
import psutil
import json
import shutil
import time
import datetime
import platform

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from jobs_launcher.core.config import *


def create_args_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tests_list', required=True, metavar="<path>")
    parser.add_argument('--output_dir', required=True)
    parser.add_argument('--render_engine', required=True)
    parser.add_argument('--scene_path', required=True)
    parser.add_argument('--render_path', required=True, metavar="<path>")
    parser.add_argument('--test_group', required=True)
    return parser.parse_args()


def update_viewer_config(test, engine, scene_path, render_path, tmp, frame_exit_after=3, iterations_per_frame=10,
                         save_frames='yes'):
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


def main():
    args = create_args_parser()

    # TODO: try-catch on file reading
    with open(args.tests_list, 'r') as file:
        tests_list = json.loads(file.read())

    if not os.path.exists(os.path.join(args.output_dir, "Color")):
        os.makedirs(os.path.join(args.output_dir, "Color"))

    if not os.path.exists(os.path.join(args.render_path, 'config.original.json')):
        shutil.copyfile(os.path.join(args.render_path, 'config.json'),
                        os.path.join(args.render_path, 'config.original.json'))
    with open(os.path.join(args.render_path, 'config.original.json'), 'r') as file:
        config_tmp = json.loads(file.read())

    if platform.system() == 'Windows':
        try:
            s = subprocess.Popen("wmic path win32_VideoController get name", stdout=subprocess.PIPE)
            stdout = s.communicate()
            render_device = stdout[0].decode("utf-8").split('\n')[1].replace('\r', '').strip(' ')
        except Exception as err:
            render_device = "undefined_" + platform.uname()[1]
            main_logger.error("Can't define GPU: {}".format(str(err)))
    else:
        render_device = "undefined_" + platform.uname()[1]

    for test in tests_list:
        main_logger.info("Creating predefined errors json...")
        # TODO: save scene name instead of scene sub path
        report = RENDER_REPORT_BASE.copy()
        report.update({'test_status': TEST_CRASH_STATUS if test['status'] == 'active' else TEST_IGNORE_STATUS,
                       'render_device': render_device,
                       'test_case': test['name'],
                       'scene_name': test['scene_sub_path'],
                       'tool': args.render_engine,
                       'file_name': test['name'] + test['file_ext'],
                       'date_time': datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
                       'script_info': test['script_info'],
                       'test_group': args.test_group,
                       'render_color_path': 'Color/' + test['name'] + test['file_ext']
                       })
        # TODO: refactor img paths
        try:
            shutil.copyfile(
                os.path.join(os.pardir, os.pardir, 'jobs_launcher', 'common', 'img', report['status'] + '.jpg'),
                os.path.join(args.output_dir, 'Color', test['name'] + test['file_ext']))
        except OSError or FileNotFoundError as err:
            main_logger.error("Can't create img stub: {}".format(str(err)))

        with open(os.path.join(args.output_dir, test["name"] + CASE_REPORT_SUFFIX), "w") as file:
            json.dump([report], file, indent=4)

    for test in tests_list:
        main_logger.info("Processing test case: {}".format(test['name']))

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
        except psutil.TimeoutExpired:
            test_case_status = TEST_CRASH_STATUS
            for child in reversed(p.children(recursive=True)):
                child.terminate()
            p.terminate()
        else:
            test_case_status = TEST_SUCCESS_STATUS
        finally:
            render_time = time.time() - start_time
            try:
                shutil.move(os.path.join(args.render_path, 'img{0}.{1}'.format(('0' * (4 - len(frame_ae)) + frame_ae),
                                         test['file_ext'])),
                            os.path.join(args.output_dir, 'Color', test['name'] + test['file_ext']))
            except FileNotFoundError:
                main_logger.error("Image {} not found".format(test['name'] + test['file_ext']))
                test_case_status = TEST_CRASH_STATUS

            with open(os.path.join(args.output_dir, test['name'] + '_app.log'), 'w') as file:
                # with open(os.path.join(args.output_dir, 'renderTool.log'), 'w') as file:
                file.write("-----[STDOUT]------\n\n")
                file.write(stdout.decode("UTF-8"))
            with open(os.path.join(args.output_dir, test['name'] + '_app.log'), 'a') as file:
                # with open(os.path.join(args.output_dir, 'renderTool.log'), 'a') as file:
                file.write("\n-----[STDERR]-----\n\n")
                file.write(stderr.decode("UTF-8"))

            # Up to date test case status
            with open(os.path.join(args.output_dir, test['name'] + CASE_REPORT_SUFFIX), 'r') as file:
                test_case_report = json.loads(file.read())[0]
                test_case_report["test_status"] = test_case_status
                test_case_report["render_time"] = render_time
                test_case_report["render_color_path"] = "Color/" + test_case_report["file_name"]

            with open(os.path.join(args.output_dir, test['name'] + CASE_REPORT_SUFFIX), 'w') as file:
                json.dump([test_case_report], file, indent=4)

    return 0


if __name__ == "__main__":
    exit(main())
