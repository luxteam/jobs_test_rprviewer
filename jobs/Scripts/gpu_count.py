import argparse
import sys
import os
import subprocess
import psutil
import json
import platform


def count_gpu():
    s = subprocess.Popen("wmic path win32_VideoController get name", stdout=subprocess.PIPE)
    stdout = s.communicate()
    render_device = stdout[0].decode("utf-8").replace('\r', '').replace(' ', '').split('\n')[1:]
    gpus_list = [x for x in render_device if x not in ['MicrosoftRemoteDisplayAdapter', '']]
    # print(render_device)
    # print(gpus_list)
    return(len(gpus_list))


def define_primary_device_number(test, engine, scene_path, render_path, tmp, frame_exit_after=100, iterations_per_frame=1):
    gpus_count = count_gpu()
    # gpus_render_time = {'0': 0, '1': 0}

    for i in range(gpus_count):
        # update confing primary_device = i, scene_path
        tmp.update(test['config_parameters'])
        tmp['engine'] = engine
        tmp['primary_device'] = i  #added
        tmp['iterations_per_frame'] = iterations_per_frame
        tmp['benchmark_mode'] = 'yes'
        tmp['save_frames'] = 'yes'
        tmp['frame_exit_after'] = frame_exit_after
        tmp['scene']['path'] = os.path.normpath(os.path.join(scene_path, test['scene_sub_path']))
        if 'uiConfig' in test.keys():
            tmp['uiConfig'] = os.path.normpath(os.path.join(scene_path, test['uiConfig']))

        with open(os.path.join(render_path, "config.json"), 'w') as file:
            json.dump(tmp, file, indent=4)

        if not os.path.exists(os.path.join(args.output_dir, "Color")):
            os.makedirs(os.path.join(args.output_dir, "Color"))

        # remove old images
        main_logger.info(os.listdir(args.render_path))
        old_images = [x for x in os.listdir(args.render_path) if os.path.isfile(x) and (x.startswith('img0') or x.endswith('.txt'))]
        main_logger.info("Detected old renderers: {}".format(str(old_images)))
        for img in old_images:
            try:
                os.remove(os.path.join(args.render_path, img))
            except OSError as err:
                main_logger.error(str(err))

        # start viwer (simpleRender)
         os.chdir(args.render_path)
        if platform.system() == 'Windows':
            viewer_run_path = os.path.normpath(os.path.join(args.render_path, "RadeonProViewer.exe"))
        try:
            stdout, stderr = p.communicate(timeout=test['render_time'])
        except (TimeoutError, psutil.TimeoutExpired, subprocess.TimeoutExpired) as err:
            main_logger.error("Aborted by timeout. {}".format(str(err)))
            for child in reversed(p.children(recursive=True)):
                child.terminate()
            p.terminate()
        # get render time from bench.txt file (from benchmarks)
        render_time = 0
        try:
            for bench_txt in os.listdir(args.render_path):
                if os.path.isfile(bench_txt) and bench_txt.startswith('scene.gltf_'):
                    with open(os.path.join(args.render_path, bench_txt), "r") as file:
                        main_logger.info("render_time pasrsed")
                        render_time_bench = float(file.readlines()[-1].split(";")[-1])
                        main_logger.info(render_time)
        except Exception as err:
            main_logger.error("Error during bench_txt parsing: {}".format(str(err))) 
        gpus_render_time.update({i: render_time})

    # sort gpus_render_time - get minimum
    render_times = list(gpus_render_time.values()).sort()
    for key in gpus_render_time.keys():
        if gpus_render_time[key] == render_times[0]:
            primary_device = key
    
    return key