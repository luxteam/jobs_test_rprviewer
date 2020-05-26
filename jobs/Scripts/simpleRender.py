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

ROOT_DIR_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir))
sys.path.append(ROOT_DIR_PATH)
from jobs_launcher.core.config import *
from jobs_launcher.core.system_info import get_gpu, get_machine_info
from jobs_launcher.image_service_client import ISClient
from jobs_launcher.rbs_client import RBS_Client, str2bool


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
    is_client = None
    rbs_client = None
    rbs_use = None

    try:
        rbs_use = str2bool(os.getenv('RBS_USE'))
    except Exception as e:
        main_logger.warning('Exception when getenv RBS USE: {}'.format(str(e)))

    if rbs_use:
        try:
            is_client = ISClient(os.getenv("IMAGE_SERVICE_URL"))
            main_logger.info("Image Service client created")
        except Exception as e:
            main_logger.info("Image Service client creation error: {}".format(str(e)))

        try:
            rbs_client = RBS_Client(
                job_id=os.getenv("RBS_JOB_ID"),
                url=os.getenv("RBS_URL"),
                build_id=os.getenv("RBS_BUILD_ID"),
                env_label=os.getenv("RBS_ENV_LABEL"),
                suite_id=None)
            main_logger.info("RBS Client created")
        except Exception as e:
            main_logger.info(" RBS Client creation error: {}".format(str(e)))

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
        main_logger.info("First execution - create copy of config.json")
        shutil.copyfile(os.path.join(args.render_path, 'config.json'),
                        os.path.join(args.render_path, 'config.original.json'))

    render_device = get_gpu()
    current_conf = set(platform.system()) if not render_device else {platform.system(), render_device}
    main_logger.info("Detected GPUs: {}".format(render_device))
    main_logger.info("PC conf: {}".format(current_conf))
    main_logger.info("Creating predefined errors json...")

    # save pre-defined reports with error status
    for test in tests_list:
        # for each case create config from default
        with open(os.path.join(args.render_path, 'config.original.json'), 'r') as file:
            config_tmp = json.loads(file.read())

        # TODO: save scene name instead of scene sub path
        report = copy.deepcopy(RENDER_REPORT_BASE)
        # if 'engine' exist in case.json - set it; else - engine from xml
        engine = test['config_parameters'].get('engine', args.render_engine)
        skip_on_it = sum([current_conf & set(x) == set(x) for x in test.get('skip_on', '')])
        test_status = TEST_IGNORE_STATUS if test['status'] == 'skipped' or skip_on_it else TEST_CRASH_STATUS

        main_logger.info("Case: {}; Engine: {}; Skip here: {}; Predefined status: {};".format(
            test['name'], engine, bool(skip_on_it), test_status
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
                       'render_color_path': 'Color/' + test['name'] + test['file_ext']
                       })
        try:
            shutil.copyfile(
                os.path.join(ROOT_DIR_PATH, 'jobs_launcher', 'common', 'img', report['test_status'] + test['file_ext']),
                os.path.join(args.output_dir, 'Color', test['name'] + test['file_ext']))
        except (OSError, FileNotFoundError) as err:
            main_logger.error("Can't create img stub: {}".format(str(err)))

        with open(os.path.join(args.output_dir, test["name"] + CASE_REPORT_SUFFIX), "w") as file:
            json.dump([report], file, indent=4)

    # run cases
    for test in [x for x in tests_list if x['status'] == 'active' and not sum([current_conf & set(y) == set(y) for y in x.get('skip_on', '')])]:
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

        p = psutil.Popen(viewer_run_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        stderr, stdout = b"", b""
        start_time = time.time()
        test_case_status = TEST_CRASH_STATUS

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
        else:
            test_case_status = TEST_SUCCESS_STATUS
        finally:
            render_time = time.time() - start_time
            try:
                shutil.copyfile(os.path.join(args.render_path, 'img{0}{1}'.format(frame_ae.zfill(4), test['file_ext'])),
                            os.path.join(args.output_dir, 'Color', test['name'] + test['file_ext']))
                test_case_status = TEST_SUCCESS_STATUS
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

    if rbs_client:
        try:
            main_logger.info('Try to send results to RBS')
            res = []

            for case in tests_list:
                case_info = json.load(open(os.path.realpath(
                    os.path.join(os.path.abspath(args.output_dir), '{}_RPR.json'.format(case['name'])))))
                image_id = is_client.send_image(os.path.realpath(
                    os.path.join(os.path.abspath(args.output_dir), case_info[0]['render_color_path'])))
                res.append({
                    'name': case['name'],
                    'status': case_info[0]['test_status'],
                    'metrics': {
                        'render_time': case_info[0]['render_time']
                    },
                    "artefacts": {
                        "rendered_image": str(image_id)
                    }
                })

            rbs_client.get_suite_id_by_name(case_info[0]['test_group'])
            # send machine info to rbs
            env = {"gpu": get_gpu(), **get_machine_info()}
            env.pop('os')
            env.update({'hostname': env.pop('host'), 'cpu_count': int(env['cpu_count'])})
            main_logger.info(env)
            main_logger.info(res)

            response = rbs_client.send_test_suite(res=res, env=env)
            main_logger.info('Test suite results sent with code {}'.format(response.status_code))
            main_logger.info(response.content)

        except Exception as e:
            main_logger.info("Test case result creation error: {}".format(str(e)))

    return 0


if __name__ == "__main__":
    exit(main())
