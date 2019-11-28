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

ROOT_DIR_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir))
sys.path.append(ROOT_DIR_PATH)
from jobs_launcher.core.config import *
from jobs_launcher.core.system_info import get_gpu

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
    if 'uiConfig' in test.keys():
        tmp['uiConfig'] = os.path.normpath(os.path.join(scene_path, test['uiConfig']))

    with open(os.path.join(render_path, "config.json"), 'w') as file:
        json.dump(tmp, file, indent=4)

    return frame_exit_after


def main():
    args = create_args_parser()

    with open(args.tests_list, 'r') as file:
        try:
            tests_list = json.loads(file.read())
        except json.decoder.JSONDecodeError as err:
            main_logger.error(str(err))
            exit(1)

    # TODO: remove code duplicate
    # remove old images
    old_images = [x for x in os.listdir(args.render_path) if os.path.isfile(x) and x.startswith('img0')]
    main_logger.info(os.listdir(args.render_path))
    if old_images:
        main_logger.info("Detected old renderer: {}".format(str(old_images)))
    for img in old_images:
        try:
            os.remove(os.path.join(args.render_path, img))
        except OSError as err:
            main_logger.error(str(err))

    if not os.path.exists(os.path.join(args.output_dir, "Color")):
        os.makedirs(os.path.join(args.output_dir, "Color"))

    # TODO: try-catch on file reading
    if not os.path.exists(os.path.join(args.render_path, 'config.original.json')):
        shutil.copyfile(os.path.join(args.render_path, 'config.json'),
                        os.path.join(args.render_path, 'config.original.json'))
    with open(os.path.join(args.render_path, 'config.original.json'), 'r') as file:
        config_tmp = json.loads(file.read())

    render_device = get_gpu()

    main_logger.info("Creating predefined errors json...")

    for test in tests_list:
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
                os.path.join(ROOT_DIR_PATH, 'jobs_launcher', 'common', 'img', report['test_status'] + test['file_ext']),
                os.path.join(args.output_dir, 'Color', test['name'] + test['file_ext']))
        except OSError or FileNotFoundError as err:
            main_logger.error("Can't create img stub: {}".format(str(err)))

        with open(os.path.join(args.output_dir, test["name"] + CASE_REPORT_SUFFIX), "w") as file:
            json.dump([report], file, indent=4)

    for test in [x for x in tests_list if x['status'] == 'active']:
        main_logger.info("Processing test case: {}".format(test['name']))

        frame_ae = str(update_viewer_config(
            test=test,
            engine=args.render_engine,
            render_path=args.render_path,
            scene_path=args.scene_path,
            tmp=config_tmp
        ))

        # remove old images
        old_images = [x for x in os.listdir(args.render_path) if os.path.isfile(os.path.join(args.render_path, x)) and x.startswith('img0')]
        main_logger.info(os.listdir(args.render_path))
        if old_images:
            main_logger.info("Detected old renderer: {}".format(str(old_images)))
        for img in old_images:
            try:
                os.remove(os.path.join(args.render_path, img))
            except OSError as err:
                main_logger.error(str(err))

        os.chdir(args.render_path)
        if platform.system() == 'Windows':
            viewer_run_path = os.path.normpath(os.path.join(args.render_path, "RadeonProViewer.exe"))
        elif platform.system() == 'Linux':
            viewer_run_path = os.path.normpath(os.path.join(args.render_path, "RadeonProViewer"))
        p = psutil.Popen(viewer_run_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stderr, stdout = b"", b""
        start_time = time.time()
        test_case_status = TEST_CRASH_STATUS

        try:
            stdout, stderr = p.communicate(timeout=test['render_time'])
        except (TimeoutError, psutil.TimeoutExpired, subprocess.TimeoutExpired) as err:
            main_logger.error("Aborted by timeout. {}".format(str(err)))
            for child in reversed(p.children(recursive=True)):
                child.terminate()
            p.terminate()
        else:
            test_case_status = TEST_SUCCESS_STATUS
        finally:
            render_time = time.time() - start_time
            try:
                shutil.copyfile(os.path.join(args.render_path, 'img{0}{1}'.format(frame_ae.zfill(4), test['file_ext'])),
                            os.path.join(args.output_dir, 'Color', test['name'] + test['file_ext']))
            except FileNotFoundError as err:
                main_logger.error("Image {} not found".format('img{0}{1}'.format(frame_ae.zfill(4), test['file_ext'])))
                main_logger.error(str(err))
                test_case_status = TEST_CRASH_STATUS

            with open(os.path.join(args.output_dir, test['name'] + '_app.log'), 'w') as file:
                file.write("-----[STDOUT]------\n\n")
                file.write(stdout.decode("UTF-8"))
            with open(os.path.join(args.output_dir, test['name'] + '_app.log'), 'a') as file:
                file.write("\n-----[STDERR]-----\n\n")
                file.write(stderr.decode("UTF-8"))

            # Up to date test case status
            with open(os.path.join(args.output_dir, test['name'] + CASE_REPORT_SUFFIX), 'r') as file:
                test_case_report = json.loads(file.read())[0]
                test_case_report["test_status"] = test_case_status
                test_case_report["render_time"] = render_time
                test_case_report["render_color_path"] = "Color/" + test_case_report["file_name"]
                test_case_report["render_log"] = test['name'] + '_app.log'

            with open(os.path.join(args.output_dir, test['name'] + CASE_REPORT_SUFFIX), 'w') as file:
                json.dump([test_case_report], file, indent=4)

    return 0


if __name__ == "__main__":
    exit(main())
