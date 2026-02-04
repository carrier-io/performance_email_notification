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

import datetime
import operator
import requests
from time import time
from influxdb import InfluxDBClient
import numpy as np
from os import environ


SELECT_LAST_BUILDS_ID = "select distinct(id) from (select build_id as id, pct95 from api_comparison where " \
                        "simulation=\'{}\' and test_type=\'{}\' and \"users\"=\'{}\' " \
                        "and build_id!~/audit_{}_/ order by time DESC) GROUP BY time(1s) order by DESC limit {}"

SELECT_LAST_BUILD_DATA = "select * from api_comparison where build_id=\'{}\'"

SELECT_USERS_COUNT = "select sum(\"max\") from (select max(\"user_count\") from \"users\" where " \
                     "build_id='{}' group by lg_id)"

SELECT_TEST_DATA = "select response_time from {} where build_id='{}' and request_name='{}' and method='{}'"

SELECT_TEST_DATA_OFFSET = "select response_time from {} where build_id='{}' and request_name='{}' and method='{}'" \
                          " and time>'{}' limit {}"

GET_REQUEST_NAMES = "show tag values on {} from {} with key=\"request_name\" where build_id='{}'"

GET_REQUEST_METHODS = "show tag values on {} from {} with key=\"method\" where build_id='{}' and request_name='{}'"

TOTAL_REQUEST_COUNT = "select count(\"response_time\") from {} where build_id='{}'"

FIRST_REQUEST = "select first(\"response_time\") from {} where build_id='{}'"

LAST_REQUEST = "select last(\"response_time\") from {} where build_id='{}'"

REQUEST_COUNT = "select count(\"response_time\") from {} where build_id='{}' and request_name='{}' and method='{}'"

REQUEST_MIN = "select min(\"response_time\") from {} where build_id='{}' and request_name='{}' and method='{}'"

REQUEST_MAX = "select max(\"response_time\") from {} where build_id='{}' and request_name='{}' and method='{}'"

REQUEST_MEAN = "select mean(\"response_time\") from {} where build_id='{}' and request_name='{}' and method='{}'"

SELECT_PERCENTILE = "select percentile(\"response_time\", {}) as \"pct\" from {} where build_id='{}' and" \
                    " request_name='{}' and method='{}'"

REQUEST_STATUS = "select count(\"response_time\") from {} where build_id='{}' and request_name='{}' and method='{}'" \
                 " and status='{}'"

REQUEST_STATUS_CODE = "select count(\"response_time\") from {} where build_id='{}' and request_name='{}' " \
                      "and method='{}' and status_code=~/^{}/"

REQUEST_STATUS_CODE_NAN = "select count(\"response_time\") from {} where build_id='{}' and request_name='{}' " \
                          "and method='{}' and status_code!~/1/ and status_code!~/2/ and status_code!~/3/ " \
                          "and status_code!~/4/ and status_code!~/5/"

CALCULATE_TOTAL_THROUGHPUT = "select  sum(throughput) as \"throughput\", sum(ko) as \"ko\", " \
                             "sum(total) as \"total\" from api_comparison where build_id='{}'"

CALCULATE_ALL_AGGREGATION = "select max(response_time), min(response_time), ROUND(MEAN(response_time)) " \
                            "as avg, PERCENTILE(response_time, 95) as pct95, PERCENTILE(response_time, 50) " \
                            "as pct50 from {} where build_id='{}'"

DELETE_TEST_DATA = "delete from {} where build_id='{}'"

DELETE_USERS_DATA = "delete from \"users\" where build_id='{}'"

COMPARISON_RULES = {"gte": "ge", "lte": "le", "gt": "gt", "lt": "lt", "eq": "eq"}

BATCH_SIZE = int(environ.get("BATCH_SIZE", 5000000))


class DataManager(object):
    def __init__(self, arguments, galloper_url, token, project_id, logger=None):
        self.args = arguments
        self.galloper_url = galloper_url
        self.token = token
        self.project_id = project_id
        self.last_build_data = None
        
        # Create default logger if not provided
        if logger is None:
            import logging
            logger = logging.getLogger(__name__)
            if not logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
                logger.addHandler(handler)
                logger.setLevel(logging.INFO)
        
        self.logger = logger
        self.client = InfluxDBClient(self.args["influx_host"], self.args['influx_port'],
                                     username=self.args['influx_user'], password=self.args['influx_password'])

    def delete_test_data(self):
        self.client.switch_database(self.args['influx_db'])
        self.client.query(DELETE_TEST_DATA.format(self.args["simulation"], self.args["build_id"]))
        self.client.query(DELETE_USERS_DATA.format(self.args["build_id"]))

    def write_comparison_data_to_influx(self):
        timestamp = time()
        user_count = self.get_user_count()
        self.logger.info(f"build_id={self.args['build_id']}")
        self.client.switch_database(self.args['influx_db'])
        total_requests_count = int(list(self.client.query(TOTAL_REQUEST_COUNT
                                                          .format(self.args['simulation'],
                                                                  self.args['build_id'])).get_points())[0]["count"])
        self.logger.info(f"Total requests count = {total_requests_count}")

        # Get request names and methods
        request_names = list(self.client.query(GET_REQUEST_NAMES.format(self.args['influx_db'], self.args['simulation'],
                                                                        self.args['build_id'])).get_points())
        request_names = list(each['value'] for each in request_names)
        reqs = []
        for request_name in request_names:
            methods = list(self.client.query(GET_REQUEST_METHODS.format(self.args['influx_db'], self.args['simulation'],
                                                                        self.args['build_id'],
                                                                        request_name)).get_points())
            for method in methods:
                reqs.append({
                    "request_name": request_name,
                    "method": method["value"]
                })

        # calculate test duration and throughput
        first_request = self.client.query(FIRST_REQUEST.format(self.args['simulation'], self.args['build_id']))
        first_request = list(first_request.get_points())
        last_request = self.client.query(LAST_REQUEST.format(self.args['simulation'], self.args['build_id']))
        last_request = list(last_request.get_points())
        start_time = int(str(datetime.datetime.strptime(first_request[0]['time'],
                                                        "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()).split(".")[0]) \
                     - int(int(first_request[0]['first']) / 1000)
        end_time = int(str(datetime.datetime.strptime(last_request[0]['time'],
                                                      "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()).split(".")[0])
        duration = end_time - start_time
        _throughput = round(float(total_requests_count / duration), 3)
        self.logger.info(f"duration = {duration}")
        self.logger.info(f"throughput = {_throughput}")

        data = np.array([])
        for req in reqs:
            req['simulation'] = self.args['simulation']
            req['test_type'] = self.args['type']
            req['env'] = self.args['env']
            req['build_id'] = self.args['build_id']
            req["total"] = int(list(self.client.query(REQUEST_COUNT.format(self.args['simulation'],
                                                                           self.args['build_id'], req['request_name'],
                                                                           req['method'])).get_points())[0]["count"])
            req["throughput"] = round(float(req["total"]) / float(duration), 3)
            req["times"] = np.array([])

            # calculate response time metrics per request
            response_time_q = SELECT_TEST_DATA.format(self.args['simulation'], self.args['build_id'],
                                                      req["request_name"], req["method"])
            if req["total"] <= BATCH_SIZE:
                _data = list(self.client.query(response_time_q).get_points())
                req["times"] = np.append(req["times"], list(int(each["response_time"]) for each in _data))
            else:
                shards = req["total"] // BATCH_SIZE
                last_read_time = '1970-01-01T19:25:26.005Z'
                for i in range(shards):
                    response_time_q = SELECT_TEST_DATA_OFFSET.format(self.args['simulation'], self.args['build_id'],
                                                                     req['request_name'], req['method'],
                                                                     last_read_time, BATCH_SIZE)
                    _data = list(self.client.query(response_time_q).get_points())
                    last_read_time = _data[-1]['time']
                    req["times"] = np.append(req["times"], list(int(each["response_time"]) for each in _data))

                if req["total"] % BATCH_SIZE != 0:
                    response_time_q = SELECT_TEST_DATA_OFFSET.format(self.args['simulation'], self.args['build_id'],
                                                                     req['request_name'], req['method'],
                                                                     last_read_time, BATCH_SIZE)
                    _data = list(self.client.query(response_time_q).get_points())
                    req["times"] = np.append(req["times"], list(int(each["response_time"]) for each in _data))
            data = np.append(data, req["times"])

            req["min"] = req.get("times").min()
            req["max"] = req.get("times").max()
            req["mean"] = req.get("times").mean()

            for pct in ["50", "75", "90", "95", "99"]:
                req[f"pct{pct}"] = int(np.percentile(req.get("times"), int(pct), interpolation="linear"))

            del req["times"]

            # calculate status and status codes per request
            ok_count = list(self.client.query(REQUEST_STATUS.format(self.args['simulation'],
                                                                    self.args['build_id'], req['request_name'],
                                                                    req['method'], "OK")).get_points())
            req["OK"] = ok_count[0]["count"] if len(ok_count) > 0 else 0
            ko_count = list(self.client.query(REQUEST_STATUS.format(self.args['simulation'],
                                                                    self.args['build_id'], req['request_name'],
                                                                    req['method'], "KO")).get_points())
            req["KO"] = ko_count[0]["count"] if len(ko_count) > 0 else 0
            for code in ["1", "2", "3", "4", "5"]:
                _tmp = list(self.client.query(REQUEST_STATUS_CODE.format(self.args['simulation'],
                                                                         self.args['build_id'], req['request_name'],
                                                                         req['method'], code)).get_points())
                req[f"{code}xx"] = _tmp[0]["count"] if len(_tmp) > 0 else 0

            _NaN = list(self.client.query(REQUEST_STATUS_CODE_NAN.format(self.args['simulation'],
                                                                         self.args['build_id'], req['request_name'],
                                                                         req['method'])).get_points())
            req["NaN"] = _NaN[0]["count"] if len(_NaN) > 0 else 0

        # calculate overall response time metrics
        response_times = {
            "min": round(float(data.min()), 2),
            "max": round(float(data.max()), 2),
            "mean": round(float(data.mean()), 2),
            "pct50": int(np.percentile(data, 50, interpolation="linear")),
            "pct75": int(np.percentile(data, 75, interpolation="linear")),
            "pct90": int(np.percentile(data, 90, interpolation="linear")),
            "pct95": int(np.percentile(data, 95, interpolation="linear")),
            "pct99": int(np.percentile(data, 99, interpolation="linear"))
        }

        # Write data to comparison db
        if not reqs:
            self.logger.error("No requests in the test")
            raise Exception("No requests in the test")
        points = []
        for req in reqs:
            influx_record = {
                "measurement": "api_comparison",
                "tags": {
                    "simulation": req['simulation'],
                    "env": req['env'],
                    "users": user_count,
                    "test_type": req['test_type'],
                    "build_id": req['build_id'],
                    "request_name": req['request_name'],
                    "method": req['method'],
                    "duration": duration
                },
                "time": datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%SZ'),
                "fields": {
                    "throughput": round(float(req["total"]) / float(duration), 3),
                    "total": req["total"],
                    "ok": req["OK"],
                    "ko": req["KO"],
                    "1xx": req["1xx"],
                    "2xx": req["2xx"],
                    "3xx": req["3xx"],
                    "4xx": req["4xx"],
                    "5xx": req["5xx"],
                    "NaN": req["NaN"],
                    "min": float(req["min"]),
                    "max": float(req["max"]),
                    "mean": round(float(req["mean"]), 2),
                    "pct50": req["pct50"],
                    "pct75": req["pct75"],
                    "pct90": req["pct90"],
                    "pct95": req["pct95"],
                    "pct99": req["pct99"],
                }
            }
            points.append(influx_record)

        # Summary
        points.append({"measurement": "api_comparison", "tags": {"simulation": self.args['simulation'],
                                                                 "env": self.args['env'], "users": user_count,
                                                                 "test_type": self.args['type'], "duration": duration,
                                                                 "build_id": self.args['build_id'],
                                                                 "request_name": "All", "method": "All"},
                       "time": datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%SZ'),
                       "fields": {"throughput": _throughput, "total": total_requests_count,
                                  "ok": sum(point['fields']['ok'] for point in points),
                                  "ko": sum(point['fields']['ko'] for point in points),
                                  "1xx": sum(point['fields']['1xx'] for point in points),
                                  "2xx": sum(point['fields']['2xx'] for point in points),
                                  "3xx": sum(point['fields']['3xx'] for point in points),
                                  "4xx": sum(point['fields']['4xx'] for point in points),
                                  "5xx": sum(point['fields']['5xx'] for point in points),
                                  "NaN": sum(point['fields']['NaN'] for point in points),
                                  "min": response_times["min"], "max": response_times["max"],
                                  "mean": response_times["mean"], "pct50": response_times["pct50"],
                                  "pct75": response_times["pct75"], "pct90": response_times["pct90"],
                                  "pct95": response_times["pct95"], "pct99": response_times["pct99"]}})
        try:
            self.client.switch_database(self.args['comparison_db'])
            self.client.write_points(points)
        except Exception as e:
            self.logger.error(e)
            self.logger.error("Failed connection to " + self.args["influx_host"] + ", database - comparison")
        return user_count, duration, response_times

    def get_api_test_info(self):
        tests_data = self.get_last_builds()
        if len(tests_data) == 0:
            raise Exception("No data found for given parameters")
        last_test_data = tests_data[0]
        self.args['build_id'] = tests_data[0][0]['build_id']
        baseline = self.get_baseline()
        total_checked, violations, thresholds = self.get_thresholds(last_test_data, add_green=True)
        # Update args with calculated SLA failed rate (overwrite old value from event)
        self.args['missed_threshold_rate'] = violations
        # Calculate Baseline failed rate in Lambda (overwrite old value from event)
        if baseline:
            performance_degradation_rate, compare_with_baseline, baseline_debug = self.compare_with_baseline(baseline, last_test_data, thresholds)
            self.args['performance_degradation_rate'] = performance_degradation_rate
            self.args['baseline_debug'] = baseline_debug
        return tests_data, last_test_data, baseline, violations, thresholds

    def get_last_builds(self):
        self.client.switch_database(self.args['comparison_db'])
        tests_data = []
        build_ids = []
        
        last_builds = self.client.query(SELECT_LAST_BUILDS_ID.format(
            self.args['test'], self.args['test_type'], str(self.args['users']), self.args['test'],
            str(self.args['test_limit'])))
        for test in list(last_builds.get_points()):
            if test['distinct'] not in build_ids:
                build_ids.append(test['distinct'])

        for _id in build_ids:
            test_data = self.client.query(SELECT_LAST_BUILD_DATA.format(_id))
            test_points = list(test_data.get_points())
            tests_data.append(test_points)
        return tests_data

    def get_user_count(self):
        self.client.switch_database(self.args['influx_db'])
        try:
            data = self.client.query(SELECT_USERS_COUNT.format(self.args['build_id']))
            data = list(data.get_points())[0]
            return int(data['sum'])
        except Exception as e:
            self.logger.error(e)
        return 0

    def compare_with_baseline(self, baseline=None, last_build=None, thresholds=None):
        if not baseline:
            baseline = self.get_baseline()
        if not last_build:
            last_build = self.get_last_build()
        comparison_metric = self.args['comparison_metric']
        compare_with_baseline = []
        if not baseline:
            self.logger.warning("Baseline not found")
            return 0, []
        
        # Get deviations from Quality Gate config for baseline (independent of SLA thresholds)
        quality_gate_config = self.args.get('quality_gate_config', {})
        settings = quality_gate_config.get('settings', {})
        summary_results = settings.get('summary_results', {})
        per_request_results = settings.get('per_request_results', {})
        
        # Set baseline deviations from Quality Gate (always use these for baseline)
        all_tp_deviation = summary_results.get('throughput_deviation', 0)
        all_er_deviation = summary_results.get('error_rate_deviation', 0)
        all_rt_deviation = summary_results.get('response_time_deviation', 0)
        every_rt_deviation = per_request_results.get('response_time_deviation', 0)
        
        # Fetch SLA thresholds for potential use (but baseline uses Quality Gate deviations)
        headers = {'Authorization': f'bearer {self.token}'} if self.token else {}
        thresholds_url = f"{self.galloper_url}/api/v1/backend_performance/thresholds/{self.project_id}?" \
                         f"test={self.args['simulation']}&env={self.args['env']}&order=asc"
        try:
            unfiltered_thresholds = requests.get(thresholds_url, headers={**headers, 'Content-type': 'application/json'}).json()
        except Exception as e:
            self.logger.error(f"Failed to fetch thresholds for baseline: {e}")
            unfiltered_thresholds = []
        
        every_rt_found = False  # Track if 'every' threshold exists
        
        # Track which thresholds were found for debug
        thresholds_found = []
        all_thresholds_debug = []  # Store ALL thresholds for debugging
        
        # First, log all thresholds we received
        for th in unfiltered_thresholds:
            # Show both request_name and scope in debug (API may use either)
            req_name = th.get('request_name', 'N/A')
            scope = th.get('scope', 'N/A')
            all_thresholds_debug.append(f"req_name={req_name}, scope={scope}, target={th.get('target', 'N/A')}, agg={th.get('aggregation', 'N/A')}, dev={th.get('deviation', 0)}")
        
        for th in unfiltered_thresholds:
            # Check both 'request_name' and 'scope' fields for 'all'/'every' (API may use either)
            req_name = th.get('request_name', '').lower()
            scope_name = th.get('scope', '').lower()
            
            # Get deviation from Quality Gate config (unified for baseline, ignore threshold deviation)
            quality_gate_config = self.args.get('quality_gate_config', {})
            settings = quality_gate_config.get('settings', {})
            
            # Determine which config section to use based on scope
            if scope_name == 'all' or req_name == 'all':
                config_section = settings.get('summary_results', {})
            else:
                config_section = settings.get('per_request_results', {})
            
            # Get deviation for specific target type from Quality Gate
            if th.get('target') == 'response_time':
                deviation = config_section.get('response_time_deviation', 0)
            elif th.get('target') == 'throughput':
                deviation = config_section.get('throughput_deviation', 0)
            elif th.get('target') == 'error_rate':
                deviation = config_section.get('error_rate_deviation', 0)
            
            if req_name == 'all' or scope_name == 'all':
                if th.get('target') == 'throughput':
                    if all_tp_deviation == 0:  # Take first found, ignore duplicates
                        all_tp_deviation = deviation
                        thresholds_found.append(f"all/throughput: dev={all_tp_deviation}")
                elif th.get('target') == 'error_rate':
                    if all_er_deviation == 0:  # Take first found, ignore duplicates
                        all_er_deviation = deviation
                        thresholds_found.append(f"all/error_rate: dev={all_er_deviation}")
                elif th.get('target') == 'response_time':
                    if all_rt_deviation == 0:  # Take first found, ignore duplicates
                        all_rt_deviation = deviation
                        thresholds_found.append(f"all/response_time: dev={all_rt_deviation}, agg={th.get('aggregation', 'N/A')}")
            elif req_name == 'every' or scope_name == 'every':
                if th.get('target') == 'response_time':
                    if not every_rt_found:  # Take first found, ignore duplicates
                        every_rt_deviation = deviation
                        every_rt_found = True
                        thresholds_found.append(f"every/response_time: dev={every_rt_deviation}, agg={th.get('aggregation', 'N/A')}")
        
        # Get Quality Gate settings to check which metrics are enabled
        quality_gate_config = self.args.get('quality_gate_config', {})
        baseline_enabled = quality_gate_config.get('baseline', {}).get('checked', False)
        
        summary_rt_check = False
        summary_er_check = False
        summary_tp_check = False
        per_request_rt_check = False
        per_request_er_check = False
        per_request_tp_check = False
        
        if baseline_enabled:
            settings = quality_gate_config.get('settings', {})
            summary_results = settings.get('summary_results', {})
            per_request_results = settings.get('per_request_results', {})
            
            summary_rt_check = summary_results.get('check_response_time', False)
            summary_er_check = summary_results.get('check_error_rate', False)
            summary_tp_check = summary_results.get('check_throughput', False)
            per_request_rt_check = per_request_results.get('check_response_time', False)
            per_request_er_check = per_request_results.get('check_error_rate', False)
            per_request_tp_check = per_request_results.get('check_throughput', False)
        
        # Compare metrics
        total_comparisons = 0
        total_violated = 0
        
        # Track for debug info
        baseline_debug = {
            "summary_rt_check": summary_rt_check,
            "summary_er_check": summary_er_check,
            "summary_tp_check": summary_tp_check,
            "per_request_rt_check": per_request_rt_check,
            "per_request_er_check": per_request_er_check,
            "per_request_tp_check": per_request_tp_check,
            "all_passed": 0,
            "all_failed": 0,
            "individual_passed": 0,
            "individual_failed": 0,
            "individual_details": [],
            "all_details": []
        }
        
        # Process per-request comparisons (exclude "All" row - will be processed separately)
        for request in last_build:
            # Skip "All" row in per-request processing (same as SLA logic)
            if request.get('request_name', '').lower() == 'all':
                continue
            
            # Only check individual requests if Per request results response_time is enabled
            # Note: Individual requests only check response_time (not ER/TP)
            if not per_request_rt_check:
                continue
                
            for baseline_request in baseline:
                if request['request_name'] == baseline_request['request_name']:
                    total_comparisons += 1
                    # Use 'every' deviation if 'every' threshold exists, otherwise fallback to 'all'
                    # IMPORTANT: If 'every' exists with deviation=0, use 0 (don't fallback to 'all')
                    rt_deviation = per_request_results.get('response_time_deviation', 0)
                    # Apply deviation to baseline value (for response_time, higher threshold is worse)
                    # NOTE: Convert to seconds and round to 2 decimal places for consistency with SLA
                    baseline_value_with_deviation = round((float(baseline_request[comparison_metric]) + rt_deviation) / 1000, 2)
                    current_val = round(float(request[comparison_metric]) / 1000, 2)
                    baseline_val = round(float(baseline_request[comparison_metric]) / 1000, 2)
                    failed = current_val > baseline_value_with_deviation
                    
                    if failed:
                        total_violated += 1
                        baseline_debug["individual_failed"] += 1
                        compare_with_baseline.append({"request_name": request['request_name'],
                                                      "response_time": request[comparison_metric],
                                                      "baseline": baseline_request[comparison_metric]
                                                      })
                    else:
                        baseline_debug["individual_passed"] += 1
                    
                    # Store detailed info (limit to first 15 to avoid huge emails)
                    if len(baseline_debug["individual_details"]) < 15:
                        baseline_debug["individual_details"].append({
                            "name": request['request_name'],
                            "current": current_val,
                            "baseline": baseline_val,
                            "baseline_with_dev": baseline_value_with_deviation,
                            "deviation": round(rt_deviation / 1000, 2),  # Convert deviation to seconds for display
                            "result": "FAIL" if failed else "PASS"
                        })
                    break  # Found matching baseline, no need to continue inner loop
        
        # Process global "All" row separately (check all 3 metrics: throughput, error_rate, response_time)
        # Find "All" row in last_build (case-insensitive)
        all_row_current = next((req for req in last_build if req.get('request_name', '').lower() == 'all'), None)
        all_row_baseline = next((req for req in baseline if req.get('request_name', '').lower() == 'all'), None)
        
        if all_row_current and all_row_baseline:
            # Check all 3 metrics for "All" row (like SLA scope="all")
            # Only check each metric if Summary results checkbox is enabled
            # Calculate error_rate for both current and baseline (not stored as field)
            
            def calculate_baseline_metric(request, target):
                if target == 'response_time':
                    original_metric = request[comparison_metric]
                    metric = round(original_metric / 1000, 2)
                elif target == 'throughput':
                    metric = round(float(request['throughput']), 2)
                elif target == 'error_rate':
                    metric = round(float(request['ko'] / request['total']) * 100, 2)
                return metric
            
            current_error_rate = calculate_baseline_metric(all_row_current, 'error_rate')
            baseline_error_rate = calculate_baseline_metric(all_row_baseline, 'error_rate')
            
            # Throughput check (only if summary_tp_check enabled)
            if summary_tp_check:
                total_comparisons += 1
                current_tp = calculate_baseline_metric(all_row_current, 'throughput')
                baseline_tp = calculate_baseline_metric(all_row_baseline, 'throughput')
                baseline_throughput_with_dev = round(baseline_tp - all_tp_deviation, 2)
                tp_failed = current_tp < baseline_throughput_with_dev
                if tp_failed:
                    total_violated += 1
                    baseline_debug["all_failed"] += 1
                    compare_with_baseline.append({"request_name": all_row_current['request_name'],
                                                  "response_time": all_row_current['throughput'],
                                                  "baseline": all_row_baseline['throughput'],
                                                  "metric": "throughput"
                                                  })
                else:
                    baseline_debug["all_passed"] += 1
                
                baseline_debug["all_details"].append({
                    "metric": "throughput",
                    "current": round(all_row_current['throughput'], 2),
                    "baseline": round(all_row_baseline['throughput'], 2),
                    "baseline_with_dev": round(baseline_throughput_with_dev, 2),
                    "deviation": all_tp_deviation,
                    "comparison": "<",
                    "result": "FAIL" if tp_failed else "PASS"
                })
            
            # Error rate check (only if summary_er_check enabled)
            if summary_er_check:
                total_comparisons += 1
                baseline_error_rate_with_dev = round(baseline_error_rate + all_er_deviation, 2)
                er_failed = current_error_rate > baseline_error_rate_with_dev
                if er_failed:
                    total_violated += 1
                    baseline_debug["all_failed"] += 1
                    compare_with_baseline.append({"request_name": all_row_current['request_name'],
                                                  "response_time": current_error_rate,
                                                  "baseline": baseline_error_rate,
                                                  "metric": "error_rate"
                                                  })
                else:
                    baseline_debug["all_passed"] += 1
                
                baseline_debug["all_details"].append({
                    "metric": "error_rate",
                    "current": round(current_error_rate, 2),
                    "baseline": round(baseline_error_rate, 2),
                    "baseline_with_dev": round(baseline_error_rate_with_dev, 2),
                    "deviation": all_er_deviation,
                    "comparison": ">",
                    "result": "FAIL" if er_failed else "PASS"
                })
            
            # Response time check (only if summary_rt_check enabled)
            if summary_rt_check:
                total_comparisons += 1
                current_rt = calculate_baseline_metric(all_row_current, 'response_time')
                baseline_rt = calculate_baseline_metric(all_row_baseline, 'response_time')
                baseline_rt_with_dev = round(baseline_rt + all_rt_deviation, 2)
                rt_failed = current_rt > baseline_rt_with_dev
                if rt_failed:
                    total_violated += 1
                    baseline_debug["all_failed"] += 1
                    compare_with_baseline.append({"request_name": all_row_current['request_name'],
                                                  "response_time": all_row_current[comparison_metric],
                                                  "baseline": all_row_baseline[comparison_metric],
                                                  "metric": comparison_metric
                                                  })
                else:
                    baseline_debug["all_passed"] += 1
                
                baseline_debug["all_details"].append({
                    "metric": "response_time",
                "current": round(all_row_current[comparison_metric], 2),
                "baseline": round(all_row_baseline[comparison_metric], 2),
                "baseline_with_dev": round(baseline_rt_with_dev, 2),
                "deviation": all_rt_deviation,
                "comparison": ">",
                "result": "FAIL" if rt_failed else "PASS"
            })
        
        # Calculate degradation rate based on all comparisons
        if total_comparisons > 0:
            performance_degradation_rate = round(float(total_violated / total_comparisons) * 100, 2)
        else:
            performance_degradation_rate = 0
            
        # Add final counts to debug
        baseline_debug["total_comparisons"] = total_comparisons
        baseline_debug["total_violated"] = total_violated
        baseline_debug["performance_degradation_rate"] = performance_degradation_rate
            
        return performance_degradation_rate, compare_with_baseline, baseline_debug

    def compare_with_thresholds(self):
        last_build = self.get_last_build()
        return self.get_thresholds(last_build)

    def get_baseline(self):
        headers = {'Authorization': f'bearer {self.token}'} if self.token else {}
        baseline_url = f"{self.galloper_url}/api/v1/backend_performance/baseline/{self.project_id}?" \
                       f"test_name={self.args['simulation']}&env={self.args['env']}"
        res = requests.get(baseline_url, headers={**headers, 'Content-type': 'application/json'}).json()
        return res["baseline"]

    def get_last_build(self):
        if self.last_build_data:
            return self.last_build_data
        self.client.switch_database(self.args['comparison_db'])
        test_data = self.client.query(SELECT_LAST_BUILD_DATA.format(self.args['build_id']))
        self.last_build_data = list(test_data.get_points())
        return self.last_build_data

    def compare_request_and_threhold(self, request, threshold):
        comparison_method = getattr(operator, COMPARISON_RULES[threshold['comparison']])
        
        # Store original value for debug
        original_metric = None
        
        if threshold['target'] == 'response_time':
            original_metric = request[threshold['aggregation']] if threshold['aggregation'] != "avg" else request["mean"]
            metric = original_metric
            # Convert milliseconds to seconds and round to 2 decimal places for comparison
            metric = round(metric / 1000, 2)
        elif threshold['target'] == 'throughput':
            metric = request['throughput']
            # Round throughput to 2 decimal places for comparison
            metric = round(metric, 2)
        else:  # Will be in case error_rate is set as target
            metric = round(float(request['ko'] / request['total']) * 100, 2)
        
        # Apply deviation if exists (acceptable deviation from threshold)
        # IMPORTANT: threshold['value'] is in milliseconds for response_time, needs conversion
        threshold_value = threshold['value']
        original_threshold = threshold_value
        
        # Get deviation from Quality Gate config based on threshold scope and target
        # Deviation is ALWAYS from Quality Gate, threshold deviation is ignored (always 0)
        quality_gate_config = self.args.get('quality_gate_config', {})
        settings = quality_gate_config.get('settings', {})
        
        # Determine which section to use based on threshold scope
        threshold_scope = threshold.get('scope', '').lower()
        if threshold_scope == 'all':
            # Use summary_results deviation for "all" scope
            config_section = settings.get('summary_results', {})
        else:
            # Use per_request_results deviation for "every" and individual scopes
            config_section = settings.get('per_request_results', {})
        
        # Get deviation based on target type from Quality Gate
        if threshold['target'] == 'response_time':
            deviation = config_section.get('response_time_deviation', 0)
        elif threshold['target'] == 'throughput':
            deviation = config_section.get('throughput_deviation', 0)
        elif threshold['target'] == 'error_rate':
            deviation = config_section.get('error_rate_deviation', 0)
        
        # For response_time: convert both threshold and deviation to seconds before applying
        if threshold['target'] == 'response_time':
            # Convert threshold from milliseconds to seconds
            threshold_value = threshold_value / 1000
            # Convert deviation from milliseconds to seconds
            deviation = deviation / 1000
        
        # For "greater than" comparisons, add deviation to threshold
        # For "less than" comparisons, subtract deviation from threshold
        if threshold['comparison'] in ['gt', 'gte']:
            # Allow metric to be higher by deviation amount before marking as red
            threshold_value = threshold_value + deviation
        elif threshold['comparison'] in ['lt', 'lte']:
            # Allow metric to be lower by deviation amount before marking as red
            threshold_value = threshold_value - deviation
        
        # Round threshold value to 2 decimal places for comparison
        threshold_value = round(threshold_value, 2)
        
        result = comparison_method(metric, threshold_value)
        color = "red" if result else "green"
        
        # Debug: store comparison details if debug mode enabled
        if self.args.get('sla_debug_enabled', False):
            if not hasattr(self, '_debug_comparisons'):
                self._debug_comparisons = []
            if len(self._debug_comparisons) < 15:
                debug_entry = {
                    'request': request.get('request_name', 'unknown'),
                    'target': threshold['target'],
                    'metric_original': original_metric if original_metric else metric,
                    'metric_rounded': metric,
                    'comparison': threshold['comparison'],
                    'threshold_original': original_threshold,
                    'deviation': threshold.get('deviation', 0),
                    'threshold_with_deviation': threshold_value,
                    'result': result,
                    'color': color
                }
                self._debug_comparisons.append(debug_entry)
        
        return color, metric

    def aggregate_test(self):
        self.client.switch_database(self.args['influx_db'])
        all_metics: list = list(self.client.query(
            CALCULATE_ALL_AGGREGATION.format(self.args['simulation'], self.args['build_id'])).get_points())
        self.client.switch_database(self.args['comparison_db'])
        tp: list = list(self.client.query(CALCULATE_TOTAL_THROUGHPUT.format(self.args['build_id'])).get_points())
        aggregated_dict = all_metics[0]
        aggregated_dict['throughput'] = round(tp[0]['throughput'], 2)
        aggregated_dict['ko'] = tp[0]['ko']
        aggregated_dict['total'] = tp[0]['total']
        aggregated_dict['request_name'] = 'all'
        return aggregated_dict


    def get_thresholds(self, test, add_green=False):
        compare_with_thresholds = []
        total_checked = 0
        total_violated = 0
        headers = {'Authorization': f'bearer {self.token}'} if self.token else {}
        thresholds_url = f"{self.galloper_url}/api/v1/backend_performance/thresholds/{self.project_id}?" \
                         f"test={self.args['simulation']}&env={self.args['env']}&order=asc"
        _thresholds = requests.get(thresholds_url, headers={**headers, 'Content-type': 'application/json'}).json()

        # Check what SLA metrics are actually configured BEFORE filtering by comparison_metric
        # This is used for warning generation in report_builder
        has_response_time_sla = any(th.get('target') == 'response_time' for th in _thresholds)
        has_error_rate_sla = any(th.get('target') == 'error_rate' for th in _thresholds)
        has_throughput_sla = any(th.get('target') == 'throughput' for th in _thresholds)
        
        # Store flags for report_builder to check
        if not has_response_time_sla:
            self.args['sla_no_response_time'] = True
        if not has_error_rate_sla:
            self.args['sla_no_error_rate'] = True
        if not has_throughput_sla:
            self.args['sla_no_throughput'] = True

        # Get comparison_metric (default to pct95 if not specified)
        comparison_metric = self.args.get('comparison_metric', 'pct95')
        
        # Filter thresholds by comparison_metric for response_time targets
        filtered_thresholds = []
        for th in _thresholds:
            if th['target'] == 'response_time':
                # For response_time, only include if aggregation matches comparison_metric
                if th.get('aggregation') == comparison_metric:
                    filtered_thresholds.append(th)
            else:
                # For throughput and error_rate, include all (no aggregation field)
                filtered_thresholds.append(th)
        
        _thresholds = filtered_thresholds

        # Get Quality Gate settings to check which metrics are enabled
        quality_gate_config = self.args.get('quality_gate_config', {})
        sla_enabled = quality_gate_config.get('SLA', {}).get('checked', False)
        
        summary_rt_check = False
        summary_er_check = False
        summary_tp_check = False
        per_request_rt_check = False
        per_request_er_check = False
        per_request_tp_check = False
        
        if sla_enabled:
            settings = quality_gate_config.get('settings', {})
            summary_results = settings.get('summary_results', {})
            per_request_results = settings.get('per_request_results', {})
            
            summary_rt_check = summary_results.get('check_response_time', False)
            summary_er_check = summary_results.get('check_error_rate', False)
            summary_tp_check = summary_results.get('check_throughput', False)
            per_request_rt_check = per_request_results.get('check_response_time', False)
            per_request_er_check = per_request_results.get('check_error_rate', False)
            per_request_tp_check = per_request_results.get('check_throughput', False)
        
        def compile_violation(request, th, total_checked, total_violated, compare_with_thresholds, add_green=False):
            # Check if this threshold should be processed based on Quality Gate settings
            scope = th.get('scope', '').lower()
            target = th['target']
            
            # Skip threshold if metric is disabled in Quality Gate
            # For "all" scope: check summary_results settings
            if scope == 'all':
                if target == 'response_time' and not summary_rt_check:
                    return total_checked, total_violated, compare_with_thresholds
                if target == 'error_rate' and not summary_er_check:
                    return total_checked, total_violated, compare_with_thresholds
                if target == 'throughput' and not summary_tp_check:
                    return total_checked, total_violated, compare_with_thresholds
            # For "every" scope (or specific request names): check per_request_results settings
            else:
                if target == 'response_time' and not per_request_rt_check:
                    return total_checked, total_violated, compare_with_thresholds
                if target == 'error_rate' and not per_request_er_check:
                    return total_checked, total_violated, compare_with_thresholds
                if target == 'throughput' and not per_request_tp_check:
                    return total_checked, total_violated, compare_with_thresholds
            
            # If we got here, metric is enabled - always count it
            total_checked += 1
            
            color, metric = self.compare_request_and_threhold(request, th)
            
            # Get deviation from Quality Gate config (always, since thresholds don't have deviation)
            quality_gate_config = self.args.get('quality_gate_config', {})
            settings = quality_gate_config.get('settings', {})
            threshold_scope = th.get('scope', '').lower()
            
            if threshold_scope == 'all':
                config_section = settings.get('summary_results', {})
            else:
                config_section = settings.get('per_request_results', {})
            
            if th['target'] == 'response_time':
                deviation = config_section.get('response_time_deviation', 0)
            elif th['target'] == 'throughput':
                deviation = config_section.get('throughput_deviation', 0)
            elif th['target'] == 'error_rate':
                deviation = config_section.get('error_rate_deviation', 0)
            else:
                deviation = 0
            
            if add_green or color != "green":
                compare_with_thresholds.append({
                    "request_name": request['request_name'],
                    "target": th['target'],
                    "aggregation": th.get("aggregation"),
                    "metric": metric,
                    "threshold": color,
                    "value": th["value"],
                    "deviation": deviation,
                    "comparison": th.get("comparison", "gt")
                })
            # Count violation if color is red (not green)
            if color != "green":
                total_violated += 1
            return total_checked, total_violated, compare_with_thresholds
        
        globaly_applicable: list = list(filter(lambda _th: _th.get('scope', '').lower() == 'all', _thresholds))
        every_applicable: list = list(filter(lambda _th: _th.get('scope', '').lower() == 'every', _thresholds))
        individual: list = list(filter(lambda _th: _th.get('scope', '').lower() not in ['every', 'all'], _thresholds))
        
        individual_dict: dict = dict()
        for each in individual:
            if each['scope'] not in individual_dict:
                individual_dict[each['scope']] = []
            individual_dict[each['scope']].append(each)
        
        # Process per-request thresholds with priority: individual > every
        # Exclude "All" row - it will be processed separately with global thresholds
        for request in test:
            # Skip "All" row in per-request processing
            if request.get('request_name', '').lower() == 'all':
                continue
            thresholds_to_check = []
            checked_targets = set()
            
            # Priority 1: Individual thresholds for this specific request
            # IMPORTANT: For individual requests, ONLY response_time makes sense per-request
            # error_rate and throughput should ONLY be checked at "all" level
            if request['request_name'] in individual_dict:
                for ind in individual_dict[request['request_name']]:
                    # Only add response_time thresholds for per-request checking
                    if ind['target'] == 'response_time':
                        thresholds_to_check.append(ind)
                        checked_targets.add(ind['target'])
            
            # Priority 2: Every thresholds (only if target not covered by individual)
            # IMPORTANT: For "every" scope, ONLY response_time makes sense per-request
            # error_rate and throughput should ONLY be checked at "all" level
            for th in every_applicable:
                if th['target'] not in checked_targets:
                    # Only add response_time thresholds for per-request checking
                    if th['target'] == 'response_time':
                        thresholds_to_check.append(th)
                        checked_targets.add(th['target'])
            
            # Check all selected thresholds for this request
            for th in thresholds_to_check:
                total_checked, total_violated, compare_with_thresholds = compile_violation(
                    request, th, total_checked, total_violated, compare_with_thresholds, add_green)
        
        # Process global "all" scope thresholds separately
        # Find "All" row in test data (aggregated metrics)
        if globaly_applicable:
            # Look for "All" row in test data (case-insensitive)
            all_row = next((req for req in test if req.get('request_name', '').lower() == 'all'), None)
            if all_row:
                # Create a copy and ensure request_name is lowercase for threshold matching
                all_row_copy = dict(all_row)
                all_row_copy['request_name'] = 'all'
                for th in globaly_applicable:
                    total_checked, total_violated, compare_with_thresholds = compile_violation(
                        all_row_copy, th, total_checked, total_violated, compare_with_thresholds, add_green)
            else:
                self.logger.warning("Warning: No 'All' row found in test data for global thresholds")
        
        violated = 0
        if total_checked:
            violated = round(float(total_violated / total_checked) * 100, 2)
        
        # Store debug info if enabled
        if self.args.get('sla_debug_enabled', False) and hasattr(self, '_debug_comparisons'):
            self.args['sla_debug_comparisons'] = self._debug_comparisons
        
        return total_checked, violated, compare_with_thresholds
