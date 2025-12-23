import requests


class ThresholdsComparison:
    METRICS_MAPPER = {
        "load_time": "load_time",
        "dom": "dom_processing",
        "tti": "time_to_interactive",
        "fcp": "first_contentful_paint",
        "lcp": "largest_contentful_paint",
        "tbt": "total_blocking_time",
        "cls": "cumulative_layout_shift",
        "fvc": "first_visual_change",
        "lvc": "last_visual_change",
        "ttfb": "time_to_first_byte",
        "inp": "interaction_to_next_paint"
    }

    def __init__(self, galloper_url, token, project_id, report_id):
        self.galloper_url = galloper_url
        self.token = token
        self.project_id = project_id
        self.report_id = report_id

    def get_thresholds_info(self):
        """Fetch thresholds from API."""
        url = f"{self.galloper_url}/api/v1/ui_performance/thresholds/{self.project_id}?report_id={self.report_id}"
        print(f"[HTTP REQUEST] {url}")

        resp = requests.get(
            url,
            headers={
                'Authorization': f'bearer {self.token}',
                'Content-type': 'application/json'
            }
        )

        print(f"[HTTP RESPONSE] {resp.status_code} for {url}")

        if resp.status_code != 200:
            print(f"[HTTP ERROR BODY] {resp.text[:500]}")
            raise Exception(f"Error fetching thresholds: {resp.status_code}")

        response_data = resp.json()

        if isinstance(response_data, dict) and 'rows' in response_data:
            return response_data['rows']
        elif isinstance(response_data, list):
            return response_data
        else:
            print(f"[WARNING] Unexpected response format: {type(response_data)}")
            return []

    def parse_thresholds_by_test_and_env(self, test_name, environment):
        """Filter thresholds by test name and environment."""
        all_thresholds = self.get_thresholds_info()

        filtered_thresholds = [
            threshold for threshold in all_thresholds
            if threshold.get('test') == test_name and threshold.get('environment') == environment
        ]

        print(f"[THRESHOLDS] Found {len(filtered_thresholds)} thresholds for test '{test_name}' in environment '{environment}'")
        return filtered_thresholds

    def get_thresholds_by_scope(self, test_name, environment, scope):
        """Get thresholds filtered by specific scope."""
        filtered_thresholds = self.parse_thresholds_by_test_and_env(test_name, environment)
        return [th for th in filtered_thresholds if th.get('scope') == scope]

    def get_thresholds_grouped_by_scope(self, test_name, environment):
        """Group thresholds by scope for easier lookup."""
        filtered_thresholds = self.parse_thresholds_by_test_and_env(test_name, environment)

        grouped = {}
        for threshold in filtered_thresholds:
            scope = threshold.get('scope')
            if scope not in grouped:
                grouped[scope] = []
            grouped[scope].append(threshold)

        return grouped

    @staticmethod
    def is_threshold_failed(actual_value, comparison, threshold_value):
        """Check if a threshold is violated based on comparison operator."""
        comparison_map = {
            'gte': lambda a, t: a >= t,
            'lte': lambda a, t: a <= t,
            'gt': lambda a, t: a > t,
            'lt': lambda a, t: a < t,
            'eq': lambda a, t: a == t
        }
        return comparison_map.get(comparison, lambda a, t: False)(actual_value, threshold_value)

    @staticmethod
    def get_aggregated_value(aggregation, values):
        """Aggregate a list of values based on aggregation type."""
        if not values:
            return 0

        aggregation_map = {
            'max': lambda v: max(v),
            'min': lambda v: min(v),
            'avg': lambda v: sum(v) / len(v),
            'median': lambda v: ThresholdsComparison._calculate_median(v),
            'pct95': lambda v: ThresholdsComparison._calculate_percentile(v, 0.95),
            'pct99': lambda v: ThresholdsComparison._calculate_percentile(v, 0.99)
        }

        return aggregation_map.get(aggregation, lambda v: 0)(values)

    @staticmethod
    def _calculate_median(values):
        """Calculate median value."""
        sorted_values = sorted(values)
        n = len(sorted_values)
        if n % 2 == 0:
            return (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2
        return sorted_values[n // 2]

    @staticmethod
    def _calculate_percentile(values, percentile):
        """Calculate percentile value."""
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def _evaluate_threshold(self, th, step_result, step_name=None):
        """Evaluate a single threshold and return result details."""
        is_failed = self.is_threshold_failed(step_result, th["comparison"], th["value"])
        status = "FAILED" if is_failed else "PASSED"

        print(f"Threshold: {th['scope']} {th['target']} {th['aggregation']} value {step_result} "
              f"{'violates' if is_failed else 'comply with'} rule {th['comparison']} {th['value']} [{status}]")

        if is_failed:
            threshold = dict(actual_value=step_result, **th)
            if step_name:
                threshold['page'] = step_name
            return threshold
        return None

    def process_thresholds_by_scope(self, test_name, environment, results_data):
        """Process and evaluate thresholds against results data."""
        all_thresholds_list = self.parse_thresholds_by_test_and_env(test_name, environment)

        print("*********************** Thresholds")
        for each in all_thresholds_list:
            print(each)
        print("***********************")

        categorized = {
            'all': [th for th in all_thresholds_list if th['scope'] == 'all'],
            'every': [th for th in all_thresholds_list if th['scope'] == 'every'],
            'page': [th for th in all_thresholds_list if th['scope'] not in ['every', 'all']]
        }

        failed_thresholds = []
        total = failed = 0

        for th in categorized['every']:
            for step in results_data.keys():
                total += 1
                step_result = self.get_aggregated_value(
                    th["aggregation"],
                    results_data[step].get(th["target"], [])
                )
                failure = self._evaluate_threshold(th, step_result, step)
                if failure:
                    failed += 1
                    failed_thresholds.append(failure)

        for th in categorized['page']:
            for step in results_data.keys():
                if th["scope"] == step:
                    total += 1
                    step_result = self.get_aggregated_value(
                        th["aggregation"],
                        results_data[step].get(th["target"], [])
                    )
                    failure = self._evaluate_threshold(th, step_result)
                    if failure:
                        failed += 1
                        failed_thresholds.append(failure)

        return {
            'failed_thresholds': failed_thresholds,
            'test_thresholds_total': total,
            'test_thresholds_failed': failed,
            'all_thresholds': categorized['all'],
            'every_thresholds': categorized['every'],
            'page_thresholds': categorized['page']
        }

    def process_all_scope_thresholds(self, test_name, environment, all_results_data):
        """Process thresholds with scope='all' against aggregated results."""
        all_thresholds_list = self.parse_thresholds_by_test_and_env(test_name, environment)
        all_thresholds = [th for th in all_thresholds_list if th['scope'] == 'all']

        failed_thresholds = []
        total = failed = 0

        for th in all_thresholds:
            total += 1
            result = all_results_data.get(th["target"], 0)
            failure = self._evaluate_threshold(th, result)
            if failure:
                failed += 1
                failed_thresholds.append(failure)

        return {
            'failed_thresholds': failed_thresholds,
            'test_thresholds_total': total,
            'test_thresholds_failed': failed
        }

