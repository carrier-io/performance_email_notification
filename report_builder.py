# Copyright 2019 getcarrier.io

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import time
import calendar
import datetime
from chart_generator import alerts_linechart, barchart, ui_comparison_linechart
from email.mime.image import MIMEImage
import statistics
from jinja2 import Environment, FileSystemLoader

GREEN = '#028003'
YELLOW = '#FFA400'
RED = '#FF0000'
GRAY = '#CCCCCC'

STATUS_COLOR = {
    "success": GREEN,
    "failed": RED,
    "finished": GRAY
}

class ReportBuilder:

    def create_api_email_body(self, args, tests_data, last_test_data, baseline, comparison_metric,
                              violation, thresholds=None):
        test_description = self.create_test_description(args, last_test_data, baseline, comparison_metric, violation)
        builds_comparison = self.create_builds_comparison(tests_data)
        general_metrics = self.get_general_metrics(args, builds_comparison[0], baseline, thresholds)
        charts = self.create_charts(builds_comparison, last_test_data, baseline, comparison_metric)
        baseline_and_thresholds = self.get_baseline_and_thresholds(args, last_test_data, baseline, comparison_metric,
                                                                   thresholds)

        email_body = self.get_api_email_body(args, test_description, last_test_data, baseline, builds_comparison,
                                             baseline_and_thresholds, general_metrics)
        return email_body, charts, str(test_description['start']).split(" ")[0]

    def create_ui_email_body(self, tests_data, last_test_data):
        test_params = self.create_ui_test_discription(last_test_data)
        #top_five_thresholds = self.get_baseline_and_thresholds(last_test_data, None, 'time')
        top_five_thresholds = []
        builds_comparison = self.create_ui_builds_comparison(tests_data)
        charts = self.create_ui_charts(last_test_data, builds_comparison)
        last_test_data = self.aggregate_last_test_results(last_test_data)
        email_body = self.get_ui_email_body(test_params, top_five_thresholds, builds_comparison, last_test_data)
        return email_body, charts, str(test_params['start_time']).split(" ")[0]

    def create_test_description(self, args, test, baseline, comparison_metric, violation):
        params = ['simulation', 'users', 'duration']
        test_params = {"test_type": args["test_type"], "env": args["env"],
                       "performance_degradation_rate": args["performance_degradation_rate"],
                       "missed_threshold_rate": args["missed_threshold_rate"],
                       "reasons_to_fail_report": args["reasons_to_fail_report"], "status": args["status"],
                       "color": STATUS_COLOR[args["status"].lower()]}
        for param in params:
            test_params[param] = test[0][param]
        test_params['end'] = str(test[0]['time']).replace("T", " ").replace("Z", "")
        timestamp = calendar.timegm(time.strptime(test_params['end'], '%Y-%m-%d %H:%M:%S'))
        test_params['start'] = datetime.datetime.utcfromtimestamp(int(timestamp) - int(float(test[0]['duration']))) \
            .strftime('%Y-%m-%d %H:%M:%S')
        # test_params['status'], test_params['color'], test_params['failed_reason'] = self.check_status(args,
        #     test, baseline, comparison_metric, violation)
        return test_params

    @staticmethod
    def create_ui_test_discription(test):
        description = {'start_time': datetime.datetime.utcfromtimestamp(int(test[0]['start_time']) / 1000).strftime(
            '%Y-%m-%d %H:%M:%S'), 'scenario': test[0]['scenario'], 'suite': test[0]['suite']}
        count, errors = 0, 0
        for page in test:
            count += int(page['count'])
            errors += int(page['failed'])
        error_rate = round(errors * 100 / count, 2)
        failed_reasons = []
        if error_rate > 10:
            description['status'] = 'FAILED'
            failed_reasons.append('error rate - ' + str(error_rate) + ' %')
        else:
            description['status'] = 'SUCCESS'
        page_count, missed_thresholds = 0, 0
        for page in test:
            page_count += 1
            if page['time_threshold'] != 'green':
                missed_thresholds += 1
        missed_thresholds_rate = round(missed_thresholds * 100 / page_count, 2)
        if missed_thresholds_rate > 50:
            description['status'] = 'FAILED'
            failed_reasons.append('missed thresholds - ' + str(missed_thresholds_rate) + ' %')
        if description['status'] is 'SUCCESS':
            description['color'] = GREEN
        else:
            description['color'] = RED
        description['failed_reason'] = failed_reasons
        return description

    def check_status(self, args, test, baseline, comparison_metric, violation):
        failed_reasons = []
        error_rate = args.get("error_rate") if args.get("error_rate") is not None else -1
        test_status, failed_message = self.check_functional_issues(error_rate, test)
        if failed_message != '':
            failed_reasons.append(failed_message)
        performance_degradation_rate = args.get("performance_degradation_rate") if args.get("performance_degradation_rate") is not None else -1
        status, failed_message = self.check_performance_degradation(performance_degradation_rate, test, baseline, comparison_metric)
        if failed_message != '':
            failed_reasons.append(failed_message)
        if test_status is 'SUCCESS':
            test_status = status
        missed_thresholds = args.get("missed_thresholds") if args.get("missed_thresholds") is not None else -1
        status, failed_message = self.check_missed_thresholds(missed_thresholds, violation)
        if failed_message != '':
            failed_reasons.append(failed_message)
        if test_status is 'SUCCESS':
            test_status = status
        if test_status is 'SUCCESS':
            color = GREEN
        else:
            color = RED
        return test_status, color, failed_reasons

    @staticmethod
    def check_functional_issues(_error_rate, test):
        if _error_rate == -1:
            return 'SUCCESS', ''
        request_count, error_count = 0, 0
        for request in test:
            request_count += int(request['total'])
            error_count += int(request['ko'])
        error_rate = round(error_count * 100 / request_count, 2)
        if error_rate > _error_rate:
            return 'FAILED', 'error rate - ' + str(error_rate) + ' %'
        return 'SUCCESS', ''

    @staticmethod
    def check_performance_degradation(degradation_rate, test, baseline, comparison_metric):
        if degradation_rate == -1:
            return 'SUCCESS', ''
        if baseline:
            request_count, performance_degradation = 0, 0
            for request in test:
                request_count += 1
                for baseline_request in baseline:
                    if request['request_name'] == baseline_request['request_name']:
                        if int(request[comparison_metric]) > int(baseline_request[comparison_metric]):
                            performance_degradation += 1
            performance_degradation_rate = round(performance_degradation * 100 / request_count, 2)
            if performance_degradation_rate > degradation_rate:
                return 'FAILED', 'performance degradation rate - ' + str(performance_degradation_rate) + ' %'
            else:
                return 'SUCCESS', ''
        else:
            return 'SUCCESS', ''

    @staticmethod
    def check_missed_thresholds(missed_thresholds, violation):
        if missed_thresholds == -1:
            return 'SUCCESS', ''
        if violation > missed_thresholds:
            return 'FAILED', 'missed thresholds rate - ' + str(violation) + ' %'
        return 'SUCCESS', ''

    def create_builds_comparison(self, tests):
        builds_comparison = []
        for test in tests:
            summary_request, test_info = {}, {}
            for req in test:
                if req["request_name"] == "All":
                    summary_request = req

            date = str(test[0]['time']).replace("T", " ").replace("Z", "")
            try:
                timestamp = calendar.timegm(time.strptime(date, '%Y-%m-%d %H:%M:%S'))
            except ValueError:
                timestamp = calendar.timegm(time.strptime(date.split(".")[0], '%Y-%m-%d %H:%M:%S'))
            if summary_request:
                test_info['date'] = datetime.datetime.utcfromtimestamp(int(timestamp)).strftime('%d-%b %H:%M')
                test_info['total'] = summary_request["total"]
                test_info['throughput'] = round(summary_request["throughput"], 2)
                test_info['pct95'] = summary_request["pct95"]
                test_info['error_rate'] = round((summary_request["ko"] / summary_request["total"]) * 100, 2)
                builds_comparison.append(test_info)
        builds_comparison = self.calculate_diffs(builds_comparison)

        return builds_comparison

    def calculate_diffs(self, builds):
        builds_comparison = []
        last_build = builds[0]
        for build in builds:
            build_info_with_diffs = self.compare_builds(build, last_build)
            builds_comparison.append(build_info_with_diffs)
        return builds_comparison

    @staticmethod
    def compare_builds(build, last_build):
        build_info = {}
        for param in ['date', 'error_rate', 'pct95', 'total', 'throughput']:
            param_diff = None
            if param in ['error_rate']:
                param_diff = round(float(build[param]) - float(last_build.get(param, 0.0)), 2)
                color = RED if param_diff > 0.0 else GREEN
            if param in ['throughput', 'total']:
                param_diff = round(float(build[param]) - float(last_build.get(param, 0.0)), 2)
                color = RED if param_diff < 0.0 else GREEN
            if param in ['pct95']:
                param_diff = round((float(build[param]) - float(last_build[param])) / 1000, 2)
                color = RED if param_diff > 0.0 else GREEN
            if param_diff is not None:
                param_diff = f"+{param_diff}" if param_diff > 0 else str(param_diff)
                build_info[f'{param}_diff'] = f"<p style=\"color: {color}\">{param_diff}</p>"
            build_info[param] = build[param]
        return build_info

    def create_charts(self, builds, last_test_data, baseline, comparison_metric):
        charts = []
        if len(builds) > 1:
            charts.append(self.create_success_rate_chart(builds))
            charts.append(self.create_throughput_chart(builds))
        return charts

    @staticmethod
    def create_success_rate_chart(builds):
        labels, keys, values = [], [], []
        count = 1
        for test in builds:
            labels.append(test['date'])
            keys.append(round(100 - test['error_rate'], 2))
            values.append(count)
            count += 1
        datapoints = {
            'title': 'Successful requests, %',
            'label': 'Successful requests, %',
            'x_axis': 'Test Runs',
            'y_axis': 'Successful requests, %',
            'width': 10,
            'height': 3,
            'path_to_save': '/tmp/success_rate.png',
            'keys': keys[::-1],
            'values': values,
            'labels': labels[::-1]
        }
        alerts_linechart(datapoints)
        fp = open('/tmp/success_rate.png', 'rb')
        image = MIMEImage(fp.read())
        image.add_header('Content-ID', '<success_rate>')
        fp.close()
        return image

    @staticmethod
    def create_throughput_chart(builds):
        labels, keys, values = [], [], []
        count = 1
        for test in builds:
            labels.append(test['date'])
            keys.append(test['throughput'])
            values.append(count)
            count += 1
        datapoints = {
            'title': 'Throughput',
            'label': 'Throughput, req/s',
            'x_axis': 'Test Runs',
            'y_axis': 'Throughput, req/s',
            'width': 10,
            'height': 3,
            'path_to_save': '/tmp/throughput.png',
            'keys': keys[::-1],
            'values': values,
            'labels': labels[::-1]
        }
        alerts_linechart(datapoints)
        fp = open('/tmp/throughput.png', 'rb')
        image = MIMEImage(fp.read())
        image.add_header('Content-ID', '<throughput>')
        fp.close()
        return image

    @staticmethod
    def create_comparison_vs_baseline_barchart(last_test_data, baseline, comparison_metric):
        green_keys, yellow_keys, utility_key, green_request_value, yellow_request_value = [], [], [], [], []
        utility_request_value, green_request_name, yellow_request_name, utility_request_name = [], [], [], []
        count = 1
        for request in last_test_data:
            for baseline_request in baseline:
                if request['request_name'] == baseline_request['request_name']:
                    if int(request[comparison_metric]) > int(baseline_request[comparison_metric]):
                        yellow_keys.append(count)
                        count += 1
                        yellow_request_value.append(round(-float(request[comparison_metric]) / 1000, 2))
                        yellow_request_name.append(request['request_name'])
                    else:
                        green_keys.append(count)
                        count += 1
                        green_request_value.append(round(float(request[comparison_metric]) / 1000, 2))
                        green_request_name.append(request['request_name'])

        if len(green_keys) == 0:
            utility_key.append(count)
            count += 1
            utility_request_name.append('utility')
            utility_request_value.append(-max(yellow_request_value) / 2)
        if len(yellow_keys) == 0:
            utility_key.append(count)
            count += 1
            utility_request_name.append('utility')
            utility_request_value.append(-max(green_request_value) / 2)
        datapoints = {"green_keys": green_keys,
                      "yellow_keys": yellow_keys,
                      "red_keys": [],
                      "utility_keys": utility_key,
                      "green_request": green_request_value,
                      "yellow_request": yellow_request_value,
                      "red_request": [],
                      "utility_request": utility_request_value,
                      "green_request_name": green_request_name,
                      "yellow_request_name": yellow_request_name,
                      "red_request_name": [],
                      "utility_request_name": utility_request_name,
                      'width': 8,
                      'height': 4.5,
                      "x_axis": "Requests", "y_axis": "Time, s", "title": "Comparison vs Baseline",
                      "path_to_save": "/tmp/baseline.png"}
        barchart(datapoints)
        fp = open('/tmp/baseline.png', 'rb')
        image = MIMEImage(fp.read())
        image.add_header('Content-ID', '<baseline>')
        fp.close()
        return image

    @staticmethod
    def create_thresholds_chart(last_test_data, comparison_metric):
        green_keys, yellow_keys, red_keys, utility_key, green_request_value = [], [], [], [], []
        yellow_request_value, red_request_value, utility_request_value, green_request_name = [], [], [], []
        yellow_request_name, red_request_name, utility_request_name = [], [], []
        count = 1
        for request in last_test_data:
            if request[comparison_metric + '_threshold'] == 'green':
                green_keys.append(count)
                count += 1
                green_request_value.append(round(float(request[comparison_metric]) / 1000, 2))
                green_request_name.append(request['request_name'])
            if request[comparison_metric + '_threshold'] == 'orange':
                yellow_keys.append(count)
                count += 1
                yellow_request_value.append(round(-float(request[comparison_metric]) / 1000, 2))
                yellow_request_name.append(request['request_name'])
            if request[comparison_metric + '_threshold'] == 'red':
                red_keys.append(count)
                count += 1
                red_request_value.append(round(-float(request[comparison_metric]) / 1000, 2))
                red_request_name.append(request['request_name'])

        if len(green_keys) == 0:
            utility_key.append(count)
            count += 1
            utility_request_name.append('utility')
            if len(red_request_value) != 0:
                utility_request_value.append(-max(red_request_value) / 2)
            else:
                utility_request_value.append(-max(yellow_request_value) / 2)
        if len(yellow_keys) == 0 and len(red_keys) == 0:
            utility_key.append(count)
            count += 1
            utility_request_name.append('utility')
            utility_request_value.append(-max(green_request_value) / 2)
        datapoints = {"green_keys": green_keys,
                      "yellow_keys": yellow_keys,
                      "red_keys": red_keys,
                      "utility_keys": utility_key,
                      "green_request": green_request_value,
                      "yellow_request": yellow_request_value,
                      "red_request": red_request_value,
                      "utility_request": utility_request_value,
                      "green_request_name": green_request_name,
                      "yellow_request_name": yellow_request_name,
                      "red_request_name": red_request_name,
                      "utility_request_name": utility_request_name,
                      'width': 8,
                      'height': 4.5,
                      "x_axis": "Requests", "y_axis": "Time, s", "title": "Comparison vs Thresholds",
                      "path_to_save": "/tmp/thresholds.png"}
        barchart(datapoints)
        fp = open('/tmp/thresholds.png', 'rb')
        image = MIMEImage(fp.read())
        image.add_header('Content-ID', '<thresholds>')
        fp.close()
        return image

    def create_ui_charts(self, test, builds_comparison):
        charts = [self.create_thresholds_chart(test, 'time')]
        if len(builds_comparison) > 1:
            charts.append(self.create_comparison_chart(builds_comparison))
        if len(builds_comparison) > 1:
            charts.append(self.create_success_rate_chart(builds_comparison))
        return charts

    @staticmethod
    def create_comparison_chart(builds_comparison):
        labels, keys, latency_values, transfer_values = [], [], [], []
        tti_values, ttl_values, total_time_values = [], [], []
        count = 1
        for build in builds_comparison:
            labels.append(build['date'])
            keys.append(count)
            count += 1
            latency_values.append(build['latency'])
            transfer_values.append(build['transfer'])
            tti_values.append(build['tti'])
            ttl_values.append(build['ttl'])
            total_time_values.append(build['total_time'])
        datapoints = {
            'title': '',
            'label': 'Time, sec',
            'x_axis': 'Test Runs',
            'y_axis': 'Time, sec',
            'width': 10,
            'height': 3,
            'path_to_save': '/tmp/comparison.png',
            'keys': keys,
            'latency_values': latency_values[::-1],
            'transfer_values': transfer_values[::-1],
            'tti_values': tti_values[::-1],
            'ttl_values': ttl_values[::-1],
            'total_time_values': total_time_values[::-1],
            'labels': labels[::-1]
        }
        ui_comparison_linechart(datapoints)
        fp = open('/tmp/comparison.png', 'rb')
        image = MIMEImage(fp.read())
        image.add_header('Content-ID', '<comparison>')
        fp.close()
        return image

    @staticmethod
    def get_general_metrics(args, build_data, baseline, thresholds=None):
        current_tp = build_data['throughput']
        current_error_rate = build_data['error_rate']
        baseline_throughput = "N/A"
        baseline_error_rate = "N/A"
        thresholds_tp_rate = "N/A"
        thresholds_error_rate = "N/A"
        thresholds_tp_color = GRAY
        thresholds_er_color = GRAY
        baseline_tp_color = GRAY
        baseline_er_color = GRAY
        if baseline and args.get("quality_gate_config", {}).get("baseline", {}).get("checked"):
            baseline_throughput = round(sum([tp['throughput'] for tp in baseline]), 2)
            baseline_ko_count = round(sum([tp['ko'] for tp in baseline]), 2)
            baseline_ok_count = round(sum([tp['ok'] for tp in baseline]), 2)
            baseline_error_rate = round((baseline_ko_count / (baseline_ko_count + baseline_ok_count)) * 100, 2)
            baseline_tp_color = RED if baseline_throughput > current_tp else GREEN
            baseline_er_color = RED if current_error_rate > baseline_error_rate else GREEN
            baseline_throughput = round(current_tp - baseline_throughput, 2)
            baseline_error_rate = round(current_error_rate - baseline_error_rate, 2)
        if thresholds and args.get("quality_gate_config", {}).get("SLA", {}).get("checked"):
            for th in thresholds:
                if th['request_name'] == 'all':
                    if th['target'] == 'error_rate':
                        thresholds_error_rate = round(th["metric"] - th['value'], 2)
                        if th['threshold'] == "red":
                            thresholds_er_color = RED
                        else:
                            thresholds_er_color = GREEN
                    if th['target'] == 'throughput':
                        thresholds_tp_rate = round(th["metric"] - th['value'], 2)
                        if th['threshold'] == "red":
                            thresholds_tp_color = RED
                        else:
                            thresholds_tp_color = GREEN
        return {
            "current_tp": current_tp,
            "baseline_tp": baseline_throughput,
            "baseline_tp_color": baseline_tp_color,
            "threshold_tp": thresholds_tp_rate,
            "threshold_tp_color": thresholds_tp_color,
            "current_er": current_error_rate,
            "baseline_er": baseline_error_rate,
            "baseline_er_color": baseline_er_color,
            "threshold_er": thresholds_error_rate,
            "threshold_er_color": thresholds_er_color
        }

    @staticmethod
    def get_baseline_and_thresholds(args, last_test_data, baseline, comparison_metric, thresholds):
        exceeded_thresholds = []
        baseline_metrics = {}
        thresholds_metrics = {}
        if baseline and args.get("quality_gate_config", {}).get("settings", {}).get("per_request_results", {}).get('check_response_time'):
            for request in baseline:
                baseline_metrics[request['request_name']] = int(request[comparison_metric])

        if thresholds and args.get("quality_gate_config", {}).get("settings", {}).get("per_request_results", {}).get('check_response_time'):
            for th in thresholds:
                if th['target'] == 'response_time':
                    thresholds_metrics[th['request_name']] = th
        for request in last_test_data:
            req = {}
            req['response_time'] = str(round(float(request[comparison_metric]) / 1000, 2))
            if len(str(request['request_name'])) > 80:
                req['request_name'] = str(request['request_name'])[:80] + "..."
            else:
                req['request_name'] = str(request['request_name'])
            if baseline and request['request_name'] in list(baseline_metrics.keys()):
                req['baseline'] = round(
                    float(int(request[comparison_metric]) - baseline_metrics[request['request_name']]) / 1000, 2)
                if req['baseline'] < 0:
                    req['baseline_color'] = GREEN
                else:
                    req['baseline_color'] = YELLOW
            else:
                req['baseline'] = "N/A"
                req['baseline_color'] = GRAY
            if thresholds_metrics and thresholds_metrics.get(request['request_name']):
                req['threshold'] = round(
                    float(int(request[comparison_metric]) -
                          int(thresholds_metrics[request['request_name']]['value'])) / 1000, 2)
                req['threshold_value'] = str(thresholds_metrics[request['request_name']]['value'])
                if thresholds_metrics[request['request_name']]['threshold'] == 'red':
                    req['line_color'] = RED
                    req['threshold_color'] = RED
                else:
                    req['threshold_color'] = GREEN
            else:
                req['threshold'] = "N/A"
                req['threshold_value'] = 0.0
                req['threshold_color'] = GRAY
                req['line_color'] = GRAY
            if not req.get('line_color'):
                if req['threshold_color'] == GREEN and req.get('baseline_color', GREEN) == GREEN:
                    req['line_color'] = GREEN
                else:
                    req['line_color'] = YELLOW
            exceeded_thresholds.append(req)
        exceeded_thresholds = sorted(exceeded_thresholds, key=lambda k: float(k['response_time']), reverse=True)
        hundered = 0
        for _ in range(len(exceeded_thresholds)):
            if not (hundered):
                exceeded_thresholds[_]['share'] = 100
                hundered = float(exceeded_thresholds[_]['response_time'])
            else:
                exceeded_thresholds[_]['share'] = int((100 * float(exceeded_thresholds[_]['response_time'])) / hundered)
        return exceeded_thresholds

    def create_ui_builds_comparison(self, tests):
        comparison, builds_info = [], []
        for build in tests:
            build_info = {'ttl': [], 'tti': [], 'transfer': [], 'latency': [], 'total_time': []}
            page_count = 0
            error_count = 0
            for page in build:
                page_count += page['count']
                error_count += page['failed']
                build_info['ttl'].append(round(statistics.median(page['ttl']) / 1000.0, 2))
                build_info['tti'].append(round(statistics.median(page['tti']) / 1000.0, 2))
                build_info['transfer'].append(round(statistics.median(page['transfer']) / 1000.0, 2))
                build_info['latency'].append(round(statistics.median(page['latency']) / 1000.0, 2))
                build_info['total_time'].append(round(statistics.median(page['total_time']) / 1000.0, 2))
            build_info['ttl'] = statistics.median(build_info['ttl'])
            build_info['tti'] = statistics.median(build_info['tti'])
            build_info['transfer'] = statistics.median(build_info['transfer'])
            build_info['latency'] = statistics.median(build_info['latency'])
            build_info['total_time'] = statistics.median(build_info['total_time'])
            build_info['date'] = datetime.datetime.utcfromtimestamp(int(build[0]['start_time']) / 1000) \
                .strftime('%d-%b %H:%M')
            build_info['count'] = page_count
            build_info['error_rate'] = round((error_count / page_count) * 100, 2)
            builds_info.append(build_info)
        last_build = builds_info[0]
        for build in builds_info:
            comparison.append(self.compare_ui_builds(last_build, build))
        return comparison

    @staticmethod
    def compare_ui_builds(last_build, build):
        build_info = {}
        params = ['date', 'error_rate', 'ttl', 'tti', 'transfer', 'latency', 'total_time', 'count']
        build_info['error_rate_diff'] = float(build['error_rate']) - float(last_build['error_rate'])
        if build_info['error_rate_diff'] > 0.0:
            build_info['error_rate_diff'] = "<b style=\"color: red\">&#9650;</b>" + str(build_info['error_rate_diff'])
        else:
            build_info['error_rate_diff'] = str(build_info['error_rate_diff']
                                                ).replace("-", "<b style=\"color: green\">&#9660;</b>")
        build_info['total_page_diff'] = round(float(build['count']) * 100 / float(last_build['count']) - 100, 1)
        if build_info['total_page_diff'] > 0.0:
            build_info['total_page_diff'] = "<b style=\"color: red\">&#9650;</b>" + str(build_info['total_page_diff'])
        else:
            build_info['total_page_diff'] = str(build_info['total_page_diff']
                                                ).replace("-", "<b style=\"color: green\">&#9660;</b>")
        build_info['total_ttl_diff'] = round(float(build['ttl']) * 100 / float(last_build['ttl']) - 100, 1)
        if build_info['total_ttl_diff'] > 0.0:
            build_info['total_ttl_diff'] = "<b style=\"color: red\">&#9650;</b>" + str(build_info['total_ttl_diff'])
        else:
            build_info['total_ttl_diff'] = str(build_info['total_ttl_diff']
                                               ).replace("-", "<b style=\"color: green\">&#9660;</b>")
        build_info['total_tti_diff'] = round(float(build['tti']) * 100 / float(last_build['tti']) - 100, 1)
        if build_info['total_tti_diff'] > 0.0:
            build_info['total_tti_diff'] = "<b style=\"color: red\">&#9650;</b>" + str(build_info['total_tti_diff'])
        else:
            build_info['total_tti_diff'] = str(build_info['total_tti_diff']
                                               ).replace("-", "<b style=\"color: green\">&#9660;</b>")

        build_info['total_transfer_diff'] = round(float(build['transfer']) * 100 / float(last_build['transfer']) - 100,
                                                  1) if int(last_build['transfer']) != 0 else 0

        if build_info['total_transfer_diff'] > 0.0:
            build_info['total_transfer_diff'] = "<b style=\"color: red\">&#9650;</b>" + \
                                                str(build_info['total_transfer_diff'])
        else:
            build_info['total_transfer_diff'] = str(build_info['total_transfer_diff']
                                                    ).replace("-", "<b style=\"color: green\">&#9660;</b>")
        build_info['total_latency_diff'] = round(float(build['latency']) * 100 / float(last_build['latency']) - 100, 1)
        if build_info['total_latency_diff'] > 0.0:
            build_info['total_latency_diff'] = "<b style=\"color: red\">&#9650;</b>" + str(
                build_info['total_latency_diff'])
        else:
            build_info['total_latency_diff'] = str(round(float(build_info['total_latency_diff']), 1)
                                                   ).replace("-", "<b style=\"color: green\">&#9660;</b>")
        build_info['total_time_diff'] = round(float(build['total_time']) * 100 / float(last_build['total_time']) - 100,
                                              1)
        if build_info['total_time_diff'] > 0.0:
            build_info['total_time_diff'] = "<b style=\"color: red\">&#9650;</b>" + str(build_info['total_time_diff'])
        else:
            build_info['total_time_diff'] = str(build_info['total_time_diff']
                                                ).replace("-", "<b style=\"color: green\">&#9660;</b>")

        for param in params:
            build_info[param] = build[param]
        return build_info

    @staticmethod
    def aggregate_last_test_results(test):
        test_data = []
        params = ['request_name', 'count', 'failed', 'time_threshold']
        for page in test:
            page_info = {}
            for param in params:
                page_info[param] = page[param]
            page_info['ttl'] = round(statistics.median(page['ttl']) / 1000.0, 2)
            page_info['tti'] = round(statistics.median(page['tti']) / 1000.0, 2)
            page_info['transfer'] = round(statistics.median(page['transfer']) / 1000.0, 2)
            page_info['latency'] = round(statistics.median(page['latency']) / 1000.0, 2)
            page_info['total_time'] = round(statistics.median(page['total_time']) / 1000.0, 2)
            test_data.append(page_info)
        return test_data

    def get_api_email_body(self, args, test_params, last_test_data, baseline, builds_comparison, baseline_and_thresholds,
                           general_metrics):
        env = Environment(loader=FileSystemLoader('./templates/'))
        template = env.get_template("backend_email_template.html")
        last_test_data = self.reprocess_test_data(last_test_data, ['total', 'throughput'])
        if args.get("performance_degradation_rate_qg", None):
            if test_params["performance_degradation_rate"] > args["performance_degradation_rate_qg"]:
                test_params["performance_degradation_rate"] = f'{test_params["performance_degradation_rate"]}%'
                test_params["baseline_status"] = "failed"
            else:
                test_params["performance_degradation_rate"] = f'{test_params["performance_degradation_rate"]}%'
                test_params["baseline_status"] = "success"
        else:
            test_params["performance_degradation_rate"] = f'-'
            test_params["baseline_status"] = "N/A"
        if args.get("missed_thresholds_qg", None):
            if test_params["missed_threshold_rate"] > args["missed_thresholds_qg"]:
                test_params["missed_threshold_rate"] = f'{test_params["missed_threshold_rate"]}%'
                test_params["threshold_status"] = "failed"
            else:
                test_params["missed_threshold_rate"] = f'{test_params["missed_threshold_rate"]}%'
                test_params["threshold_status"] = "success"
        else:
            test_params["missed_threshold_rate"] = f'-'
            test_params["threshold_status"] = "N/A"
        html = template.render(t_params=test_params, summary=last_test_data, baseline=baseline,
                               comparison=builds_comparison,
                               baseline_and_thresholds=baseline_and_thresholds, general_metrics=general_metrics)
        return html

    @staticmethod
    def stringify_number(number):
        if float(number) // 1000000 > 0:
            return f'{str(round(float(number) / 1000000, 2))}M'
        elif float(number) // 1000 > 0:
            return f'{str(round(float(number) / 1000, 2))}K'
        else:
            return str(number)

    def reprocess_test_data(self, results_list, keys):
        for _ in range(len(results_list)):
            for key in keys:
                results_list[_][key] = self.stringify_number(results_list[_][key])
        return results_list

    @staticmethod
    def get_ui_email_body(test_params, top_five_thresholds, builds_comparison, last_test_data):
        env = Environment(loader=FileSystemLoader('./templates/'))
        template = env.get_template("ui_email_template.html")
        html = template.render(t_params=test_params, top_five_thresholds=top_five_thresholds,
                               comparison=builds_comparison,
                               summary=last_test_data)
        return html
