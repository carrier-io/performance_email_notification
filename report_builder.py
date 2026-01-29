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

"""
SLA Threshold & Baseline Matching Logic for API Performance Reports.

For complete documentation of threshold matching rules, metric selection,
baseline comparison logic, and configuration scenarios, see:
    THRESHOLD_MATCHING_LOGIC.md

Quick Summary:
- General metrics: Uses ONLY lowercase 'all' threshold (strict match)
- Request metrics (All row): Uses ONLY lowercase 'all' threshold
- Request metrics (Individual): Per request results check → fallback chain
- Baseline: Controlled by Summary/Per request results settings
- Metric selection: User → Single SLA → Highest SLA → Default pct95
"""

import time
import calendar
import datetime
import pytz
import requests
from chart_generator import alerts_linechart, barchart, ui_comparison_linechart
from email.mime.image import MIMEImage
import statistics
from jinja2 import Environment, FileSystemLoader


def convert_utc_to_cet(utc_datetime_str, output_format='%Y-%m-%d %H:%M:%S'):
    """
    Convert UTC datetime string to CET/CEST timezone.
    
    Args:
        utc_datetime_str: UTC datetime string in format 'YYYY-MM-DD HH:MM:SS'
        output_format: Output format for datetime string
    
    Returns:
        Datetime string in CET/CEST timezone
    """
    utc_tz = pytz.UTC
    cet_tz = pytz.timezone('Europe/Paris')  # CET/CEST timezone
    
    # Parse UTC datetime string
    utc_dt = datetime.datetime.strptime(utc_datetime_str, '%Y-%m-%d %H:%M:%S')
    utc_dt = utc_tz.localize(utc_dt)
    
    # Convert to CET
    cet_dt = utc_dt.astimezone(cet_tz)
    
    return cet_dt.strftime(output_format)


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

    @staticmethod
    def fetch_api_reports(galloper_url, galloper_project_id, name, limit, token):
        """
        Get API reports from Galloper.
        Return total, rows, start_time, end_time from reports.
        """
        url = f"{galloper_url}/api/v1/backend_performance/reports/{galloper_project_id}?name={name}&limit={limit}"
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        total = data.get("total", 0)
        rows = data.get("rows", [])
        start_time = None
        end_time = None
        if rows and isinstance(rows, list):
            first_row = rows[0]
            start_time = first_row.get("start_time")
            end_time = first_row.get("end_time")
        return total, rows, start_time, end_time
    
    @staticmethod
    def _get_baseline_api_report_id(args, baseline_build_id):
        """
        Get report_id for baseline API test by its build_id.
        Returns report_id (int) or None if not found.
        """
        try:
            test_name = args.get('test') or args.get('simulation')
            galloper_url = args.get('galloper_url')
            project_id = args.get('project_id')
            token = args.get('token')
            
            if not all([galloper_url, project_id, token, test_name]):
                return None
            
            # Fetch all reports to find the one with matching build_id
            url = f"{galloper_url}/api/v1/backend_performance/reports/{project_id}?name={test_name}&limit=100"
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            rows = data.get("rows", [])
            
            # Find report with matching build_id
            for row in rows:
                if row.get('build_id') == baseline_build_id:
                    return row.get('id')
            
            return None
        except Exception as e:
            print(f"Warning: Could not fetch baseline report_id: {e}")
            return None
    
    def fetch_api_reports_for_comparison(self, args, build_ids=None):
        """
        Fetch API reports to get start_time for historical tests.
        end_time is only included for the latest (first) report.
        
        Args:
            args: Arguments dict with galloper_url, project_id, token, test name
            build_ids: Optional list of specific build_ids we need data for.
                      If provided, will fetch enough records to find all of them.
        
        Returns a dict mapping build_id to report data.
        """
        try:
            test_name = args.get('test') or args.get('simulation')
            galloper_url = args.get('galloper_url')
            project_id = args.get('project_id')
            token = args.get('token')
            
            # If build_ids provided, use 3x buffer to ensure we get all of them
            # (need larger buffer because there may be many tests between current and old ones)
            # Otherwise use test_limit with default of 5
            if build_ids:
                limit = len(build_ids) * 3
            else:
                limit = args.get('test_limit', 5)
            
            if not all([galloper_url, project_id, token, test_name]):
                return {}
            
            total, rows, _, _ = self.fetch_api_reports(galloper_url, project_id, test_name, limit, token)
            
            # Create a mapping of build_id to report data
            reports_map = {}
            
            for idx, row in enumerate(rows):
                build_id = row.get('build_id')
                if build_id:
                    report_data = {
                        'start_time': row.get('start_time'),
                        'duration': row.get('duration'),
                        'report_id': row.get('id')
                    }
                    # Only include end_time for the first (latest) report
                    if idx == 0:
                        report_data['end_time'] = row.get('end_time')
                    reports_map[build_id] = report_data
            
            return reports_map
        except Exception as e:
            print(f"Warning: Could not fetch API reports for comparison: {e}")
            return {}

    def create_api_email_body(self, args, tests_data, last_test_data, baseline, comparison_metric,
                              violation, thresholds=None, report_data=None):
        # Smart metric selection: if comparison_metric is default (pct95) and Per request results is not enabled,
        # but SLA is configured with different metrics, auto-select the metric from SLA
        per_request_results_config = args.get("quality_gate_config", {}).get("settings", {}).get("per_request_results", {})
        per_request_rt_check = per_request_results_config.get('check_response_time', False)
        per_request_er_check = per_request_results_config.get('check_error_rate', False)
        per_request_tp_check = per_request_results_config.get('check_throughput', False)
        per_request_enabled = per_request_rt_check or per_request_er_check or per_request_tp_check
        
        sla_enabled = args.get("quality_gate_config", {}).get("SLA", {}).get("checked")
        baseline_enabled = args.get("quality_gate_config", {}).get("baseline", {}).get("checked")
        
        if not per_request_rt_check and sla_enabled and thresholds:
            # Extract all unique pct metrics from SLA thresholds (only from response_time if it exists)
            sla_metrics = set()
            for th in thresholds:
                if th.get('target') == 'response_time':
                    sla_metrics.add(th.get('aggregation', 'pct95'))
            
            # If multiple metrics exist, store for warning
            if len(sla_metrics) > 1:
                args['comparison_metric_sla_options'] = list(sla_metrics)
                # If comparison_metric is default pct95 and pct95 not in SLA, auto-select highest
                if comparison_metric == 'pct95' and 'pct95' not in sla_metrics:
                    pct_priority = {'pct99': 4, 'pct95': 3, 'pct90': 2, 'pct50': 1, 'mean': 0}
                    sorted_metrics = sorted(sla_metrics, key=lambda x: pct_priority.get(x, 0), reverse=True)
                    comparison_metric = sorted_metrics[0]
                    args['comparison_metric_auto_selected'] = True
            # If only one metric exists and it's not pct95 (default), switch to it
            elif len(sla_metrics) == 1 and comparison_metric == 'pct95':
                single_metric = list(sla_metrics)[0]
                if single_metric != 'pct95':
                    comparison_metric = single_metric
        
        # Create baseline_and_thresholds first to check for metric mismatch
        baseline_and_thresholds_temp = self.get_baseline_and_thresholds(args, last_test_data, baseline, comparison_metric, thresholds)
        
        test_description = self.create_test_description(args, last_test_data, baseline, comparison_metric, violation, report_data)
        
        # Override users count with vusers from report_data if available
        if report_data and 'vusers' in report_data:
            test_description["users"] = report_data["vusers"]
        
        # Check Quality Gate settings once
        # Summary results is enabled if ANY of the three checks is enabled
        summary_results_config = args.get("quality_gate_config", {}).get("settings", {}).get("summary_results", {})
        summary_rt_check = summary_results_config.get('check_response_time', False)
        summary_er_check = summary_results_config.get('check_error_rate', False)
        summary_tp_check = summary_results_config.get('check_throughput', False)
        summary_enabled = summary_rt_check or summary_er_check or summary_tp_check
        
        # Store metric visibility flags in test_description for use in template
        test_description['summary_rt_check'] = summary_rt_check
        test_description['summary_er_check'] = summary_er_check
        test_description['summary_tp_check'] = summary_tp_check
        test_description['sla_enabled'] = sla_enabled
        test_description['baseline_enabled'] = baseline_enabled
        
        # Initialize warning fields in test_description
        if 'sla_metric_warning' not in test_description:
            test_description['sla_metric_warning'] = None
        if 'baseline_metric_warning' not in test_description:
            test_description['baseline_metric_warning'] = None
        if 'sla_deviation_warning' not in test_description:
            test_description['sla_deviation_warning'] = None
        if 'baseline_deviation_warning' not in test_description:
            test_description['baseline_deviation_warning'] = None
        if 'sla_disabled_metrics_info' not in test_description:
            test_description['sla_disabled_metrics_info'] = None
        if 'baseline_disabled_metrics_info' not in test_description:
            test_description['baseline_disabled_metrics_info'] = None
        
        # SLA warnings (priority order - only one SLA warning shown)
        # Check if SLA thresholds exist in system (any of three metrics configured)
        sla_exists_in_system = not (args.get('sla_no_response_time') and args.get('sla_no_error_rate') and args.get('sla_no_throughput'))
        
        if not sla_enabled and sla_exists_in_system:
            # Priority 0: SLA is disabled but thresholds exist in system
            test_description['sla_metric_warning'] = "SLA comparison is disabled in Quality Gate configuration. Enable SLA to see comparison with configured thresholds."
        
        elif sla_enabled and not per_request_enabled and not summary_enabled and sla_exists_in_system:
            # Priority 1: SLA enabled but both Summary and Per request results are disabled (and thresholds exist)
            test_description['sla_metric_warning'] = "SLA is enabled, but both \"Summary results\" and \"Per request results\" options are disabled in Quality Gate configuration. Enable at least one option to see SLA data."
        
        elif sla_enabled and args.get('sla_no_response_time') and args.get('sla_no_error_rate') and args.get('sla_no_throughput'):
            # Priority 2: SLA enabled but NO thresholds configured at all
            test_description['sla_metric_warning'] = "SLA is enabled but no thresholds are configured. Please configure SLA for at least one metric (response time, error rate, or throughput)."
        
        elif sla_enabled and summary_enabled and not per_request_enabled:
            # Priority 3j (NEW): SLA enabled, Summary ON but Per request OFF (all metrics enabled in Summary) - Per request won't show SLA
            test_description['sla_metric_warning'] = "Per request SLA is disabled. Enable \"Per request results\" in Quality Gate configuration to see SLA for individual requests."
        
        elif sla_enabled and per_request_enabled and not summary_enabled:
            # Priority 3: SLA enabled, Per request ON but Summary OFF - General metrics won't show SLA (all metrics enabled)
            test_description['sla_metric_warning'] = "General metrics SLA is disabled. Enable \"Summary results\" in Quality Gate configuration to see SLA for general metrics."
        
        # DEBUG: Store debug info for threshold analysis if debug mode is enabled
        # Control via args['debug_mode'] or environment variable DEBUG_MODE=true
        import os
        # debug_mode_enabled = args.get('debug_mode', False) or os.getenv('DEBUG_MODE', '').lower() == 'true'
        debug_mode_enabled = False
        
        if debug_mode_enabled:
            # DEBUG: Extract complete quality_gate_config structure
            quality_gate_config = args.get('quality_gate_config', {})
            
            # FULL RAW DUMP of quality_gate_config
            import json
            try:
                debug_qg_raw = json.dumps(quality_gate_config, indent=2, default=str)
            except:
                debug_qg_raw = str(quality_gate_config)
            
            debug_qg = {
                'raw_quality_gate_config': debug_qg_raw,  # Full structure as JSON string
                'SLA_checked': quality_gate_config.get('SLA', {}).get('checked', None),
                'baseline_checked': quality_gate_config.get('baseline', {}).get('checked', None),
                'per_request_results': {
                    'check_response_time': per_request_results_config.get('check_response_time', None),
                    'check_error_rate': per_request_results_config.get('check_error_rate', None),
                    'check_throughput': per_request_results_config.get('check_throughput', None),
                    'response_time_deviation': per_request_results_config.get('response_time_deviation', None),
                    'error_rate_deviation': per_request_results_config.get('error_rate_deviation', None),
                    'throughput_deviation': per_request_results_config.get('throughput_deviation', None),
                },
                'summary_results': {
                    'check_response_time': summary_results_config.get('check_response_time', None),
                    'check_error_rate': summary_results_config.get('check_error_rate', None),
                    'check_throughput': summary_results_config.get('check_throughput', None),
                    'response_time_deviation': summary_results_config.get('response_time_deviation', None),
                    'error_rate_deviation': summary_results_config.get('error_rate_deviation', None),
                    'throughput_deviation': summary_results_config.get('throughput_deviation', None),
                },
                'calculated_flags': {
                    'per_request_enabled': per_request_enabled,
                    'per_request_rt_check': per_request_rt_check,
                    'per_request_er_check': per_request_er_check,
                    'per_request_tp_check': per_request_tp_check,
                    'summary_enabled': summary_enabled,
                    'summary_rt_check': summary_rt_check,
                    'summary_er_check': summary_er_check,
                    'summary_tp_check': summary_tp_check,
                    'sla_enabled': sla_enabled,
                    'baseline_enabled': baseline_enabled,
                }
            }
            
            test_description['debug_quality_gate_config'] = debug_qg
        
        # DEBUG: Add baseline calculation debug info
        if debug_mode_enabled and args.get('baseline_debug'):
            test_description['debug_baseline_calculation'] = args['baseline_debug']
        
        if sla_enabled and debug_mode_enabled:
            debug_all = baseline_and_thresholds_temp.get('debug_all_thresholds', [])
            debug_rt_only = baseline_and_thresholds_temp.get('debug_thresholds_info', [])
            debug_input = baseline_and_thresholds_temp.get('debug_input_thresholds', [])
            debug_api = baseline_and_thresholds_temp.get('debug_api_thresholds', [])
            
            # DEBUG: Collect threshold lookup info from requests
            threshold_lookup_samples = []
            if baseline_and_thresholds_temp.get('requests'):
                for req in baseline_and_thresholds_temp['requests'][:3]:  # First 3 requests
                    if req.get('threshold_lookup_debug'):
                        threshold_lookup_samples.append(req['threshold_lookup_debug'])
            
            test_description['debug_info'] = {
                'sla_has_every': baseline_and_thresholds_temp.get('sla_has_every', False),
                'comparison_metric': comparison_metric,
                'all_thresholds': debug_all,
                'rt_thresholds': debug_rt_only,
                'threshold_lookups': threshold_lookup_samples,
                'input_thresholds': debug_input,
                'api_thresholds': debug_api
            }
        
        if sla_enabled and baseline_and_thresholds_temp.get('sla_metric_mismatch') and baseline_and_thresholds_temp.get('sla_configured_metric'):
            # Priority 4: SLA metric mismatch detected (no "all" SLA for comparison_metric)
            # This handles Case 4a only (SLA exists for comparison_metric but no "all" scope)
            # Case 4b (wrong metric) is handled by Informational Warning below
            sla_metric = baseline_and_thresholds_temp['sla_configured_metric']
            # Check if this is RT mismatch caused by disabled Summary RT checkbox
            is_rt_disabled_mismatch = (sla_metric == comparison_metric and 
                                      sla_metric in ['pct95', 'pct99', 'pct90', 'pct50', 'mean'] and 
                                      not summary_rt_check)
            
            if not is_rt_disabled_mismatch and sla_metric == comparison_metric:
                # Case 4a: SLA for comparison_metric exists but no "all"
                # Only show if it's NOT caused by disabled RT checkbox AND metric matches
                has_every = baseline_and_thresholds_temp.get('sla_has_every', False)
                has_missing = baseline_and_thresholds_temp.get('has_missing_sla', False)
                
                if has_every and not has_missing:
                    # Case 4a1b: Has "every", no "all", some requests covered by specific SLA
                    test_description['sla_metric_warning'] = f"SLA for {comparison_metric.upper()} uses 'Every' scope and some are configured for individual requests. No general 'All' SLA is configured. Configure 'All' SLA to see aggregated metrics in General metrics table."
                elif has_every:
                    # Case 4a1a: Has "every", no "all"
                    test_description['sla_metric_warning'] = f"SLA for {comparison_metric.upper()} uses 'Every' scope (applies to all requests by default). No general 'All' SLA is configured. Configure 'All' SLA to see aggregated metrics in General metrics table."
                elif has_missing:
                    # Case 4a2b: No "every", no "all", and some requests are missing SLA
                    test_description['sla_metric_warning'] = f"SLA for {comparison_metric.upper()} is configured only for specific requests. Some requests show 'Set SLA'. Configure 'Every' SLA to cover all requests and/or 'All' SLA to see aggregated metrics."
                else:
                    # Case 4a2a: No "every", no "all", but all requests have specific SLA
                    test_description['sla_metric_warning'] = f"SLA for {comparison_metric.upper()} is configured for individual requests. No general 'All' SLA is configured. Configure 'All' SLA to see aggregated metrics in General metrics table."
        
        # Priority 4a3: Has "all" but some requests show "Set SLA" (missing specific SLA)
        if sla_enabled and not test_description.get('sla_metric_warning') and baseline_and_thresholds_temp.get('has_missing_sla'):
            # Check if we have "all" and no "every" for comparison_metric
            # IMPORTANT: Use debug_api_thresholds (raw API data with scope field) to check for "every" and "all"
            has_all = False
            has_every = False
            api_thresholds_raw = baseline_and_thresholds_temp.get('debug_api_thresholds', [])
            # Parse the debug strings: "req='', scope='all', target=response_time, agg=pct95"
            for th_str in api_thresholds_raw:
                if 'target=response_time' in th_str and f'agg={comparison_metric}' in th_str:
                    # Extract scope value from string like "scope='all'"
                    if "scope='all'" in th_str or 'scope="all"' in th_str:
                        has_all = True
                    elif "scope='every'" in th_str or 'scope="every"' in th_str:
                        has_every = True
            
            if has_all and not has_every:
                # Case 4a3: Has "all", no "every", but some requests missing specific SLA
                test_description['sla_metric_warning'] = f"Some requests show 'Set SLA' for {comparison_metric.upper()} metric. Configure SLA thresholds for individual requests in Thresholds section or use 'Every' scope to apply SLA to all requests automatically."
        
        # Priority 5: SLA metric selection info (when Per request is completely disabled)
        # This is INFORMATIONAL (blue block), not a Priority warning (yellow block)
        # Store in separate field to avoid overwriting other sla_info_warning
        # Use all_sla_rt_metrics from API (not filtered thresholds) to detect ALL configured metrics
        # Handles both single metric (1) and multiple metrics (>1) cases
        all_sla_rt_metrics = baseline_and_thresholds_temp.get('all_sla_rt_metrics', [])
        if sla_enabled and not per_request_enabled and len(all_sla_rt_metrics) >= 1:
            if len(all_sla_rt_metrics) > 1:
                all_metrics = ', '.join(sorted([m.upper() for m in all_sla_rt_metrics], reverse=True))
                test_description['sla_multiple_metrics_info'] = f"Multiple SLA metrics configured ({all_metrics}). Report uses {comparison_metric.upper()} (default). To select a different metric, enable \"Per request results\" in Quality Gate configuration."
            else:
                # Single metric - show simplified message
                test_description['sla_multiple_metrics_info'] = f"SLA comparison uses default metric ({comparison_metric.upper()}). To select a different comparison metric, enable \"Per request results\" in Quality Gate configuration."
        
        # Independent informational warnings for SLA disabled metrics (shown in addition to Priority warnings)
        if sla_enabled and (summary_enabled or per_request_enabled):
            disabled_info_parts = []
            
            # Check Response Time
            if not summary_rt_check and not per_request_rt_check:
                disabled_info_parts.append("Response Time SLA is disabled for both general metrics and individual requests. Enable 'Response time' in Quality Gate configuration to see SLA for response time metrics")
            elif not summary_rt_check and summary_enabled:
                disabled_info_parts.append("Response Time SLA is disabled for general metrics. Enable 'Response time' in Quality Gate configuration to see SLA for response time metrics")
            elif not per_request_rt_check and per_request_enabled:
                disabled_info_parts.append("Response Time SLA is disabled for individual requests. Enable 'Response time' in Quality Gate configuration to see SLA for individual request metrics")
            
            # Check Error Rate
            if not summary_er_check and not per_request_er_check:
                disabled_info_parts.append("Error Rate SLA is disabled for both general metrics and individual requests. Enable 'Error rate' in Quality Gate configuration to see SLA for error rate metrics")
            elif not summary_er_check and summary_enabled:
                disabled_info_parts.append("Error Rate SLA is disabled for general metrics. Enable 'Error rate' in Quality Gate configuration to see SLA for error rate metrics")
            elif not per_request_er_check and per_request_enabled:
                disabled_info_parts.append("Error Rate SLA is disabled for individual requests. Enable 'Error rate' in Quality Gate configuration to see SLA for individual request metrics")
            
            # Check Throughput
            if not summary_tp_check and not per_request_tp_check:
                disabled_info_parts.append("Throughput SLA is disabled for both general metrics and individual requests. Enable 'Throughput' in Quality Gate configuration to see SLA for throughput metrics")
            elif not summary_tp_check and summary_enabled:
                disabled_info_parts.append("Throughput SLA is disabled for general metrics. Enable 'Throughput' in Quality Gate configuration to see SLA for throughput metrics")
            elif not per_request_tp_check and per_request_enabled:
                disabled_info_parts.append("Throughput SLA is disabled for individual requests. Enable 'Throughput' in Quality Gate configuration to see SLA for individual request metrics")
            
            if disabled_info_parts:
                # Join all parts with "; " separator for better readability
                test_description['sla_disabled_metrics_info'] = ". ".join(disabled_info_parts) + "."
        
        # Baseline warnings (independent from SLA, priority order - only one Baseline warning shown)
        if not baseline_enabled and baseline and len(baseline) > 0:
            # Priority 0a: Baseline is disabled but baseline data exists
            test_description['baseline_metric_warning'] = "Baseline comparison is disabled in Quality Gate configuration. Enable Baseline to see comparison with previous test results."
        
        elif baseline_enabled and not per_request_enabled and not summary_enabled and baseline and len(baseline) > 0:
            # Priority 1: Baseline enabled but both Summary and Per request results are disabled (all 6 checkboxes OFF)
            # This is a configuration issue - user enabled Baseline but disabled all sections where it would be displayed
            # Only shown when baseline data EXISTS (if no baseline test, Priority 0b takes precedence)
            test_description['baseline_metric_warning'] = "Baseline comparison is enabled, but both \"Summary results\" and \"Per request results\" options are disabled in Quality Gate configuration. Enable at least one option to see baseline data."
        
        elif baseline_enabled and summary_enabled and not per_request_enabled and not summary_rt_check and baseline and len(baseline) > 0:
            # Priority 1b: Baseline enabled, Summary ON (only ER/TP), Per request OFF
            # This shows General metrics for ER/TP but no response_time data available
            # Note: This is informational - baseline works for ER/TP, just no RT percentile selection available
            pass  # No warning needed - this is a valid configuration
        
        elif baseline_enabled and summary_enabled and not per_request_enabled and baseline and len(baseline) > 0:
            # Priority 3j: Baseline enabled, Summary ON but Per request OFF (all metrics enabled in Summary) - Per request won't show Baseline
            test_description['baseline_metric_warning'] = "Per request baseline is disabled. Enable \"Per request results\" in Quality Gate configuration to see baseline for individual requests."
        
        elif baseline_enabled and per_request_enabled and not summary_enabled and baseline and len(baseline) > 0:
            # Priority 3: Baseline enabled, Per request ON but Summary OFF - General metrics won't show Baseline
            test_description['baseline_metric_warning'] = "General metrics baseline is disabled. Enable \"Summary results\" in Quality Gate configuration to see baseline for general metrics."
        
        # Independent informational warnings for Baseline disabled metrics (shown in addition to Priority warnings)
        if baseline_enabled and (summary_enabled or per_request_enabled) and baseline and len(baseline) > 0:
            disabled_info_parts = []
            
            # Check Response Time
            if not summary_rt_check and not per_request_rt_check:
                disabled_info_parts.append("Response Time baseline is disabled for both general metrics and individual requests. Enable 'Response time' in Quality Gate configuration to see baseline for response time metrics")
            elif not summary_rt_check and summary_enabled:
                disabled_info_parts.append("Response Time baseline is disabled for general metrics. Enable 'Response time' in Quality Gate configuration to see baseline for response time metrics")
            elif not per_request_rt_check and per_request_enabled:
                disabled_info_parts.append("Response Time baseline is disabled for individual requests. Enable 'Response time' in Quality Gate configuration to see baseline for individual request metrics")
            
            # Check Error Rate
            if not summary_er_check and not per_request_er_check:
                disabled_info_parts.append("Error Rate baseline is disabled for both general metrics and individual requests. Enable 'Error rate' in Quality Gate configuration to see baseline for error rate metrics")
            elif not summary_er_check and summary_enabled:
                disabled_info_parts.append("Error Rate baseline is disabled for general metrics. Enable 'Error rate' in Quality Gate configuration to see baseline for error rate metrics")
            elif not per_request_er_check and per_request_enabled:
                disabled_info_parts.append("Error Rate baseline is disabled for individual requests. Enable 'Error rate' in Quality Gate configuration to see baseline for individual request metrics")
            
            # Check Throughput
            if not summary_tp_check and not per_request_tp_check:
                disabled_info_parts.append("Throughput baseline is disabled for both general metrics and individual requests. Enable 'Throughput' in Quality Gate configuration to see baseline for throughput metrics")
            elif not summary_tp_check and summary_enabled:
                disabled_info_parts.append("Throughput baseline is disabled for general metrics. Enable 'Throughput' in Quality Gate configuration to see baseline for throughput metrics")
            elif not per_request_tp_check and per_request_enabled:
                disabled_info_parts.append("Throughput baseline is disabled for individual requests. Enable 'Throughput' in Quality Gate configuration to see baseline for individual request metrics")
            
            if disabled_info_parts:
                # Join all parts with ". " separator for better readability
                test_description['baseline_disabled_metrics_info'] = ". ".join(disabled_info_parts) + "."
        
        # Informational warnings (shown independently, in addition to Priority warnings)
        
        # Baseline: Show "uses default PCT95" when Per request is completely OFF and Summary RT is enabled
        # Baseline: Show "uses default PCT95" when Per request is completely OFF
        if baseline_enabled and not per_request_enabled and baseline and len(baseline) > 0:
            test_description['baseline_info_warning'] = f"Baseline comparison uses default metric ({comparison_metric.upper()}). To select a different comparison metric, enable \"Per request results\" in Quality Gate configuration."
        
        # SLA: Show info about comparison metric usage and check if selected metric has SLA configured
        # Show when RT data is displayed (Summary RT OR Per Request RT enabled)
        # Comparison metric selection is controlled by per_request_enabled, but this warning validates the chosen metric
        # DEBUG: Log if this block is entered
        sla_info_block_entered = False
        if sla_enabled and (summary_rt_check or per_request_rt_check):
            sla_info_block_entered = True
            # First check if specific comparison_metric has SLA configured (more specific check)
            has_comparison_metric_sla = False
            if thresholds:
                for th in thresholds:
                    if th.get('target') == 'response_time' and th.get('aggregation', 'pct95') == comparison_metric:
                        has_comparison_metric_sla = True
                        break
            
            # Check if there's ANY response_time SLA at all
            has_any_rt_sla = not args.get('sla_no_response_time')
            
            # Only show warning if comparison_metric is NOT configured
            if not has_comparison_metric_sla:
                if has_any_rt_sla:
                    # RT SLA exists but not for comparison_metric - show missing metric warning
                    if per_request_enabled and not test_description.get('sla_metric_warning'):
                        # Use all_sla_rt_metrics from API (already collected in baseline_and_thresholds_temp)
                        # This ensures we show ALL configured RT metrics, not just those in filtered thresholds
                        all_sla_rt_metrics = baseline_and_thresholds_temp.get('all_sla_rt_metrics', [])
                        configured_rt_metrics = sorted(list(all_sla_rt_metrics), reverse=True)
                        
                        # Show detailed message with available metrics
                        if configured_rt_metrics and len(configured_rt_metrics) > 1:
                            metrics_list = ', '.join([m.upper() for m in configured_rt_metrics])
                            test_description['sla_info_warning'] = f"SLA thresholds are not configured for {comparison_metric.upper()} metric. SLA is available only for {metrics_list}. Configure SLA thresholds in Thresholds section to see threshold values and differences in Request metrics and General metrics tables or select a different metric to see data."
                        elif configured_rt_metrics:
                            test_description['sla_info_warning'] = f"SLA thresholds are not configured for {comparison_metric.upper()} metric. SLA is available only for {configured_rt_metrics[0].upper()}. Configure SLA thresholds in Thresholds section to see threshold values and differences in Request metrics and General metrics tables or select a different metric to see data."
                        else:
                            # Fallback if we can't determine configured metrics (should not happen if has_any_rt_sla is True)
                            test_description['sla_info_warning'] = f"SLA comparison uses {comparison_metric.upper()}, but {comparison_metric.upper()} is not configured in Thresholds. SLA values will be hidden. Configure {comparison_metric.upper()} SLA or select a different metric to see data."
                    else:
                        test_description['sla_info_warning'] = f"SLA uses default {comparison_metric.upper()}, but {comparison_metric.upper()} is not configured in Thresholds. SLA values will be hidden. Configure {comparison_metric.upper()} SLA or enable \"Per request results\" to select a different metric."
                else:
                    # No RT SLA at all
                    if per_request_enabled and not test_description.get('sla_metric_warning'):
                        test_description['sla_info_warning'] = f"SLA comparison uses {comparison_metric.upper()}, but Response Time is not configured in Thresholds. SLA values will be hidden. Configure Response Time SLA to see data."
                    else:
                        test_description['sla_info_warning'] = f"SLA uses default {comparison_metric.upper()}, but Response Time is not configured in Thresholds. SLA values will be hidden. Configure Response Time SLA or enable \"Per request results\" to select a different metric."
        
        # DEBUG: Store whether SLA info block was entered
        if debug_mode_enabled:
            test_description['sla_info_block_debug'] = {
                'sla_info_block_entered': sla_info_block_entered,
                'sla_enabled': sla_enabled,
                'summary_rt_check': summary_rt_check,
                'per_request_rt_check': per_request_rt_check,
                'condition_result': sla_enabled and (summary_rt_check or per_request_rt_check)
            }
        
        # Deviation warnings (informational - show when deviation is enabled AND data is visible AND thresholds exist)
        quality_gate_config = args.get('quality_gate_config', {})
        settings = quality_gate_config.get('settings', {})
        
        # Check SLA deviation (only if at least one section is enabled - data is visible - and thresholds exist)
        if sla_enabled and (summary_enabled or per_request_enabled) and sla_exists_in_system:
            summary_config = settings.get('summary_results', {})
            per_request_config = settings.get('per_request_results', {})
            
            sla_tp_dev = summary_config.get('throughput_deviation', 0) or per_request_config.get('throughput_deviation', 0)
            sla_er_dev = summary_config.get('error_rate_deviation', 0) or per_request_config.get('error_rate_deviation', 0)
            sla_rt_dev = summary_config.get('response_time_deviation', 0) or per_request_config.get('response_time_deviation', 0)
            
            if sla_tp_dev > 0 or sla_er_dev > 0 or sla_rt_dev > 0:
                test_description['sla_deviation_warning'] = True
        
        # Check Baseline deviation (only if at least one section is enabled - data is visible)
        if baseline_enabled and baseline and (summary_enabled or per_request_enabled):
            summary_config = settings.get('summary_results', {})
            per_request_config = settings.get('per_request_results', {})
            
            bl_tp_dev = summary_config.get('throughput_deviation', 0) or per_request_config.get('throughput_deviation', 0)
            bl_er_dev = summary_config.get('error_rate_deviation', 0) or per_request_config.get('error_rate_deviation', 0)
            bl_rt_dev = summary_config.get('response_time_deviation', 0) or per_request_config.get('response_time_deviation', 0)
            
            if bl_tp_dev > 0 or bl_er_dev > 0 or bl_rt_dev > 0:
                test_description['baseline_deviation_warning'] = True
        
        # Extract build_ids from tests_data to fetch specific API reports
        build_ids_to_fetch = []
        for test in tests_data:
            if test and len(test) > 0:
                build_id = test[0].get('build_id')
                if build_id:
                    build_ids_to_fetch.append(build_id)
        
        # Fetch API reports to get start_time for historical tests
        api_reports = self.fetch_api_reports_for_comparison(args, build_ids=build_ids_to_fetch)
        builds_comparison = self.create_builds_comparison(tests_data, args, api_reports, comparison_metric)
        general_metrics = self.get_general_metrics(args, builds_comparison[0], baseline, thresholds, comparison_metric)
        charts = self.create_charts(builds_comparison, last_test_data, baseline, comparison_metric)
        baseline_and_thresholds = baseline_and_thresholds_temp

        # test_description now contains all warnings generated above
        email_body = self.get_api_email_body(args, test_description, last_test_data, baseline, builds_comparison,
                                             baseline_and_thresholds, general_metrics, comparison_metric)
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

    def create_test_description(self, args, test, baseline, comparison_metric, violation, report_data=None):
        params = ['simulation', 'users', 'duration']
        test_params = {"test_type": args["test_type"], "env": args["env"],
                       "performance_degradation_rate": args["performance_degradation_rate"],
                       "missed_threshold_rate": args["missed_threshold_rate"],
                       "reasons_to_fail_report": args["reasons_to_fail_report"], "status": args["status"],
                       "color": STATUS_COLOR[args["status"].lower()]}
        # Add SLA debug info if enabled
        if args.get('sla_debug_enabled', False) and 'sla_debug_comparisons' in args:
            test_params["sla_debug_enabled"] = True
            test_params["sla_debug_comparisons"] = args["sla_debug_comparisons"]
        # Add baseline report URL if baseline exists and has build_id
        if baseline and len(baseline) > 0 and baseline[0].get("build_id"):
            baseline_build_id = baseline[0]["build_id"]
            # Get report_id for baseline from API
            baseline_report_id = self._get_baseline_api_report_id(args, baseline_build_id)
            if baseline_report_id:
                test_params["baseline_report_url"] = f"{args['galloper_url']}/-/performance/backend/results?result_id={baseline_report_id}"
        if report_data:
            report_id = report_data.get("id") or report_data.get("report_id")
            if report_id:
                test_params["current_report_url"] = f"{args['galloper_url']}/-/performance/backend/results?result_id={report_id}"
        for param in params:
            test_params[param] = test[0][param]
        
        # Use start_time and end_time from report_data if available (for API tests)
        if report_data and 'start_time' in report_data and 'end_time' in report_data:
            # Convert from UTC to CET
            utc_tz = pytz.UTC
            cet_tz = pytz.timezone('CET')
            
            # Parse start_time: "2025-12-08T10:08:17.315000Z"
            start_time_str = str(report_data['start_time']).replace("Z", "").split(".")[0]
            start_dt_utc = datetime.datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M:%S')
            start_dt_utc = utc_tz.localize(start_dt_utc)
            start_dt_cet = start_dt_utc.astimezone(cet_tz)
            test_params['start'] = start_dt_cet.strftime('%Y-%m-%d %H:%M:%S')
            
            # Parse end_time: "2025-12-08T10:10:22.219000Z"
            end_time_str = str(report_data['end_time']).replace("Z", "").split(".")[0]
            end_dt_utc = datetime.datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M:%S')
            end_dt_utc = utc_tz.localize(end_dt_utc)
            end_dt_cet = end_dt_utc.astimezone(cet_tz)
            test_params['end'] = end_dt_cet.strftime('%Y-%m-%d %H:%M:%S')
        else:
            # Fallback to old calculation method (for backward compatibility)
            test_params['end'] = str(test[0]['time']).replace("T", " ").replace("Z", "")
            timestamp = calendar.timegm(time.strptime(test_params['end'], '%Y-%m-%d %H:%M:%S'))
            test_params['start'] = datetime.datetime.utcfromtimestamp(int(timestamp) - int(float(test[0]['duration']))) \
                .strftime('%Y-%m-%d %H:%M:%S')
        
        # Override status to FINISHED if all quality gate checks are disabled
        error_rate = args.get("error_rate") if args.get("error_rate") is not None else -1
        performance_degradation_rate = args.get("performance_degradation_rate") if args.get("performance_degradation_rate") is not None else -1
        missed_thresholds = args.get("missed_thresholds") if args.get("missed_thresholds") is not None else -1
        all_checks_disabled = error_rate == -1 and performance_degradation_rate == -1 and missed_thresholds == -1
        
        if all_checks_disabled and test_params["status"].lower() == "success":
            test_params["status"] = "finished"
            test_params["color"] = STATUS_COLOR["finished"]
        
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
        status, failed_message = self.check_performance_degradation(performance_degradation_rate, test, baseline, comparison_metric, args)
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
        
        # If no quality gate checks were performed (all disabled), set status to FINISHED
        all_checks_disabled = error_rate == -1 and performance_degradation_rate == -1 and missed_thresholds == -1
        
        if all_checks_disabled:
            test_status = 'FINISHED'
            color = GRAY
        elif test_status is 'SUCCESS':
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
    def check_performance_degradation(degradation_rate, test, baseline, comparison_metric, args=None):
        if degradation_rate == -1:
            return 'SUCCESS', ''
        if baseline:
            # Get deviations from Quality Gate config (unified for baseline, ignore threshold deviation)
            # Matching data_manager.compare_with_baseline logic
            quality_gate_config = args.get('quality_gate_config', {}) if args else {}
            settings = quality_gate_config.get('settings', {})
            summary_config = settings.get('summary_results', {})
            per_request_config = settings.get('per_request_results', {})
            
            all_tp_deviation = summary_config.get('throughput_deviation', 0)
            all_er_deviation = summary_config.get('error_rate_deviation', 0)
            all_rt_deviation = summary_config.get('response_time_deviation', 0)
            every_rt_deviation = per_request_config.get('response_time_deviation', 0)
            
            # Total checks: 3 for "All" (tp, er, rt) + number of individual requests (rt only)
            total_checks = 0
            failed_checks = 0
            
            for request in test:
                for baseline_request in baseline:
                    if request['request_name'] == baseline_request['request_name']:
                        if request['request_name'].lower() == 'all':
                            # For "All": check all 3 metrics (3 separate checks like SLA)
                            # Throughput: current must be >= baseline - deviation
                            if 'throughput' in request and 'throughput' in baseline_request:
                                total_checks += 1
                                current_tp = float(request['throughput'])
                                baseline_tp = float(baseline_request['throughput'])
                                baseline_tp_with_deviation = baseline_tp - all_tp_deviation
                                if current_tp < baseline_tp_with_deviation:
                                    failed_checks += 1
                            
                            # Error rate: current must be <= baseline + deviation
                            # Calculate error_rate if not present (baseline data may only have ko/total)
                            current_er = float(request.get('error_rate', round(float(request['ko'] / request['total']) * 100, 2)))
                            baseline_er = float(baseline_request.get('error_rate', round(float(baseline_request['ko'] / baseline_request['total']) * 100, 2)))
                            total_checks += 1
                            baseline_er_with_deviation = baseline_er + all_er_deviation
                            if current_er > baseline_er_with_deviation:
                                failed_checks += 1
                            
                            # Response time: current must be <= baseline + deviation
                            total_checks += 1
                            current_rt = int(request[comparison_metric])
                            baseline_rt = int(baseline_request[comparison_metric])
                            baseline_rt_with_deviation = baseline_rt + all_rt_deviation
                            if current_rt > baseline_rt_with_deviation:
                                failed_checks += 1
                        else:
                            # For individual requests: check only response_time (1 check per request)
                            total_checks += 1
                            rt_deviation = every_rt_deviation if every_rt_deviation > 0 else all_rt_deviation
                            
                            current_value = int(request[comparison_metric])
                            baseline_value = int(baseline_request[comparison_metric])
                            baseline_with_deviation = baseline_value + rt_deviation
                            if current_value > baseline_with_deviation:
                                failed_checks += 1
                            
            performance_degradation_rate = round(failed_checks * 100 / total_checks, 2) if total_checks > 0 else 0
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

    def create_builds_comparison(self, tests, args, api_reports=None, comparison_metric='pct95'):
        builds_comparison = []
        if api_reports is None:
            api_reports = {}
            
        for test in tests:
            summary_request, test_info = {}, {}
            for req in test:
                if req["request_name"] == "All":
                    summary_request = req

            if summary_request:
                # Try to get start_time from API first
                build_id = test[0].get('build_id')
                api_data = api_reports.get(build_id, {})
                
                if api_data and api_data.get('start_time'):
                    # Use start_time from API
                    utc_date = str(api_data['start_time']).replace("T", " ").replace("Z", "").split(".")[0]
                else:
                    # Fallback: Calculate start_time from time field and duration
                    time_str = str(test[0]['time']).replace("T", " ").replace("Z", "").split(".")[0]
                    time_dt = datetime.datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                    duration_seconds = int(test[0].get('duration', 0))
                    start_dt = time_dt - datetime.timedelta(seconds=duration_seconds)
                    utc_date = start_dt.strftime('%Y-%m-%d %H:%M:%S')
                
                test_info['date'] = convert_utc_to_cet(utc_date, '%d-%b %H:%M')
                test_info['date_img'] = convert_utc_to_cet(utc_date, '%d-%b\n%H:%M')
                test_info['total'] = summary_request["total"]
                test_info['throughput'] = round(summary_request["throughput"], 2)
                test_info['response_time'] = round(summary_request[comparison_metric] / 1000, 2)
                test_info['error_rate'] = round((summary_request["ko"] / summary_request["total"]) * 100, 2)
                # Add report URL for clickable date
                if api_data and api_data.get('report_id'):
                    test_info['report_url'] = f"{args['galloper_url']}/-/performance/backend/results?result_id={api_data['report_id']}"
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
        # Preserve report_url if it exists
        if 'report_url' in build:
            build_info['report_url'] = build['report_url']
        for param in ['date', 'date_img', 'error_rate', 'response_time', 'total', 'throughput']:
            param_diff = None
            if param in ['error_rate']:
                param_diff = round(float(build[param]) - float(last_build.get(param, 0.0)), 2)
                color = RED if param_diff > 0.0 else GREEN
            if param in ['throughput', 'total']:
                param_diff = round(float(build[param]) - float(last_build.get(param, 0.0)), 2)
                color = RED if param_diff < 0.0 else GREEN
            if param in ['response_time']:
                param_diff = round(float(build[param]) - float(last_build[param]), 2)
                color = RED if param_diff > 0.0 else GREEN
            if param_diff is not None:
                param_diff = f"+{param_diff}" if param_diff > 0 else str(param_diff)
                build_info[f'{param}_diff'] = f"<p style=\"color: {color}\">{param_diff}</p>"
            build_info[param] = build[param]
        return build_info

    def create_charts(self, builds, last_test_data, baseline, comparison_metric):
        charts = []
        if len(builds) >= 1:
            charts.append(self.create_success_rate_chart(builds))
            charts.append(self.create_throughput_chart(builds))
            charts.append(self.create_response_time_chart(builds, comparison_metric))
        return charts

    @staticmethod
    def create_success_rate_chart(builds):
        labels, keys, values = [], [], []
        count = 1
        for test in builds:
            labels.append(test.get('date_img', test.get('date', '')))
            keys.append(round(100 - test['error_rate'], 2))
            values.append(count)
            count += 1
        datapoints = {
            'title': 'Successful requests, %',
            'label': 'Successful requests, %',
            'x_axis': 'Test Runs',
            'y_axis': 'Successful requests, %',
            'width': 10,
            'height': 2,
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
            labels.append(test.get('date_img', test.get('date', '')))
            keys.append(test['throughput'])
            values.append(count)
            count += 1
        datapoints = {
            'title': 'Throughput',
            'label': 'Throughput, req/s',
            'x_axis': 'Test Runs',
            'y_axis': 'Throughput, req/s',
            'width': 10,
            'height': 2,
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
    def create_response_time_chart(builds, metric_name='pct95'):
        labels, keys, values = [], [], []
        count = 1
        for test in builds:
            labels.append(test.get('date_img', test.get('date', '')))
            keys.append(test['response_time'])
            values.append(count)
            count += 1
        datapoints = {
            'title': f'Response Time ({metric_name})',
            'label': 'Response Time, sec',
            'x_axis': 'Test Runs',
            'y_axis': 'Response Time, sec',
            'width': 10,
            'height': 2,
            'path_to_save': '/tmp/response_time.png',
            'keys': keys[::-1],
            'values': values,
            'labels': labels[::-1]
        }
        alerts_linechart(datapoints)
        fp = open('/tmp/response_time.png', 'rb')
        image = MIMEImage(fp.read())
        image.add_header('Content-ID', '<response_time>')
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
    def get_general_metrics(args, build_data, baseline, thresholds=None, comparison_metric='pct95'):
        current_tp = build_data['throughput']
        current_error_rate = build_data['error_rate']
        current_rt = build_data['response_time']
        baseline_throughput = "N/A"
        baseline_error_rate = "N/A"
        baseline_rt = "N/A"
        baseline_tp_value = "N/A"
        baseline_er_value = "N/A"
        baseline_rt_value = "N/A"
        baseline_tp_original = "N/A"
        baseline_er_original = "N/A"
        baseline_rt_original = "N/A"
        thresholds_tp_rate = "N/A"
        thresholds_error_rate = "N/A"
        thresholds_rt = "N/A"
        threshold_tp_value = "N/A"
        threshold_er_value = "N/A"
        threshold_rt_value = "N/A"
        threshold_tp_original = "N/A"
        threshold_er_original = "N/A"
        threshold_rt_original = "N/A"
        thresholds_tp_color = GRAY
        thresholds_er_color = GRAY
        thresholds_rt_color = GRAY
        baseline_tp_color = GRAY
        baseline_er_color = GRAY
        baseline_rt_color = GRAY
        # Check if Summary results is enabled for General metrics baseline
        summary_results_config = args.get("quality_gate_config", {}).get("settings", {}).get("summary_results", {})
        summary_rt_check = summary_results_config.get('check_response_time', False)
        summary_er_check = summary_results_config.get('check_error_rate', False)
        summary_tp_check = summary_results_config.get('check_throughput', False)
        summary_enabled = summary_rt_check or summary_er_check or summary_tp_check
        
        if baseline and args.get("quality_gate_config", {}).get("baseline", {}).get("checked") and summary_enabled:
            # Find "All" request in baseline
            baseline_all = None
            for b in baseline:
                if b.get('request_name') == 'All':
                    baseline_all = b
                    break
            
            if baseline_all:
                
                # Store original baseline values (without deviation)
                baseline_tp_original = round(baseline_all['throughput'], 2)
                baseline_ko_count = baseline_all['ko']
                baseline_ok_count = baseline_all['ok']
                baseline_er_original = round((baseline_ko_count / (baseline_ko_count + baseline_ok_count)) * 100, 2)
                baseline_rt_original = round(baseline_all[comparison_metric] / 1000, 2)
                
                # Deviation is ALWAYS taken from Quality Gate config, not from thresholds
                # It's independent of aggregation type (pct50/pct95/pct99) and thresholds
                quality_gate_config = args.get('quality_gate_config', {})
                settings = quality_gate_config.get('settings', {})
                config_section = settings.get('summary_results', {})
                
                tp_deviation = config_section.get('throughput_deviation', 0)
                er_deviation = config_section.get('error_rate_deviation', 0)
                rt_deviation = config_section.get('response_time_deviation', 0)
                
                # Get comparison operators from thresholds (for display purposes only)
                tp_comparison = None
                er_comparison = None
                rt_comparison = None
                
                if thresholds:
                    for th in thresholds:
                        req_name = th.get('request_name', '').lower()
                        scope_name = th.get('scope', '').lower()
                        
                        if req_name == 'all' or scope_name == 'all':
                            if th['target'] == 'throughput' and tp_comparison is None:
                                tp_comparison = th.get('comparison')
                            elif th['target'] == 'error_rate' and er_comparison is None:
                                er_comparison = th.get('comparison')
                            elif th['target'] == 'response_time' and rt_comparison is None:
                                rt_comparison = th.get('comparison')
                
                # Apply deviation to baseline values
                # For baseline comparison: ALWAYS ADD deviation to create tolerance range
                # Deviation allows current values to be slightly worse than baseline without failing
                # This is different from SLA where comparison type matters
                # For throughput (higher is better): baseline - deviation = min acceptable
                # For error_rate (lower is better): baseline + deviation = max acceptable  
                # For response_time (lower is better): baseline + deviation = max acceptable
                
                # Throughput: subtract deviation (allows current to be lower than baseline)
                baseline_tp_with_dev = baseline_tp_original - tp_deviation
                
                # Error rate: add deviation (allows current to be higher than baseline)
                baseline_er_with_dev = baseline_er_original + er_deviation
                
                # Response time: add deviation (allows current to be higher than baseline)
                baseline_rt_with_dev = baseline_rt_original + (rt_deviation / 1000)
                
                # Store values with deviation for display
                baseline_tp_value = round(baseline_tp_with_dev, 2)
                baseline_er_value = round(baseline_er_with_dev, 2)
                baseline_rt_value = round(baseline_rt_with_dev, 2)
                
                # Calculate colors and diffs using values with deviation
                baseline_tp_color = RED if baseline_tp_value > current_tp else GREEN
                baseline_er_color = RED if current_error_rate > baseline_er_value else GREEN
                baseline_rt_color = RED if current_rt > baseline_rt_value else GREEN
                
                baseline_throughput = round(current_tp - baseline_tp_value, 2)
                baseline_error_rate = round(current_error_rate - baseline_er_value, 2)
                baseline_rt = round(current_rt - baseline_rt_value, 2)
        # Check if Summary results is enabled for General metrics SLA
        if thresholds and args.get("quality_gate_config", {}).get("SLA", {}).get("checked") and summary_enabled:
            # For General metrics, ONLY use thresholds with request_name = "all" (lowercase, strict match)
            # Do NOT use "every" or "All" (capital) - if no "all" threshold exists, show N/A
            for th in thresholds:
                # Case-insensitive match for 'all'
                if th.get('request_name', '').lower() == 'all':
                    if th['target'] == 'error_rate':
                        # Apply deviation for error_rate from Quality Gate
                        threshold_original = th['value']
                        threshold_er_original = round(threshold_original, 2)  # Store original without deviation
                        
                        # Get deviation from Quality Gate summary_results
                        quality_gate_config = args.get('quality_gate_config', {})
                        settings = quality_gate_config.get('settings', {})
                        config_section = settings.get('summary_results', {})
                        deviation = config_section.get('error_rate_deviation', 0)
                        
                        if th.get('comparison') in ['gt', 'gte']:
                            threshold_er_value = round(threshold_original + deviation, 2)
                        elif th.get('comparison') in ['lt', 'lte']:
                            threshold_er_value = round(threshold_original - deviation, 2)
                        else:
                            threshold_er_value = round(threshold_original, 2)
                        
                        thresholds_error_rate = round(th["metric"] - threshold_er_value, 2)
                        if th['threshold'] == "red":
                            thresholds_er_color = RED
                        else:
                            thresholds_er_color = GREEN
                    if th['target'] == 'throughput':
                        # Apply deviation for throughput
                        threshold_original = th['value']
                        threshold_tp_original = round(threshold_original, 2)  # Store original without deviation
                        
                        # Get deviation from Quality Gate summary_results
                        quality_gate_config = args.get('quality_gate_config', {})
                        settings = quality_gate_config.get('settings', {})
                        config_section = settings.get('summary_results', {})
                        deviation = config_section.get('throughput_deviation', 0)
                        
                        if th.get('comparison') in ['gt', 'gte']:
                            threshold_tp_value = round(threshold_original + deviation, 2)
                        elif th.get('comparison') in ['lt', 'lte']:
                            threshold_tp_value = round(threshold_original - deviation, 2)
                        else:
                            threshold_tp_value = round(threshold_original, 2)
                        
                        thresholds_tp_rate = round(th["metric"] - threshold_tp_value, 2)
                        if th['threshold'] == "red":
                            thresholds_tp_color = RED
                        else:
                            thresholds_tp_color = GREEN
                    if th['target'] == 'response_time':
                        # Only use threshold if aggregation matches comparison_metric
                        th_aggregation = th.get('aggregation', 'pct95')
                        if th_aggregation == comparison_metric:
                            # Calculate threshold WITH deviation for display
                            threshold_original = th['value'] / 1000
                            threshold_rt_original = round(threshold_original, 2)  # Store original without deviation
                            
                            # Get deviation from Quality Gate summary_results
                            quality_gate_config = args.get('quality_gate_config', {})
                            settings = quality_gate_config.get('settings', {})
                            config_section = settings.get('summary_results', {})
                            deviation = config_section.get('response_time_deviation', 0) / 1000
                            
                            # Apply deviation based on comparison type
                            if th.get('comparison') in ['gt', 'gte']:
                                threshold_rt_value = round(threshold_original + deviation, 2)
                            elif th.get('comparison') in ['lt', 'lte']:
                                threshold_rt_value = round(threshold_original - deviation, 2)
                            else:
                                threshold_rt_value = round(threshold_original, 2)
                            
                            # metric is already in seconds (converted in compare_request_and_threhold)
                            current_metric_value = round(th["metric"], 2)
                            thresholds_rt = round(current_metric_value - threshold_rt_value, 2)
                            thresholds_rt_color = RED if th['threshold'] == "red" else GREEN
        return {
            "current_tp": current_tp,
            "baseline_tp": baseline_throughput,
            "baseline_tp_value": baseline_tp_value,
            "baseline_tp_original": baseline_tp_original,
            "baseline_tp_color": baseline_tp_color,
            "threshold_tp": thresholds_tp_rate,
            "threshold_tp_value": threshold_tp_value,
            "threshold_tp_original": threshold_tp_original,
            "threshold_tp_color": thresholds_tp_color,
            "current_er": current_error_rate,
            "baseline_er": baseline_error_rate,
            "baseline_er_value": baseline_er_value,
            "baseline_er_original": baseline_er_original,
            "baseline_er_color": baseline_er_color,
            "threshold_er": thresholds_error_rate,
            "threshold_er_value": threshold_er_value,
            "threshold_er_original": threshold_er_original,
            "threshold_er_color": thresholds_er_color,
            "current_rt": current_rt,
            "baseline_rt": baseline_rt,
            "baseline_rt_value": baseline_rt_value,
            "baseline_rt_original": baseline_rt_original,
            "baseline_rt_color": baseline_rt_color,
            "threshold_rt": thresholds_rt,
            "threshold_rt_value": threshold_rt_value,
            "threshold_rt_original": threshold_rt_original,
            "threshold_rt_color": thresholds_rt_color,
            "show_baseline_column": baseline_throughput != "N/A" or baseline_error_rate != "N/A" or baseline_rt != "N/A",
            "show_threshold_column": thresholds_tp_rate != "N/A" or thresholds_error_rate != "N/A" or thresholds_rt != "N/A",
            "comparison_metric": comparison_metric.capitalize()
        }

    @staticmethod
    def get_baseline_and_thresholds(args, last_test_data, baseline, comparison_metric, thresholds):
        # DEBUG: Track input thresholds parameter
        debug_input_thresholds = []
        if thresholds:
            for th in thresholds:
                debug_input_thresholds.append(f"req='{th.get('request_name', '')}', scope='{th.get('scope', '')}', target={th.get('target')}, agg={th.get('aggregation', 'pct95')}")
        
        # For baseline deviation: need ALL thresholds from API (not filtered by comparison_metric)
        # because deviation is universal across all aggregations
        all_thresholds_for_baseline = []
        try:
            galloper_url = args.get('galloper_url')
            project_id = args.get('project_id')
            simulation = args.get('simulation')
            env = args.get('env')
            token = args.get('token')
            
            if galloper_url and project_id and simulation:
                import requests
                headers = {'Authorization': f'bearer {token}'} if token else {}
                thresholds_url = f"{galloper_url}/api/v1/backend_performance/thresholds/{project_id}?" \
                                f"test={simulation}&env={env}&order=asc"
                all_thresholds_for_baseline = requests.get(thresholds_url, 
                    headers={**headers, 'Content-type': 'application/json'}).json()
        except Exception as e:
            print(f"Warning: Could not fetch unfiltered thresholds for baseline: {e}")
            all_thresholds_for_baseline = []
        
        # DEBUG: Track all_thresholds_for_baseline from API
        debug_api_thresholds = []
        if all_thresholds_for_baseline:
            for th in all_thresholds_for_baseline:
                debug_api_thresholds.append(f"req='{th.get('request_name', '')}', scope='{th.get('scope', '')}', target={th.get('target')}, agg={th.get('aggregation', 'pct95')}")
        
        # Priority 5: Extract all unique pct metrics from API thresholds (for multiple metrics warning)
        # Use all_thresholds_for_baseline to get ALL metrics, not just filtered ones
        all_sla_rt_metrics = set()
        if all_thresholds_for_baseline:
            for th in all_thresholds_for_baseline:
                if th.get('target') == 'response_time':
                    all_sla_rt_metrics.add(th.get('aggregation', 'pct95'))
        
        exceeded_thresholds = []
        baseline_metrics = {}
        baseline_all_data = {}  # All baseline data regardless of settings (for "disabled" message)
        thresholds_metrics = {}
        sla_metric_mismatch = False
        sla_configured_metric = None
        sla_configured_metrics = None
        sla_has_every = False
        
        # Store all baseline data for checking if baseline exists (used for "Baseline disabled" message)
        baseline_enabled = args.get("quality_gate_config", {}).get("baseline", {}).get("checked")
        baseline_all_data = {}  # Store baseline values
        
        if baseline and baseline_enabled:
            for request in baseline:
                baseline_all_data[request['request_name']] = int(request[comparison_metric])
        
        # Only populate baseline_metrics if Per request results is enabled (used for actual display)
        if baseline and baseline_enabled and args.get("quality_gate_config", {}).get("settings", {}).get("per_request_results", {}).get('check_response_time'):
            for request in baseline:
                baseline_metrics[request['request_name']] = int(request[comparison_metric])

        # Check SLA if it's enabled and either per_request_results OR summary_results is checking response_time
        sla_checked = args.get("quality_gate_config", {}).get("SLA", {}).get("checked")
        per_request_results_config = args.get("quality_gate_config", {}).get("settings", {}).get("per_request_results", {})
        per_request_rt_check = per_request_results_config.get('check_response_time', False)
        per_request_er_check = per_request_results_config.get('check_error_rate', False)
        per_request_tp_check = per_request_results_config.get('check_throughput', False)
        per_request_enabled = per_request_rt_check or per_request_er_check or per_request_tp_check
        summary_results_config = args.get("quality_gate_config", {}).get("settings", {}).get("summary_results", {})
        summary_rt_check = summary_results_config.get('check_response_time', False)
        summary_er_check = summary_results_config.get('check_error_rate', False)
        summary_tp_check = summary_results_config.get('check_throughput', False)
        summary_enabled = summary_rt_check or summary_er_check or summary_tp_check
        
        if thresholds and sla_checked and (per_request_enabled or summary_enabled):
            matching_thresholds = []
            all_sla_metrics = set()
            has_all_for_comparison_metric = False
            has_every_for_comparison_metric = False
            response_time_thresholds_count = 0
            debug_thresholds_info = []  # DEBUG: Track threshold processing
            debug_all_thresholds = []  # DEBUG: Track ALL thresholds before filtering
            
            # IMPORTANT: Also check all_thresholds_for_baseline for "every" scope
            # because input thresholds might have filtered it out
            # "every" is identified by scope='every' OR empty scope (if no specific request_name)
            # If found, add it to thresholds_metrics for proper lookup in Request metrics table
            for th in all_thresholds_for_baseline:
                if th.get('target') == 'response_time':
                    th_aggregation = th.get('aggregation', 'pct95')
                    if th_aggregation == comparison_metric:
                        scope_name = str(th.get('scope', '')).strip().lower()
                        # "every" scope means fallback for all requests
                        if scope_name == 'every':
                            has_every_for_comparison_metric = True
                            # Add to thresholds_metrics under 'every' key for lookup
                            if 'every' not in thresholds_metrics:
                                thresholds_metrics['every'] = th
                            break
            
            for th in thresholds:
                # DEBUG: Collect info about ALL thresholds (before target filter)
                request_name_raw = th.get('request_name', '')
                debug_all_thresholds.append(f"req='{request_name_raw}', scope='{th.get('scope', '')}', target={th.get('target')}, agg={th.get('aggregation', 'pct95')}")
                
                if th['target'] == 'response_time':
                    response_time_thresholds_count += 1
                    # Track all SLA metrics
                    th_aggregation = th.get('aggregation', 'pct95')
                    all_sla_metrics.add(th_aggregation)
                    # DEBUG: Collect threshold info
                    request_name_raw = th.get('request_name', '')
                    request_name_normalized = str(request_name_raw).lower().strip()
                    is_match = (th_aggregation == comparison_metric)
                    dict_key = th['request_name'] if is_match else 'N/A'
                    debug_thresholds_info.append(f"req='{request_name_raw}'(norm='{request_name_normalized}'), agg={th_aggregation}, match={is_match}, dict_key='{dict_key}'")
                    # Only add threshold if aggregation matches comparison_metric
                    if th_aggregation == comparison_metric:
                        thresholds_metrics[th['request_name']] = th
                        matching_thresholds.append(th)
                        # Normalize request_name for comparison - handle case sensitivity and whitespace
                        # Check if there's a general "all" SLA for this metric
                        if request_name_normalized == 'all':
                            has_all_for_comparison_metric = True
                        # Check if there's "every" SLA for this metric (fallback for individual requests)
                        elif request_name_normalized == 'every':
                            has_every_for_comparison_metric = True
            
            # Determine if there's a mismatch
            # Case 1: No matching thresholds at all (SLA configured for different metric)
            if all_sla_metrics and not matching_thresholds:
                sla_metric_mismatch = True
                # Store all configured metrics for informative warning message
                sla_configured_metrics = sorted(list(all_sla_metrics), reverse=True)  # List of all metrics
                sla_configured_metric = sla_configured_metrics[0]  # Keep for backward compatibility
            # Case 2: Has matching thresholds but no "all" for comparison_metric
            elif matching_thresholds and not has_all_for_comparison_metric:
                sla_metric_mismatch = True
                sla_configured_metric = comparison_metric
                # Store has_every flag for warning message differentiation
                sla_has_every = has_every_for_comparison_metric
        else:
            debug_thresholds_info = []  # Initialize if not set
            debug_all_thresholds = []  # Initialize if not set
            
        for request in last_test_data:
            req = {}
            req['response_time'] = str(round(float(request[comparison_metric]) / 1000, 2))
            if len(str(request['request_name'])) > 80:
                req['request_name'] = str(request['request_name'])[:80] + "..."
            else:
                req['request_name'] = str(request['request_name'])
            
            # Determine request category based on method field
            method = request.get('method', '').upper()
            if request['request_name'].lower() == 'all':
                req['category'] = 'all'  # Overall metrics
            elif method == 'TRANSACTION':
                req['category'] = 'transaction'  # Transactions
            else:
                req['category'] = 'request'  # Individual requests
            # For baseline: check if appropriate setting is enabled and data exists
            # For "All" row - requires Summary results enabled
            # For individual requests - requires Per request results enabled
            show_baseline_for_request = False
            baseline_data_exists = baseline_enabled and request['request_name'] in list(baseline_all_data.keys())
            
            if baseline_data_exists:
                if request['request_name'].lower() == 'all':
                    # All row requires Summary results enabled for response_time
                    # Note: Request metrics table only shows response_time, so check RT specifically
                    show_baseline_for_request = summary_rt_check
                else:
                    # Individual requests require Per request results enabled for response_time
                    # Note: Request metrics table only shows response_time, so check RT specifically
                    show_baseline_for_request = per_request_rt_check
            
            if show_baseline_for_request:
                # Round values first, then calculate difference
                current_value = round(float(request[comparison_metric]) / 1000, 2)
                baseline_original = round(baseline_all_data[request['request_name']] / 1000, 2)
                
                # Get response_time deviation based on request type
                # Use Quality Gate config deviation (unified for baseline, ignore threshold deviation)
                quality_gate_config = args.get('quality_gate_config', {})
                settings = quality_gate_config.get('settings', {})
                
                if request['request_name'].lower() == 'all':
                    config_section = settings.get('summary_results', {})
                else:
                    config_section = settings.get('per_request_results', {})
                
                request_deviation = config_section.get('response_time_deviation', 0)
                
                # For baseline: ALWAYS ADD deviation (response_time: lower is better, so baseline + deviation = max acceptable)
                # This creates tolerance range allowing current to be slightly worse than baseline
                baseline_value = round(baseline_original + (request_deviation / 1000), 2)
                req['baseline'] = round(current_value - baseline_value, 2)
                req['baseline_value'] = baseline_value
                req['baseline_original_value'] = baseline_original
                if req['baseline'] <= 0:
                    req['baseline_color'] = GREEN
                else:
                    req['baseline_color'] = YELLOW
            else:
                req['baseline'] = "-"
                # Show different message based on whether section is completely disabled
                # For "All" row: disabled if Summary results Response Time is OFF
                # For individual requests: disabled if Per request results is OFF (all 3 checkboxes OFF)
                if baseline_data_exists:
                    if request['request_name'].lower() == 'all' and not summary_enabled:
                        req['baseline_value'] = "Baseline disabled"
                    elif request['request_name'].lower() == 'all' and not summary_rt_check:
                        req['baseline_value'] = "Enable Response Time"
                    elif request['request_name'].lower() != 'all' and not per_request_enabled:
                        req['baseline_value'] = "Baseline disabled"
                    elif request['request_name'].lower() != 'all' and per_request_enabled and not per_request_rt_check:
                        req['baseline_value'] = "Enable Response Time"
                    else:
                        req['baseline_value'] = "N/A"
                else:
                    req['baseline_value'] = "N/A"
                req['baseline_original_value'] = "N/A"  # Set original value to N/A when baseline is not shown
                req['baseline_color'] = GRAY
            # For "All" row, ONLY use threshold with request_name = "all" (lowercase, strict match)
            # Do NOT fallback to "every" - if no "all" threshold exists, show N/A
            # Also check if Summary results is enabled
            if request['request_name'].lower() == 'all':
                threshold_for_request = None
                # Only show SLA for All row if Summary results is enabled for response_time
                # Note: Request metrics table only shows response_time, so check RT specifically
                if summary_rt_check:
                    # Search for ONLY lowercase "all" in thresholds array
                    for th in thresholds:
                        if (th.get('target') == 'response_time' and 
                            th.get('aggregation', 'pct95') == comparison_metric and
                            th.get('request_name', '').lower() == 'all'):  # Case-insensitive match for 'all'
                            threshold_for_request = th
                            break
                # Do NOT fallback to "every" or "All" (capital) for the "All" row
            # For individual requests/transactions, check if Per request results is enabled
            else:
                threshold_for_request = None
                
                # If Per request results is enabled for response_time, use full fallback chain
                # Note: Request metrics table only shows response_time, so check RT specifically
                if per_request_rt_check:
                    # Try to get threshold for specific request name
                    threshold_for_request = thresholds_metrics.get(request['request_name'])
                    
                    # DEBUG: Track threshold lookup process
                    lookup_info = f"Looking for threshold: req='{request['request_name']}'"
                    if threshold_for_request:
                        lookup_info += f" -> FOUND specific"
                    
                    if not threshold_for_request:
                        # Fallback to "every" if no specific threshold found
                        # Note: "every" applies to all requests individually, while "all" is for aggregated metrics only
                        for key in thresholds_metrics.keys():
                            if key.lower() == 'every':
                                threshold_for_request = thresholds_metrics[key]
                                lookup_info += f" -> FALLBACK to 'every' (key='{key}')"
                                break
                        # Do NOT fallback to "all" - it's for aggregated metrics, not individual requests
                        if not threshold_for_request:
                            lookup_info += f" -> NOT FOUND (keys in dict: {list(thresholds_metrics.keys())})"
                    
                    # DEBUG: Store lookup info for first few requests
                    if 'threshold_lookup_debug' not in request:
                        request['threshold_lookup_debug'] = lookup_info
                
                # If Per request results is disabled but SLA is enabled
                # Don't use per-request thresholds, but threshold_for_request stays None
                # This will trigger "SLA disabled" message below
            
            # Process threshold value or show appropriate message
            if thresholds_metrics and threshold_for_request:
                # Round values first, then calculate difference
                current_value = round(float(request[comparison_metric]) / 1000, 2)
                
                # Calculate threshold WITH deviation for display
                threshold_original = float(threshold_for_request['value']) / 1000
                threshold_original_value = round(threshold_original, 2)  # Store original without deviation
                
                # Get response_time deviation from Quality Gate config (unified for SLA, ignore threshold deviation)
                quality_gate_config = args.get('quality_gate_config', {})
                settings = quality_gate_config.get('settings', {})
                
                if request['request_name'].lower() == 'all':
                    config_section = settings.get('summary_results', {})
                else:
                    config_section = settings.get('per_request_results', {})
                
                deviation = config_section.get('response_time_deviation', 0) / 1000  # Convert to seconds
                
                # Apply deviation based on comparison type
                if threshold_for_request.get('comparison') in ['gt', 'gte']:
                    threshold_value = round(threshold_original + deviation, 2)
                elif threshold_for_request.get('comparison') in ['lt', 'lte']:
                    threshold_value = round(threshold_original - deviation, 2)
                else:
                    threshold_value = round(threshold_original, 2)
                
                req['threshold'] = round(current_value - threshold_value, 2)
                req['threshold_value'] = threshold_value
                req['threshold_original_value'] = threshold_original_value
                if threshold_for_request['threshold'] == 'red':
                    req['line_color'] = RED
                    req['threshold_color'] = RED
                else:
                    req['threshold_color'] = GREEN
            else:
                req['threshold'] = "-"
                # Show different message based on whether section is completely disabled
                # For "All" row: disabled if Summary results is OFF (all 3 checkboxes OFF)
                # For individual requests: disabled if Per request results is OFF (all 3 checkboxes OFF)
                if sla_checked:
                    if request['request_name'].lower() == 'all' and not summary_enabled:
                        req['threshold_value'] = "SLA disabled"
                    elif request['request_name'].lower() != 'all' and not per_request_enabled:
                        req['threshold_value'] = "SLA disabled"
                    else:
                        req['threshold_value'] = "Set SLA"
                else:
                    req['threshold_value'] = "Set SLA"
                req['threshold_original_value'] = "Set SLA"  # Set original value when threshold is not configured
                req['threshold_color'] = GRAY
                req['line_color'] = GRAY
            if not req.get('line_color'):
                if req['threshold_color'] == GREEN and req.get('baseline_color', GREEN) == GREEN:
                    req['line_color'] = GREEN
                else:
                    req['line_color'] = YELLOW
            exceeded_thresholds.append(req)
        
        # Group by category and sort by color within each group
        # Category priority: all (0), transaction (1), request (2)
        # Color priority: RED (0), YELLOW (1), GREEN (2), GRAY (3)
        category_priority = {'all': 0, 'transaction': 1, 'request': 2}
        color_priority = {RED: 0, YELLOW: 1, GREEN: 2, GRAY: 3}
        exceeded_thresholds = sorted(
            exceeded_thresholds, 
            key=lambda k: (
                category_priority.get(k.get('category', 'request'), 3),
                color_priority.get(k.get('line_color', GRAY), 4)
            )
        )
        hundered = 0
        for _ in range(len(exceeded_thresholds)):
            if not (hundered):
                exceeded_thresholds[_]['share'] = 100
                hundered = float(exceeded_thresholds[_]['response_time'])
            else:
                exceeded_thresholds[_]['share'] = int((100 * float(exceeded_thresholds[_]['response_time'])) / hundered)
        
        # Determine column visibility for Request metrics table
        # Show baseline column only if there's at least one actual baseline value (not "N/A", not "-", not "Baseline disabled")
        show_baseline = any(req.get('baseline') not in ["N/A", "-", None, ""] and req.get('baseline_value') not in ["N/A", "Baseline disabled", None, ""] for req in exceeded_thresholds)
        show_threshold = any(req.get('threshold_value') not in ["N/A", None, "", "Set SLA", "SLA disabled"] for req in exceeded_thresholds)
        # Check if any INDIVIDUAL requests (not "All" row) show "Set SLA"
        # "All" row shows "Set SLA" when no "all" scope configured, which is expected
        has_missing_sla = any(req.get('threshold_value') == "Set SLA" and req.get('request_name', '').lower() != 'all' for req in exceeded_thresholds)
        # has_disabled_sla should only be True when INDIVIDUAL requests (not "All" row) have "SLA disabled"
        # This indicates Per request results is OFF (all 3 checkboxes OFF)
        has_disabled_sla = any(req.get('threshold_value') == "SLA disabled" and req.get('request_name', '').lower() != 'all' for req in exceeded_thresholds)
        # has_disabled_baseline should only be True when INDIVIDUAL requests (not "All" row) have "Baseline disabled"
        # This indicates Per request results is OFF (all 3 checkboxes OFF)
        has_disabled_baseline = any(req.get('baseline_value') == "Baseline disabled" and req.get('request_name', '').lower() != 'all' for req in exceeded_thresholds)
        # has_disabled_summary_sla should be True when "All" row has "SLA disabled"
        # This indicates Summary results is OFF (all 3 checkboxes OFF)
        has_disabled_summary_sla = any(req.get('threshold_value') == "SLA disabled" and req.get('request_name', '').lower() == 'all' for req in exceeded_thresholds)
        # has_disabled_summary_baseline should be True when "All" row has "Baseline disabled"
        # This indicates Summary results is OFF (all 3 checkboxes OFF)
        has_disabled_summary_baseline = any(req.get('baseline_value') == "Baseline disabled" and req.get('request_name', '').lower() == 'all' for req in exceeded_thresholds)
        # show_representation = show_baseline or show_threshold  # Original logic
        show_representation = False  # Hide Representation column but keep sorting by color
        
        # Prepare debug info
        first_threshold = thresholds[0] if thresholds and len(thresholds) > 0 else None
        first_baseline = baseline[0] if baseline and len(baseline) > 0 else None
        
        # Find deviations for each metric from thresholds
        tp_dev = 0
        er_dev = 0
        rt_dev = 0
        rt_dev_every = 0  # Separate deviation for 'every' requests
        if thresholds:
            for th in thresholds:
                if th.get('request_name', '').lower() == 'all':
                    if th['target'] == 'throughput' and tp_dev == 0:
                        tp_dev = th.get('deviation', 0)  # Take first found, ignore duplicates
                    elif th['target'] == 'error_rate' and er_dev == 0:
                        er_dev = th.get('deviation', 0)  # Take first found, ignore duplicates
                    elif th['target'] == 'response_time' and rt_dev == 0:
                        rt_dev = th.get('deviation', 0)  # Take first found, ignore duplicates
                elif th.get('request_name', '').lower() == 'every':
                    if th['target'] == 'response_time' and rt_dev_every == 0:
                        rt_dev_every = th.get('deviation', 0)  # Take first found, ignore duplicates
        
        # Control visibility of visual warnings (⚠️ and hint) in Request metrics table headers
        # When True: shows ⚠️ and "(Configure for X)" in headers when has_missing_sla is True
        # When False: hides visual warnings in headers (warnings still appear in Warning section and table cells)
        show_missing_sla_warnings = False  # Set to True to enable visual warnings in table headers
        
        return {
            "requests": exceeded_thresholds,
            "show_baseline_column": show_baseline,
            "show_threshold_column": show_threshold,
            "show_representation_column": show_representation,
            "has_missing_sla": has_missing_sla,
            "show_missing_sla_warnings": show_missing_sla_warnings,  # Feature toggle for visual warnings in headers
            "has_disabled_sla": has_disabled_sla,
            "has_disabled_baseline": has_disabled_baseline,
            "has_disabled_summary_sla": has_disabled_summary_sla,
            "has_disabled_summary_baseline": has_disabled_summary_baseline,
            "sla_metric_mismatch": sla_metric_mismatch,
            "sla_configured_metric": sla_configured_metric,
            "sla_configured_metrics": sla_configured_metrics if sla_metric_mismatch else None,
            "sla_has_every": sla_has_every,
            "all_sla_rt_metrics": list(all_sla_rt_metrics),  # All RT metrics from API for Priority 5
            "debug_thresholds_info": debug_thresholds_info,  # DEBUG: threshold processing details
            "debug_all_thresholds": debug_all_thresholds,  # DEBUG: all thresholds from main loop
            "debug_input_thresholds": debug_input_thresholds,  # DEBUG: input parameter thresholds
            "debug_api_thresholds": debug_api_thresholds  # DEBUG: thresholds from API
        }

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
                           general_metrics, comparison_metric='pct95'):
        def format_number(value):
            """Format number with thousand separators and max 2 decimal places"""
            if value in ['N/A', '', None]:
                return value
            try:
                # Convert to float
                num = float(value)
                # Format with 2 decimal places and thousand separators (comma)
                formatted = "{:,.2f}".format(num)
                # Remove trailing zeros after decimal point
                if '.' in formatted:
                    formatted = formatted.rstrip('0').rstrip('.')
                return formatted
            except (ValueError, TypeError):
                return value
        
        def format_failed_reason(reason):
            """Replace incorrect % units with proper units based on metric type and improve wording"""
            import re
            
            # First, fix the units
            # Check if it's throughput
            if 'throughput' in reason.lower():
                # Replace "- X%" or "- X %" with "- X req/sec"
                reason = re.sub(r'(\s*-\s*[\d.]+)\s*%', r'\1 req/sec', reason)
            # Check if it's response_time
            elif 'response_time' in reason.lower() or 'response time' in reason.lower():
                # Replace "- X%" or "- X %" with "- X sec"
                reason = re.sub(r'(\s*-\s*[\d.]+)\s*%', r'\1 sec', reason)
            # error_rate keeps % (don't change)
            
            # Second, fix "exceeded" wording - make it more generic
            # "exceeded SLA value" -> "violated SLA threshold"
            reason = reason.replace('exceeded SLA value', 'violated SLA threshold')
            
            return reason
        
        env = Environment(loader=FileSystemLoader('./templates/'))
        env.filters['format_number'] = format_number
        env.filters['format_failed_reason'] = format_failed_reason
        template = env.get_template("backend_email_template.html")
        last_test_data = self.reprocess_test_data(last_test_data, ['total', 'throughput'])
        
        # Check if Baseline is actually enabled and has required settings
        baseline_enabled = args.get("quality_gate_config", {}).get("baseline", {}).get("checked")
        per_request_results_config = args.get("quality_gate_config", {}).get("settings", {}).get("per_request_results", {})
        per_request_rt_check = per_request_results_config.get('check_response_time', False)
        per_request_er_check = per_request_results_config.get('check_error_rate', False)
        per_request_tp_check = per_request_results_config.get('check_throughput', False)
        per_request_enabled = per_request_rt_check or per_request_er_check or per_request_tp_check
        summary_results_config = args.get("quality_gate_config", {}).get("settings", {}).get("summary_results", {})
        summary_rt_check = summary_results_config.get('check_response_time', False)
        summary_er_check = summary_results_config.get('check_error_rate', False)
        summary_tp_check = summary_results_config.get('check_throughput', False)
        summary_enabled = summary_rt_check or summary_er_check or summary_tp_check
        baseline_has_data = baseline and len(baseline) > 0
        baseline_operational = baseline_enabled and (per_request_enabled or summary_enabled) and baseline_has_data
        
        # Check if Baseline is enabled but no baseline data exists
        # Priority 0b: Show this warning regardless of section settings - if Baseline is enabled, user needs to set a baseline test
        baseline_enabled_but_missing = baseline_enabled and not baseline_has_data
        
        if baseline_enabled_but_missing:
            # Baseline is enabled in Quality Gate but no baseline test is defined
            test_params["performance_degradation_rate"] = f'-'
            test_params["baseline_status"] = "missing"
            test_params["baseline_note"] = "Baseline check is enabled but no baseline is set. Please set a baseline test first."
        elif args.get("performance_degradation_rate_qg", None) and baseline_operational:
            if test_params["performance_degradation_rate"] > args["performance_degradation_rate_qg"]:
                test_params["performance_degradation_rate"] = f'{test_params["performance_degradation_rate"]}%'
                test_params["baseline_status"] = "failed"
            elif test_params["performance_degradation_rate"] > 0:
                test_params["performance_degradation_rate"] = f'{test_params["performance_degradation_rate"]}%'
                test_params["baseline_status"] = "warning"
            else:
                test_params["performance_degradation_rate"] = f'{test_params["performance_degradation_rate"]}%'
                test_params["baseline_status"] = "success"
        else:
            test_params["performance_degradation_rate"] = f'-'
            test_params["baseline_status"] = "N/A"
        
        # Check if SLA is actually enabled and has required settings
        sla_enabled = args.get("quality_gate_config", {}).get("SLA", {}).get("checked")
        sla_operational = sla_enabled and (per_request_enabled or summary_enabled)
        # Check if at least one SLA threshold exists in General metrics OR Request metrics
        # Use show_threshold_column from both general_metrics and baseline_and_thresholds
        sla_has_thresholds = general_metrics.get('show_threshold_column', False) or baseline_and_thresholds.get('show_threshold_column', False)
        
        if args.get("missed_thresholds_qg", None) and sla_operational and sla_has_thresholds:
            if test_params["missed_threshold_rate"] > args["missed_thresholds_qg"]:
                test_params["missed_threshold_rate"] = f'{test_params["missed_threshold_rate"]}%'
                test_params["threshold_status"] = "failed"
            elif test_params["missed_threshold_rate"] > 0:
                test_params["missed_threshold_rate"] = f'{test_params["missed_threshold_rate"]}%'
                test_params["threshold_status"] = "warning"
            else:
                test_params["missed_threshold_rate"] = f'{test_params["missed_threshold_rate"]}%'
                test_params["threshold_status"] = "success"
        else:
            test_params["missed_threshold_rate"] = f'-'
            test_params["threshold_status"] = "N/A"
        
        html = template.render(t_params=test_params, summary=last_test_data, baseline=baseline,
                               comparison=builds_comparison,
                               baseline_and_thresholds=baseline_and_thresholds, general_metrics=general_metrics,
                               comparison_metric=comparison_metric)
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
            
            # Add category field for grouping in Results summary table
            method = results_list[_].get('method', '').upper()
            if results_list[_].get('request_name', '').lower() == 'all':
                results_list[_]['category'] = 'all'
            elif method == 'TRANSACTION':
                results_list[_]['category'] = 'transaction'
            else:
                results_list[_]['category'] = 'request'
        return results_list

    @staticmethod
    def get_ui_email_body(test_params, top_five_thresholds, builds_comparison, last_test_data):
        env = Environment(loader=FileSystemLoader('./templates/'))
        template = env.get_template("ui_email_template.html")
        html = template.render(t_params=test_params, top_five_thresholds=top_five_thresholds,
                               comparison=builds_comparison,
                               summary=last_test_data)
        return html
