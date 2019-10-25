import json
import os
import subprocess
import sys
from jinja2 import Environment
from jinja2 import PackageLoader

def main():

	env = Environment(
			loader=PackageLoader('import_tmp', 'template base'),
			autoescape=True
			)
	template = env.get_template('base.html')

	with open("C:\\Users\\user\\RprViewerAuto\\jobs_test_rprviewer\\Work\\summary_report.json", 'r') as file:
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
					graph_data.append([test_case["scene_name"]])
					graph_data[test_case_id + 1].append(test_case['render_time_bench'])
				
		# graph_data =[ ['Scene name', 'GPU 1', 'GPU 2'],
		 #        ['New York City, NY', 8175000, 8008000],
		 #        ['Los Angeles, CA', 3792000, 3694000],
		 #        ['Chicago, IL', 2695000, 2896000],
		 #        ['Houston, TX', 2099000, 1953000],
		 #        ['Philadelphia, PA', 1526000, 1517000] ]

		configurations.update({ conf: graph_data })
		
	print(json.dumps(configurations, indent=4))	

	output_temp = template.render(title="Benchmarks Report",
		configurations=configurations)

	with open("render_temp.html", "w") as fh:
		fh.write(output_temp)


if __name__ == "__main__":
	main()