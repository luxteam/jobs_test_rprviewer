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
import copy
from utils import is_case_skipped

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
    parser.add_argument('--retries', required=False, default=2, type=int)
    parser.add_argument('--update_refs', required=True)
    return parser.parse_args()


def update_viewer_config(test, engine, scene_path, render_path, tmp, frame_exit_after=3, iterations_per_frame=10,
                         save_frames=True):
    # Refresh Viewer config for test case
    tmp['engine'] = engine
    tmp['iterations_per_frame'] = iterations_per_frame
    tmp['save_frames'] = save_frames
    tmp['frame_exit_after'] = frame_exit_after
    tmp['scene']['path'] = os.path.normpath(os.path.join(scene_path, test['scene_sub_path']))

    tmp.update(test['config_parameters'])
    if 'uiConfig' in test.keys():
        tmp['uiConfig'] = os.path.normpath(os.path.join(scene_path, test['uiConfig']))
    if 'upscaler' in test['config_parameters'].keys():
        if test['config_parameters']['upscaler']:
            if "rml_postprocessing" in tmp.keys():
                tmp['rml_postprocessing'][1]['disabled'] = False
                del tmp['upscaler']

    with open(os.path.join(render_path, "config.json"), 'w') as file:
        json.dump(tmp, file, indent=4)

    return tmp['frame_exit_after']


def main():
    args = create_args_parser()

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

    try:
        test_cases_path = os.path.realpath(os.path.join(os.path.abspath(args.output_dir), 'test_cases.json'))
        shutil.copyfile(args.tests_list, test_cases_path)
    except:
        main_logger.error("Can't copy test_case.json")
        main_logger.error(str(e))
        exit(-1)

    try:
        with open(test_cases_path, 'r') as file:
            tests_list = json.load(file)
    except OSError as e:
        main_logger.error("Failed to read test cases json. ")
        main_logger.error(str(e))
        exit(-1)

    # TODO: try-catch on file reading
    if not os.path.exists(os.path.join(args.render_path, 'config.original.json')):
        main_logger.info("First execution - create copy of config.json")
        shutil.copyfile(os.path.join(args.render_path, 'config.json'),
                        os.path.join(args.render_path, 'config.original.json'))

    render_device = get_gpu()
    system_pl = platform.system()
    current_conf = set(platform.system()) if not render_device else {platform.system(), render_device}
    main_logger.info("Detected GPUs: {}".format(render_device))
    main_logger.info("PC conf: {}".format(current_conf))
    main_logger.info("Creating predefined errors json...")

    if system_pl == "Windows":
        baseline_path_tr = os.path.join(
            'c:/TestResources/rpr_viewer_autotests_baselines', args.test_group)
    else:
        baseline_path_tr = os.path.expandvars(os.path.join(
            '$CIS_TOOLS/../TestResources/rpr_viewer_autotests_baselines', args.test_group))

    baseline_path = os.path.join(
        args.output_dir, os.path.pardir, os.path.pardir, os.path.pardir, 'Baseline', args.test_group)

    if not os.path.exists(baseline_path):
        os.makedirs(baseline_path)
        os.makedirs(os.path.join(baseline_path, 'Color'))

    # save pre-defined reports with error status
    for test in tests_list:
        # for each case create config from default
        with open(os.path.join(args.render_path, 'config.original.json'), 'r') as file:
            config_tmp = json.loads(file.read())

        # TODO: save scene name instead of scene sub path
        report = copy.deepcopy(RENDER_REPORT_BASE)
        # if 'engine' exist in case.json - set it; else - engine from xml
        engine = test['config_parameters'].get('engine', args.render_engine)
        is_skipped = is_case_skipped(test, current_conf)
        test_status = TEST_IGNORE_STATUS if is_skipped else TEST_CRASH_STATUS

        main_logger.info("Case: {}; Engine: {}; Skip here: {}; Predefined status: {};".format(
            test['name'], engine, bool(is_skipped), test_status
        ))
        report.update({'test_status': test_status,
                       'render_device': render_device,
                       'test_case': test['name'],
                       'scene_name': test['scene_sub_path'],
                       'tool': engine,
                       'file_name': test['name'] + test['file_ext'],
                       'date_time': datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
                       'script_info': test['script_info'],
                       'test_group': args.test_group,
                       'render_color_path': 'Color/' + test['name'] + test['file_ext'],
                       'testcase_timeout': test['render_time']
                       })

        if 'Update' not in args.update_refs:
            try:
                shutil.copyfile(os.path.join(baseline_path_tr, test['name'] + CASE_REPORT_SUFFIX),
                         os.path.join(baseline_path, test['name'] + CASE_REPORT_SUFFIX))

                with open(os.path.join(baseline_path, test['name'] + CASE_REPORT_SUFFIX)) as baseline:
                    baseline_json = json.load(baseline)

                for thumb in [''] + THUMBNAIL_PREFIXES:
                    if os.path.exists(os.path.join(baseline_path_tr, baseline_json[thumb + 'render_color_path'])):
                        shutil.copyfile(os.path.join(baseline_path_tr, baseline_json[thumb + 'render_color_path']),
                                 os.path.join(baseline_path, baseline_json[thumb + 'render_color_path']))
            except:
                main_logger.error('Failed to copy baseline ' +
                                              os.path.join(baseline_path_tr, test['name'] + CASE_REPORT_SUFFIX))

        if test_status == TEST_IGNORE_STATUS:
            report.update({'group_timeout_exceeded': False})
            test['status'] = TEST_IGNORE_STATUS
        try:
            shutil.copyfile(
                os.path.join(ROOT_DIR_PATH, 'jobs_launcher', 'common', 'img', report['test_status'] + test['file_ext']),
                os.path.join(args.output_dir, 'Color', test['name'] + test['file_ext']))
        except (OSError, FileNotFoundError) as err:
            main_logger.error("Can't create img stub: {}".format(str(err)))

        with open(os.path.join(args.output_dir, test["case"] + CASE_REPORT_SUFFIX), "w") as file:
            json.dump([report], file, indent=4)

    with open(test_cases_path, 'w') as file:
        json.dump(tests_list, file, indent=4)

    # run cases
    for test in [x for x in tests_list if x['status'] == 'active' and not is_case_skipped(x, current_conf)]:
        main_logger.info("\nProcessing test case: {}".format(test['name']))
        engine = test['config_parameters'].get('engine', args.render_engine)
        frame_ae = str(update_viewer_config(
            test=test,
            engine=engine,
            render_path=args.render_path,
            scene_path=args.scene_path,
            tmp=copy.deepcopy(config_tmp)
        ))

        if frame_ae == '0':
            main_logger.info("Case with infinity loop. Abort by timeout is expected. Will save 5th frame")

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
            os.system('chmod +x {}'.format(viewer_run_path))
        else:
            viewer_run_path = os.path.normpath(os.path.join(args.render_path, "RadeonProViewer"))
            os.system('chmod +x {}'.format(viewer_run_path))

        i = 0
        test_case_status = TEST_CRASH_STATUS
        while i < args.retries and test_case_status == TEST_CRASH_STATUS:
            main_logger.info("Try #" + str(i))
            i += 1
            p = psutil.Popen(viewer_run_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            stderr, stdout = b"", b""
            start_time = time.time()
            test_case_status = TEST_CRASH_STATUS

            aborted_by_timeout = False
            try:
                stdout, stderr = p.communicate(timeout=test['render_time'])
            except (TimeoutError, psutil.TimeoutExpired, subprocess.TimeoutExpired) as err:
                main_logger.error("Aborted by timeout. {}".format(str(err)))

                # RS_CONF_IT_022 - RS_CONF_IT_028
                if frame_ae == '0':
                    test_case_status = TEST_SUCCESS_STATUS
                    frame_ae = '50'

                for child in reversed(p.children(recursive=True)):
                    child.terminate()
                p.terminate()
                stdout, stderr = p.communicate()
                aborted_by_timeout = True
            else:
                test_case_status = TEST_SUCCESS_STATUS

            render_time = time.time() - start_time
            error_messages = []
            try:
                shutil.copyfile(os.path.join(args.render_path, 'img{0}{1}'.format(frame_ae.zfill(4), test['file_ext'])),
                            os.path.join(args.output_dir, 'Color', test['name'] + test['file_ext']))
                test_case_status = TEST_SUCCESS_STATUS
            except FileNotFoundError as err:
                image_not_found_str = "Image {} not found".format('img{0}{1}'.format(frame_ae.zfill(4), test['file_ext']))
                error_messages.append(image_not_found_str)
                main_logger.error(image_not_found_str)
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
            if error_messages:
                test_case_report["message"] = test_case_report["message"] + error_messages
            test_case_report["test_status"] = test_case_status
            test_case_report["render_time"] = render_time
            test_case_report["render_color_path"] = "Color/" + test_case_report["file_name"]
            test_case_report["render_log"] = test['name'] + '_app.log'
            test_case_report["group_timeout_exceeded"] = False
            test_case_report["testcase_timeout_exceeded"] = aborted_by_timeout

        with open(os.path.join(args.output_dir, test['name'] + CASE_REPORT_SUFFIX), 'w') as file:
            json.dump([test_case_report], file, indent=4)

        test["status"] = test_case_status
        with open(test_cases_path, 'w') as file:
            json.dump(tests_list, file, indent=4)

    return 0


if __name__ == "__main__":
    exit(main())
