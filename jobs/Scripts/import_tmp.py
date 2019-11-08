import argparse
import json
import os
import subprocess
import sys
from jinja2 import Environment
from jinja2 import PackageLoader



def get_jobs_launcher_version(value):
    return subprocess.check_output("git describe --tags --abbrev=0", shell=True).decode("utf-8")


def env_override(value, key):
    return os.getenv(key, value)


def main():

	parser=argparse.ArgumentParser()
	parser.add_argument('--work_dir', required=True)
	parser.add_argument('--output_dir', required=True)
	args = parser.parse_args()

	env = Environment(
			loader=PackageLoader('import_tmp', 'template base'),
			autoescape=True
			)
	env.filters['env_override'] = env_override
	env.filters['get_jobs_launcher_version'] = get_jobs_launcher_version
	template = env.get_template('base.html')

	with open(os.path.join(args.work_dir, "summary_report.json"), 'r') as file:
		summary_report_data = json.loads(file.read())

	platforms = []
	confs = []
	
	for platform in summary_report_data:
		platforms.append(platform)
		for conf in summary_report_data[platform]['results']['Benchmarks']:
			confs.append(conf)

	configurations = {}
	for conf in confs:
		graph_data = [['Scene name']]
		for platform in platforms:
			graph_data[0].append(platform)
			for test_case_id in range(len(summary_report_data[platform]['results']['Benchmarks'][conf]['render_results'])):
				test_case = summary_report_data[platform]['results']['Benchmarks'][conf]['render_results'][test_case_id]
				try:
					graph_data[test_case_id + 1].append(test_case['render_time_bench'])
				except IndexError:
					graph_data.append([test_case["scene_name"].split('/')[0]])
					graph_data[test_case_id + 1].append(test_case['render_time_bench'])

		configurations.update({ conf: graph_data })		

	with open(os.path.join(args.output_dir, "bench.json"), 'w') as file:
		json.dump(configurations, file, indent=4)

	common_info = {"reporting_date": "date", "branch_name": "master", "commit_sha": "fsoei", "commit_message": "HI"}

	output_temp = template.render(title="Benchmarks Report",
		configurations=configurations,
		common_info=common_info)

	with open(os.path.join(args.output_dir, "render_temp.html"), "w") as fh:
		fh.write(output_temp)


if __name__ == "__main__":	
	main()
