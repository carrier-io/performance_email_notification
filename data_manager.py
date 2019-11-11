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

from influxdb import InfluxDBClient
import statistics

GREEN = '#028003'
YELLOW = '#FFA400'
RED = '#FF0000'

SELECT_LAST_BUILDS_ID = "select distinct(id) from (select build_id as id, pct95 from api_comparison where " \
                        "simulation=\'{}\' and test_type=\'{}\' and \"users\"=\'{}\' " \
                        "and build_id!~/audit_{}_/ order by time DESC) GROUP BY time(1s) order by DESC limit {}"

SELECT_TEST_DATA = "select * from api_comparison where build_id=\'{}\'"

SELECT_BASELINE_BUILD_ID = "select last(pct95), build_id from api_comparison where simulation=\'{}\' " \
                           "and test_type=\'{}\' and \"users\"=\'{}\' and build_id=~/audit_{}_/"

SELECT_THRESHOLDS = "select last(red) as red, last(yellow) as yellow from threshold where request_name=\'{}\' " \
                    "and simulation=\'{}\'"

SELECT_LAST_UI_BUILD_ID = "select distinct(id) from (select build_id as id, count from uiperf where scenario=\'{}\' " \
                          "and suite=\'{}\' group by start_time order by time DESC limit 1) GROUP BY time(1s) " \
                          "order by DESC limit {}"

SELECT_UI_TEST_DATA = "select build_id, scenario, suite, domain, start_time, page, status, url, latency, tti, ttl," \
                      " onload, total_time, transfer, firstPaint, encodedBodySize, decodedBodySize from uiperf " \
                      "where build_id=\'{}\'"


class DataManager:
    def __init__(self, arguments):
        self.args = arguments
        self.client = InfluxDBClient(arguments['influx_host'], arguments['influx_port'],
                                     username=arguments['influx_user'], password=arguments['influx_password'])

    def get_api_test_info(self):
        tests_data = self.get_last_builds()
        if len(tests_data) == 0:
            raise Exception("No data found for given parameters")
        last_test_data = tests_data[0]
        last_test_data = self.append_thresholds_to_test_data(last_test_data)
        baseline = self.get_baseline()
        return tests_data, last_test_data, baseline

    def get_ui_test_info(self):
        tests_data = self.get_ui_last_builds()
        if len(tests_data) == 0:
            raise Exception("No data found for given parameters")
        tests_data = self.aggregate_ui_test_results(tests_data)
        last_test_data = tests_data[0]
        last_test_data = self.append_ui_thresholds_to_test_data(last_test_data)
        return tests_data, last_test_data

    def get_last_builds(self):
        self.client.switch_database(self.args['influx_comparison_database'])
        tests_data = []
        build_ids = []
        last_builds = self.client.query(SELECT_LAST_BUILDS_ID.format(self.args['test'], self.args['test_type'],
                                                                     str(self.args['users']), self.args['test'],
                                                                     str(self.args['test_limit'])))
        for test in list(last_builds.get_points()):
            if test['distinct'] not in build_ids:
                build_ids.append(test['distinct'])

        for _id in build_ids:
            test_data = self.client.query(SELECT_TEST_DATA.format(_id))
            tests_data.append(list(test_data.get_points()))
        return tests_data

    def get_baseline(self):
        self.client.switch_database(self.args['influx_comparison_database'])
        baseline_build_id = self.client.query(
            SELECT_BASELINE_BUILD_ID.format(self.args['test'], self.args['test_type'],
                                            str(self.args['users']), self.args['test']))
        result = list(baseline_build_id.get_points())
        if len(result) == 0:
            print("Baseline not found")
            return None
        _id = result[0]['build_id']
        baseline_data = self.client.query(SELECT_TEST_DATA.format(_id))
        return list(baseline_data.get_points())

    def append_thresholds_to_test_data(self, test):
        self.client.switch_database(self.args['influx_thresholds_database'])
        params = ['request_name', 'total', 'throughput', 'ko', 'min', 'max', 'pct50', 'pct95', 'time',
                  'simulation', 'users', 'duration']
        test_summary = []
        for request in test:
            request_data = {}
            threshold = self.client.query(SELECT_THRESHOLDS.format(str(request['request_name']),
                                                                   str(request['simulation'])))
            if len(list(threshold.get_points())) == 0:
                red_threshold = 3000
                yellow_threshold = 2000
            else:
                red_threshold = int(list(threshold.get_points())[0]['red'])
                yellow_threshold = int(list(threshold.get_points())[0]['yellow'])
            for param in ['min', 'max', 'pct50', 'pct95']:
                if int(request[param]) < yellow_threshold:
                    request_data[param + '_threshold'] = GREEN
                else:
                    request_data[param + '_threshold'] = YELLOW
                if int(request[param]) >= red_threshold:
                    request_data[param + '_threshold'] = RED
            request_data['yellow_threshold_value'] = yellow_threshold
            request_data['red_threshold_value'] = red_threshold
            for param in params:
                request_data[param] = request[param]
            test_summary.append(request_data)
        return test_summary

    def append_ui_thresholds_to_test_data(self, test):
        params = ['request_name', 'scenario', 'suite', 'build_id', 'start_time', 'url', 'count', 'failed', 'total_time',
                  'ttl', 'tti', 'onload', 'latency', 'transfer', 'encodedBodySize', 'decodedBodySize']
        self.client.switch_database(self.args['influx_thresholds_database'])
        test_summary = []
        for page in test:
            page_data = {}
            threshold = self.client.query(SELECT_THRESHOLDS.format(str(page['request_name']), str(page['scenario'])))
            if len(list(threshold.get_points())) == 0:
                red_treshold = 1000
                yellow_treshold = 150
            else:
                red_treshold = int(list(threshold.get_points())[0]['red'])
                yellow_treshold = int(list(threshold.get_points())[0]['yellow'])
            page_data['yellow_threshold_value'] = yellow_treshold
            page_data['red_threshold_value'] = red_treshold
            median_total_time = statistics.median(page['total_time'])
            median_latency = statistics.median(page['latency'])
            time = median_total_time - median_latency
            if time < yellow_treshold:
                page_data['time_threshold'] = 'green'
            else:
                page_data['time_threshold'] = 'orange'
            if time >= red_treshold:
                page_data['time_threshold'] = 'red'
            page_data['time'] = time
            for param in params:
                page_data[param] = page[param]
            test_summary.append(page_data)
        return test_summary

    def get_ui_last_builds(self):
        self.client.switch_database(self.args['influx_ui_tests_database'])
        tests_data = []
        build_ids = []
        last_builds = self.client.query(
            SELECT_LAST_UI_BUILD_ID.format(self.args['test'], str(self.args['test_type']),
                                           str(self.args['test_limit'])))
        for test in list(last_builds.get_points()):
            build_ids.append(test['distinct'])
        for _id in build_ids:
            test_data = self.client.query(SELECT_UI_TEST_DATA.format(_id))
            tests_data.append(test_data)
        return tests_data

    @staticmethod
    def aggregate_ui_test_results(tests):
        tests_data = []
        for test in tests:
            test_data = {}
            for page in list(test.get_points()):
                if page['page'] not in test_data:
                    test_data[page['page']] = {
                        'scenario': page['scenario'],
                        'suite': page['suite'],
                        'build_id': page['build_id'],
                        'start_time': page['start_time'],
                        'request_name': page['page'],
                        'url': str(page['domain']) + str(page['url']),
                        'count': 1,
                        'failed': 0,
                        'total_time': [page['total_time']],
                        'ttl': [page['ttl']],
                        'tti': [page['tti']],
                        'onload': [page['onload']],
                        'latency': [page['latency']],
                        'transfer': [page['transfer']],
                        'encodedBodySize': page['encodedBodySize'],
                        'decodedBodySize': page['decodedBodySize']
                    }
                    if page['status'] == 'ko':
                        test_data[page['page']]['failed'] = int(test_data[page['page']]['failed']) + 1
                else:
                    test_data[page['page']]['total_time'].append(page['total_time'])
                    test_data[page['page']]['ttl'].append(page['ttl'])
                    test_data[page['page']]['tti'].append(page['tti'])
                    test_data[page['page']]['onload'].append(page['onload'])
                    test_data[page['page']]['latency'].append(page['latency'])
                    test_data[page['page']]['transfer'].append(page['transfer'])
                    test_data[page['page']]['count'] = int(test_data[page['page']]['count']) + 1
                    if page['status'] == 'ko':
                        test_data[page['page']]['failed'] = int(test_data[page['page']]['failed']) + 1
            tests_data.append(list(test_data.values()))
        return tests_data
