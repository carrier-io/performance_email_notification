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
        
        # API returns {'total': N, 'rows': [...]} structure
        if isinstance(response_data, dict) and 'rows' in response_data:
            return response_data['rows']
        elif isinstance(response_data, list):
            return response_data
        else:
            print(f"[WARNING] Unexpected response format: {type(response_data)}")
            return []
    
    def parse_thresholds_by_test_and_env(self, test_name, environment):
       
        all_thresholds = self.get_thresholds_info()
        
        filtered_thresholds = [
            threshold for threshold in all_thresholds
            if threshold.get('test') == test_name and threshold.get('environment') == environment
        ]
        
        print(f"[THRESHOLDS] Found {len(filtered_thresholds)} thresholds for test '{test_name}' in environment '{environment}'")
        
        return filtered_thresholds
    
    def get_thresholds_by_scope(self, test_name, environment, scope):
        filtered_thresholds = self.parse_thresholds_by_test_and_env(test_name, environment)
        
        scope_thresholds = [
            threshold for threshold in filtered_thresholds
            if threshold.get('scope') == scope
        ]
        
        return scope_thresholds
    
    def get_thresholds_grouped_by_scope(self, test_name, environment):
        
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
        """
        Check if a threshold is failed based on comparison operator.
        
        Args:
            actual_value: The actual measured value
            comparison: Comparison operator ('gte', 'lte', 'gt', 'lt', 'eq')
            threshold_value: The threshold value to compare against
        
        Returns:
            True if threshold is violated/failed, False if it passes
            
        Logic (threshold value represents the boundary for failure):
            - 'gte N': FAIL if actual >= N (N is maximum allowed, fail if too high)
            - 'lte N': FAIL if actual <= N (N is minimum required, fail if too low)
            - 'gt N': FAIL if actual > N (N is maximum allowed, fail if strictly higher)
            - 'lt N': FAIL if actual < N (N is minimum required, fail if strictly lower)
            - 'eq N': FAIL if actual == N (fail if equals the boundary)
        """
        if comparison == 'gte':
            return actual_value >= threshold_value  # Fails if at or above maximum
        elif comparison == 'lte':
            return actual_value <= threshold_value  # Fails if at or below minimum
        elif comparison == 'gt':
            return actual_value > threshold_value  # Fails if strictly above maximum
        elif comparison == 'lt':
            return actual_value < threshold_value  # Fails if strictly below minimum
        elif comparison == 'eq':
            return actual_value == threshold_value  # Fails if equals boundary
        return False
    
    @staticmethod
    def get_aggregated_value(aggregation, values):
        """
        Aggregate a list of values based on aggregation type.
        
        Args:
            aggregation: Type of aggregation ('max', 'min', 'avg', 'median', 'pct95', 'pct99')
            values: List of numeric values
        
        Returns:
            Aggregated value
        """
        if not values:
            return 0
        
        if aggregation == 'max':
            return max(values)
        elif aggregation == 'min':
            return min(values)
        elif aggregation == 'avg':
            return sum(values) / len(values)
        elif aggregation == 'median':
            sorted_values = sorted(values)
            n = len(sorted_values)
            if n % 2 == 0:
                return (sorted_values[n//2 - 1] + sorted_values[n//2]) / 2
            else:
                return sorted_values[n//2]
        elif aggregation == 'pct95':
            sorted_values = sorted(values)
            index = int(len(sorted_values) * 0.95)
            return sorted_values[index] if index < len(sorted_values) else sorted_values[-1]
        elif aggregation == 'pct99':
            sorted_values = sorted(values)
            index = int(len(sorted_values) * 0.99)
            return sorted_values[index] if index < len(sorted_values) else sorted_values[-1]
        return 0
    
    def process_thresholds_by_scope(self, test_name, environment, results_data):
        """
        Process thresholds and evaluate them against results data.
        Similar to post_processing.py logic (lines 51-142).
        
        Args:
            test_name: Name of the test
            environment: Environment name
            results_data: Dictionary with structure:
                {
                    "identifier": {
                        "load_time": [value1, value2, ...],
                        "first_contentful_paint": [value1, value2, ...],
                        ...
                    }
                }
        
        Returns:
            Dictionary containing:
                - failed_thresholds: List of failed threshold details
                - test_thresholds_total: Total number of thresholds evaluated
                - test_thresholds_failed: Number of failed thresholds
                - all_thresholds: List of thresholds with scope='all'
                - every_thresholds: List of thresholds with scope='every'
                - page_thresholds: List of page-specific thresholds
        """
        # Get all thresholds
        all_thresholds_list = self.parse_thresholds_by_test_and_env(test_name, environment)
        
        print("*********************** Thresholds")
        for each in all_thresholds_list:
            print(each)
        print("***********************")
        
        # Categorize thresholds by scope
        all_thresholds = list(filter(lambda _th: _th['scope'] == 'all', all_thresholds_list))
        every_thresholds = list(filter(lambda _th: _th['scope'] == 'every', all_thresholds_list))
        page_thresholds = list(filter(lambda _th: _th['scope'] != 'every' and _th['scope'] != 'all', all_thresholds_list))
        
        failed_thresholds = []
        test_thresholds_total = 0
        test_thresholds_failed = 0
        
        # Process thresholds with scope = every
        for th in every_thresholds:
            for step in results_data.keys():
                test_thresholds_total += 1
                step_result = self.get_aggregated_value(th["aggregation"], results_data[step].get(th["target"], []))
                if not self.is_threshold_failed(step_result, th["comparison"], th["value"]):
                    print(f"Threshold: {th['scope']} {th['target']} {th['aggregation']} value {step_result}"
                          f" comply with rule {th['comparison']} {th['value']} [PASSED]")
                else:
                    test_thresholds_failed += 1
                    threshold = dict(actual_value=step_result, page=step, **th)
                    failed_thresholds.append(threshold)
                    print(f"Threshold: {th['scope']} {th['target']} {th['aggregation']} value {step_result}"
                          f" violates rule {th['comparison']} {th['value']} [FAILED]")
        
        # Process thresholds for specific pages
        for th in page_thresholds:
            for step in results_data.keys():
                if th["scope"] == step:
                    test_thresholds_total += 1
                    step_result = self.get_aggregated_value(th["aggregation"], results_data[step].get(th["target"], []))
                    if not self.is_threshold_failed(step_result, th["comparison"], th["value"]):
                        print(f"Threshold: {th['scope']} {th['target']} {th['aggregation']} value {step_result}"
                              f" comply with rule {th['comparison']} {th['value']} [PASSED]")
                    else:
                        test_thresholds_failed += 1
                        threshold = dict(actual_value=step_result, **th)
                        failed_thresholds.append(threshold)
                        print(f"Threshold: {th['scope']} {th['target']} {th['aggregation']} value {step_result}"
                              f" violates rule {th['comparison']} {th['value']} [FAILED]")
        
        return {
            'failed_thresholds': failed_thresholds,
            'test_thresholds_total': test_thresholds_total,
            'test_thresholds_failed': test_thresholds_failed,
            'all_thresholds': all_thresholds,
            'every_thresholds': every_thresholds,
            'page_thresholds': page_thresholds
        }
    
    def process_all_scope_thresholds(self, test_name, environment, all_results_data):
        """
        Process thresholds with scope='all' against aggregated results.
        
        Args:
            test_name: Name of the test
            environment: Environment name
            all_results_data: Dictionary with aggregated results across all pages:
                {
                    "load_time": value,
                    "first_contentful_paint": value,
                    ...
                }
        
        Returns:
            Dictionary containing:
                - failed_thresholds: List of failed threshold details
                - test_thresholds_total: Total number of thresholds evaluated
                - test_thresholds_failed: Number of failed thresholds
        """
        all_thresholds_list = self.parse_thresholds_by_test_and_env(test_name, environment)
        all_thresholds = list(filter(lambda _th: _th['scope'] == 'all', all_thresholds_list))
        
        failed_thresholds = []
        test_thresholds_total = 0
        test_thresholds_failed = 0
        
        # Process thresholds with scope = all
        for th in all_thresholds:
            test_thresholds_total += 1
            result = all_results_data.get(th["target"], 0)
            if not self.is_threshold_failed(result, th["comparison"], th["value"]):
                print(f"Threshold: {th['scope']} {th['target']} {th['aggregation']} value {result}"
                      f" comply with rule {th['comparison']} {th['value']} [PASSED]")
            else:
                test_thresholds_failed += 1
                threshold = dict(actual_value=result, **th)
                failed_thresholds.append(threshold)
                print(f"Threshold: {th['scope']} {th['target']} {th['aggregation']} value {result}"
                      f" violates rule {th['comparison']} {th['value']} [FAILED]")
        
        return {
            'failed_thresholds': failed_thresholds,
            'test_thresholds_total': test_thresholds_total,
            'test_thresholds_failed': test_thresholds_failed
        }
