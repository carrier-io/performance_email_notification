from datetime import datetime
import pytz
import requests
import numpy as np
from jinja2 import Environment, FileSystemLoader
from email.mime.image import MIMEImage

from chart_generator import ui_metrics_chart_pages, ui_metrics_chart_actions
from email_notifications import Email
from thresholds_comparison import ThresholdsComparison
from performance_report_generator import PerformanceReportGenerator

GREEN = '#18B64D'
YELLOW = '#FFA400'
RED = '#FF0000'
GRAY = '#CCCCCC'


class UIEmailNotification:
    def __init__(self, arguments):
        self.test_id = arguments['test_id']
        self.gelloper_url = arguments['galloper_url']
        self.gelloper_token = arguments['token']
        self.galloper_project_id = arguments['project_id']
        self.report_id = arguments['report_id']
        self.test_name = arguments['test']
        self.args = arguments


    def _safe_metric_conversion(self, value, metric_name, is_cls=False, divisor=1000):
        """Convert metric value safely with error handling."""
        try:
            if value == "No data":
                return value
            return round(float(value) / divisor, 2) if not is_cls else round(float(value), 2)
        except (ValueError, TypeError) as e:
            print(f"[WARNING] Invalid value for metric '{metric_name}': {e}")
            return "No data"

    def _aggregate_metrics(self, test_data, metric_names, is_cls_metric=False):
        """Aggregate metrics from test data using 75th percentile (p75)."""
        aggregated = {}
        for metric in metric_names:
            try:
                if metric == "cls":
                    _arr = [float(item[metric]) for item in test_data if metric in item]
                else:
                    _arr = [int(item[metric]) for item in test_data if metric in item]
                
                if len(_arr) > 0:
                    # Calculate 75th percentile using numpy for statistical accuracy
                    p75_value = np.percentile(_arr, 75)
                    
                    if metric == "cls":
                        aggregated[metric] = round(p75_value, 2)
                    else:
                        aggregated[metric] = round(p75_value / 1000, 2)
                else:
                    aggregated[metric] = "No data"
            except (KeyError, ValueError, TypeError) as e:
                print(f"[WARNING] Missing or invalid metric '{metric}': {e}")
                aggregated[metric] = "No data"
        return aggregated

    def _build_comparison_data(self, last_reports, tests_data):
        """Build page and action comparison data from test results using p75."""
        page_comparison, action_comparison = [], []

        for index, test in enumerate(tests_data):
            test_date = self.convert_short_date_to_cet(last_reports[index]["start_time"], '%d-%b %H:%M')
            
            # Filter out FAILED status (if status is missing, assume OK)
            filtered_pages = [p for p in test["pages"] if p.get("status") != "FAILED"]
            filtered_actions = [a for a in test["actions"] if a.get("status") != "FAILED"]
            
            page_metrics = self._aggregate_metrics(filtered_pages, ["load_time", "tbt", "fcp", "lcp", "ttfb"])
            page_metrics["date"] = test_date
            page_metrics[
                "report"] = f"{self.gelloper_url}/-/performance/ui/results?result_id={last_reports[index]['id']}"
            page_comparison.append(page_metrics)

            action_metrics = self._aggregate_metrics(filtered_actions, ["cls", "tbt", "inp"])
            action_metrics["date"] = test_date
            action_metrics[
                "report"] = f"{self.gelloper_url}/-/performance/ui/results?result_id={last_reports[index]['id']}"
            action_comparison.append(action_metrics)

        return page_comparison, action_comparison

    def _apply_threshold_colors(self, results_info, thresholds_grouped, thresholds_processor, report_info):
        """Apply threshold-based color coding to results."""
        total_checked = failed_count = 0
        failed_pages_lcp = []
        failed_actions_inp = []

        for result in results_info:
            identifier = result.get('identifier', result.get('name'))
            result_type = result.get('type', 'page')

            applicable_thresholds = (
                    thresholds_grouped.get('every', []) +
                    thresholds_grouped.get(identifier, []) +
                    thresholds_grouped.get('all', [])
            )

            metrics_to_check = ["load_time", "dom", "fcp", "lcp", "cls", "tbt", "ttfb", "fvc", "lvc"] \
                if result_type == "page" else ["cls", "tbt", "inp"]

            for metric_short in metrics_to_check:
                if metric_short not in result:
                    continue

                metric_full = thresholds_processor.METRICS_MAPPER.get(metric_short, metric_short)
                metric_thresholds = [th for th in applicable_thresholds if th.get('target') == metric_full]

                if not metric_thresholds:
                    result[f"{metric_short}_color"] = ""
                    continue

                actual_value = float(result[metric_short]) if metric_short == "cls" else int(result[metric_short])
                is_failed = False

                for threshold in metric_thresholds:
                    threshold_value = threshold.get('value', 0)
                    if metric_short != "cls":
                        threshold_value *= 1000

                    comparison = threshold.get('comparison', 'lte')
                    total_checked += 1

                    if thresholds_processor.is_threshold_failed(actual_value, comparison, threshold_value):
                        is_failed = True
                        failed_count += 1
                        print(
                            f"[THRESHOLD VIOLATION] {result.get('name')} - {metric_short}: {actual_value} violates {comparison} {threshold_value}")
                        
                        # Track failed LCP pages and INP actions (convert back to seconds for display)
                        if metric_short == "lcp" and result_type == "page":
                            failed_pages_lcp.append({
                                "name": result.get('name'),
                                "value": round(actual_value / 1000, 2),  # Convert to seconds
                                "threshold": threshold_value,
                                "report": result.get('report', '')
                            })
                        elif metric_short == "inp" and result_type == "action":
                            failed_actions_inp.append({
                                "name": result.get('name'),
                                "value": round(actual_value / 1000, 2),  # Convert to seconds
                                "threshold": threshold_value,
                                "report": result.get('report', '')
                            })
                        
                        break
                    else:
                        print(
                            f"[THRESHOLD PASS] {result.get('name')} - {metric_short}: {actual_value} complies with {comparison} {threshold_value}")

                result[f"{metric_short}_color"] = f"color: {RED};" if is_failed else f"color: {GREEN};"

        missed_pct = round(float(failed_count / total_checked) * 100, 2) if total_checked > 0 else 0
        print(f"[THRESHOLDS SUMMARY] Total: {total_checked}, Failed: {failed_count}, Missed: {missed_pct}%")
        
        # Sort and get top 3
        failed_pages_lcp.sort(key=lambda x: x['value'], reverse=True)
        failed_actions_inp.sort(key=lambda x: x['value'], reverse=True)
        
        return missed_pct, failed_pages_lcp[:3], failed_actions_inp[:3]

    def _convert_result_units(self, results_info):
        """Convert result units from milliseconds to seconds."""
        for result in results_info:
            result["report"] = f"{self.gelloper_url}{result['report'][0]}"

            for metric in ["load_time", "dom", "fcp", "lcp", "tbt", "ttfb", "fvc", "lvc", "inp"]:
                if metric in result:
                    result[metric] = self._safe_metric_conversion(result[metric], metric)
                else:
                    result[metric] = "No data"

            if "cls" in result:
                result["cls"] = self._safe_metric_conversion(result["cls"], "cls", is_cls=True, divisor=1)
            else:
                result["cls"] = "No data"

    def _process_baseline_comparison(self, baseline_info, results_info, baseline_report_info):
        """Process baseline comparison and calculate degradation rate."""
        # Filter out FAILED status from both baseline and current results
        filtered_baseline_info = [r for r in baseline_info if r.get("status") != "FAILED"]
        filtered_results_info = [r for r in results_info if r.get("status") != "FAILED"]
        
        baseline_results = self._aggregate_results_by_identifier(filtered_baseline_info, is_baseline=True)
        current_results = self._aggregate_results_by_identifier(filtered_results_info, is_baseline=False)

        aggregated_baseline = self._finalize_aggregated_results(baseline_results)
        aggregated_current = self._finalize_aggregated_results(current_results)

        baseline_comparison_pages, baseline_comparison_actions = [], []
        count, failed = 0, 0
        degradation_rate_setting = self.args.get("deviation")
        try:
            degradation_rate_setting = float(degradation_rate_setting)
        except (TypeError, ValueError):
            degradation_rate_setting = 0.0
        if degradation_rate_setting < 0:
            degradation_rate_setting = 0.0

        for current in aggregated_current:
            baseline = next((b for b in aggregated_baseline if b["identifier"] == current["identifier"]), None)
            if not baseline:
                continue

            comparison = {"name": current["name"]}
            metrics = ["lcp", "tbt", "ttfb"] if current["type"] == "page" else ["tbt", "cls", "inp"]
            impact_metric = "lcp" if current["type"] == "page" else "inp"
            any_failed = False
            any_checked = False

            for metric in metrics:
                comparison[metric] = current[metric]
                comparison[f"{metric}_baseline"] = baseline[metric]

                if current[metric] == "No data" or baseline[
                    metric] == "No data":
                    comparison[f"{metric}_diff"] = "No data"
                    comparison[f"{metric}_diff_color"] = ""
                else:
                    if metric == impact_metric:
                        any_checked = True
                    baseline_with_deviation = float(baseline[metric]) * (1 + (degradation_rate_setting / 100))
                    baseline_with_deviation = round(baseline_with_deviation, 2)
                    comparison[f"{metric}_baseline"] = baseline_with_deviation
                    diff = round(float(current[metric]) - baseline_with_deviation, 2)
                    if diff > 0:
                        if metric == impact_metric:
                            # Only the impact metric affects status for page/action comparison.
                            any_failed = True
                        comparison[f"{metric}_diff"] = f'+{diff}'
                        comparison[f"{metric}_diff_color"] = "color:red;"
                    else:
                        comparison[f"{metric}_diff"] = diff
                        comparison[f"{metric}_diff_color"] = "color:green;"

            if any_checked:
                count += 1
                if any_failed:
                    failed += 1
            comparison["comparison_failed"] = any_failed
            target_list = baseline_comparison_pages if current["type"] == "page" else baseline_comparison_actions
            target_list.append(comparison)

        baseline_comparison_pages = sorted(
            baseline_comparison_pages,
            key=lambda item: (not item.get("comparison_failed", False), item.get("name", ""))
        )
        baseline_comparison_actions = sorted(
            baseline_comparison_actions,
            key=lambda item: (not item.get("comparison_failed", False), item.get("name", ""))
        )

        degradation_rate = round(float(failed / count) * 100, 2) if count else 0
        return baseline_comparison_pages, baseline_comparison_actions, degradation_rate, aggregated_baseline

    def _aggregate_results_by_identifier(self, results, is_baseline):
        """Aggregate results by identifier for comparison."""
        aggregated = {}

        for result in results:
            identifier = result["identifier"]
            if identifier not in aggregated:
                aggregated[identifier] = {"name": result["name"], "type": result["type"]}

            metrics = ["load_time", "fcp", "lcp", "tbt", "ttfb"] if result["type"] == "page" else ["tbt", "cls", "inp"]

            for metric in metrics:
                if metric not in result:
                    self._append_metric_value(aggregated[identifier], metric, "No data")
                    continue

                value = result[metric]
                if value == "No data":
                    self._append_metric_value(aggregated[identifier], metric, value)
                elif is_baseline:
                    converted = self._safe_metric_conversion(value, metric, is_cls=(metric == "cls"))
                    self._append_metric_value(aggregated[identifier], metric, converted)
                else:
                    self._append_metric_value(aggregated[identifier], metric, float(value))

        return aggregated

    def _append_metric_value(self, target_dict, metric, value):
        """Helper to append metric value to aggregated dict."""
        if metric not in target_dict:
            target_dict[metric] = []
        target_dict[metric].append(value)

    def _finalize_aggregated_results(self, aggregated_dict):
        """Convert aggregated metric lists to 75th percentile."""
        finalized = []

        for identifier, data in aggregated_dict.items():
            result = {"identifier": identifier, "name": data["name"], "type": data["type"]}

            for metric in ["load_time", "fcp", "lcp", "tbt", "inp", "cls", "ttfb"]:
                if metric not in data:
                    result[metric] = "No data"
                    continue

                values = data[metric]
                if "No data" in values:
                    result[metric] = "No data"
                else:
                    # Calculate 75th percentile using numpy for statistical accuracy
                    p75_value = np.percentile(values, 75)
                    result[metric] = round(p75_value, 2)

            finalized.append(result)

        return finalized

    def _calculate_p75_metrics(self, results_info):
        """
        Calculate 75th percentile for LCP and INP from results.
        
        Args:
            results_info (list): List of result dictionaries
            
        Returns:
            dict: {"lcp_p75": float, "inp_p75": float}
        """
        lcp_values = []
        inp_values = []
        
        for result in results_info:
            # Skip FAILED results
            if result.get("status") == "FAILED":
                continue
            
            # Collect LCP from pages
            if result.get('type') == 'page' and 'lcp' in result:
                value = result['lcp']
                if value != "No data":
                    try:
                        lcp_values.append(float(value))
                    except (ValueError, TypeError):
                        pass
            
            # Collect INP from actions
            if result.get('type') == 'action' and 'inp' in result:
                value = result['inp']
                if value != "No data":
                    try:
                        inp_values.append(float(value))
                    except (ValueError, TypeError):
                        pass
        
        # Calculate p75 (75th percentile) using numpy for statistical accuracy
        def calculate_percentile(values, percentile=75):
            if not values:
                return 0.0
            return round(np.percentile(values, percentile), 2)
        
        return {
            "lcp_p75": calculate_percentile(lcp_values),
            "inp_p75": calculate_percentile(inp_values)
        }

    def ui_email_notification(self):
        info = self._get_test_info()
        last_reports = self._get_last_report(info['name'], 10)

        tests_data = []
        for each in last_reports:
            if each["test_status"]["status"] not in ["Finished", "Success", "Failed"] or len(tests_data) >= 5:
                continue

            report = {"pages": [], "actions": []}
            results_info = self._get_results_info(each["uid"])
            for result in results_info:
                report["pages" if result["type"] == "page" else "actions"].append(result)
            tests_data.append(report)

        page_comparison, action_comparison = self._build_comparison_data(last_reports, tests_data)

        report_info = self._get_report_info()
        report_uid = report_info.get("uid", self.report_id)
        results_info = self._get_results_info(report_uid)
        test_environment = report_info["environment"]

        test_status = report_info.get("test_status", {})
        status = test_status.get("status", "PASSED")
        thresholds_total = report_info.get("thresholds_total", 0)
        thresholds_failed = report_info.get("thresholds_failed", 0)

        if thresholds_total > 0:
            missed_thresholds = round((thresholds_failed / thresholds_total) * 100, 1)
        else:
            missed_thresholds = 0

        if status == "Failed":
            color = RED
        elif status == "Finished":
            color = None
        else:
            color = GREEN

        thresholds_processor = ThresholdsComparison(
            self.gelloper_url, self.gelloper_token, self.galloper_project_id, self.report_id
        )

        try:
            raw_thresholds = thresholds_processor.get_thresholds_info()
            print(f"[RAW THRESHOLDS] Total: {len(raw_thresholds)}")

            thresholds_grouped = thresholds_processor.get_thresholds_grouped_by_scope(
                report_info['name'], test_environment
            )
            print(
                f"[THRESHOLDS] Loaded {sum(len(v) for v in thresholds_grouped.values())} across {len(thresholds_grouped)} scopes")
        except Exception as e:
            print(f"[WARNING] Could not load thresholds: {e}")
            thresholds_grouped = {}

        local_missed_thresholds, failed_pages_lcp, failed_actions_inp = self._apply_threshold_colors(
            results_info, thresholds_grouped, thresholds_processor, report_info
        )
        self._convert_result_units(results_info)

        try:
            baseline_id = self._get_baseline_report(report_info['name'], report_info['environment'])
            base_id = baseline_id["baseline_id"]
        except Exception as e:
            print(e)
            base_id = None

        baseline_info, baseline_test_url, baseline_test_date = [], "", ""
        baseline_comparison_pages, baseline_comparison_actions = [], []
        aggregated_baseline = []
        degradation_rate = 0

        if base_id:
            baseline_report_info = self._get_url(
                f"/ui_performance/reports/{self.galloper_project_id}?report_id={base_id}")
            baseline_info = self._get_results_info(base_id)
            baseline_test_url = f"{self.gelloper_url}/-/performance/ui/results?result_id={baseline_report_info['id']}"
            baseline_test_date = baseline_report_info['start_time']

            baseline_comparison_pages, baseline_comparison_actions, degradation_rate, aggregated_baseline = \
                self._process_baseline_comparison(baseline_info, results_info, baseline_report_info)

        # Quality gate enforcement logic
        missed_threshold_rate = self.args.get('missed_threshold_rate', 0)
        baseline_deviation = self.args.get('baseline_deviation', 0)
        reasons_to_fail_report = []

        # Check threshold quality gate (skip if missed_threshold_rate is 0)
        if missed_threshold_rate > 0:
            if missed_thresholds > missed_threshold_rate:
                status = "Failed"
                color = RED
                reasons_to_fail_report.append("Failed by thresholds comparison to quality gate")
                print(f"[QUALITY GATE] Threshold gate FAILED: {missed_thresholds}% > {missed_threshold_rate}%")
            else:
                print(f"[QUALITY GATE] Threshold gate PASSED: {missed_thresholds}% <= {missed_threshold_rate}%")
        else:
            print(f"[QUALITY GATE] Threshold gate check SKIPPED (missed_threshold_rate=0)")

        # Check baseline quality gate (skip if baseline_deviation is 0 or no baseline)
        if baseline_deviation > 0 and base_id is not None:
            if degradation_rate > baseline_deviation:
                status = "Failed"
                color = RED
                reasons_to_fail_report.append("Failed by baseline comparison to quality gate")
                print(f"[QUALITY GATE] Baseline gate FAILED: {degradation_rate}% > {baseline_deviation}%")
            else:
                print(f"[QUALITY GATE] Baseline gate PASSED: {degradation_rate}% <= {baseline_deviation}%")
        else:
            if baseline_deviation == 0:
                print(f"[QUALITY GATE] Baseline gate check SKIPPED (baseline_deviation=0)")
            elif base_id is None:
                print(f"[QUALITY GATE] Baseline gate check SKIPPED (no baseline configured)")

        print(f"[QUALITY GATE] Final status: {status}, Reasons: {reasons_to_fail_report}")

        browser_version = report_info.get('browser_version')
        if not browser_version or browser_version == 'undefined':
            browser_version = results_info[0].get('browser_version', 'Unknown') if results_info else 'Unknown'

        # Generate Performance Summary based on Google CWV standards
        try:
            # Get degradation rate setting
            degradation_rate_setting = self.args.get("baseline_deviation")
            try:
                degradation_rate_setting = float(degradation_rate_setting)
            except (TypeError, ValueError):
                degradation_rate_setting = 10.0  # Default to 10%
            if degradation_rate_setting < 0:
                degradation_rate_setting = 10.0
            
            # Calculate current p75 metrics
            current_metrics = self._calculate_p75_metrics(results_info)
            
            # Calculate previous p75 metrics from baseline or last report
            prev_lcp_p75 = 0.0
            prev_inp_p75 = 0.0
            
            if aggregated_baseline:
                # Use baseline data if available - need to convert units first
                # Create a copy to avoid modifying the original baseline_info
                baseline_info_copy = [dict(item) for item in baseline_info]
                self._convert_result_units(baseline_info_copy)
                baseline_metrics = self._calculate_p75_metrics(baseline_info_copy)
                prev_lcp_p75 = baseline_metrics.get("lcp_p75", 0.0)
                prev_inp_p75 = baseline_metrics.get("inp_p75", 0.0)
            elif len(tests_data) > 1:
                # Use previous test run data - need to convert units first
                prev_test_results = tests_data[1]["pages"] + tests_data[1]["actions"]
                # Create a copy to avoid modifying the original data
                prev_test_results_copy = [dict(item) for item in prev_test_results]
                self._convert_result_units(prev_test_results_copy)
                prev_metrics = self._calculate_p75_metrics(prev_test_results_copy)
                prev_lcp_p75 = prev_metrics.get("lcp_p75", 0.0)
                prev_inp_p75 = prev_metrics.get("inp_p75", 0.0)
            
            # Determine threshold status for summary generator
            if status == "Failed":
                threshold_status = "Failed"
            elif status == "Finished":
                threshold_status = "Finished"
            else:
                threshold_status = "Success"
            
            # Generate the executive summary
            perf_generator = PerformanceReportGenerator()
            performance_summary = perf_generator.generate_summary(
                threshold_status=threshold_status,
                lcp_p75=current_metrics["lcp_p75"],
                inp_p75=current_metrics["inp_p75"],
                prev_lcp_p75=prev_lcp_p75,
                prev_inp_p75=prev_inp_p75,
                degradation_rate=degradation_rate_setting
            )
            
        except Exception as e:
            print(f"[WARNING] Could not generate performance summary: {e}")
            # Fallback to basic summary
            performance_summary = {
                "metrics": {
                    "lcp": {"value": "N/A", "label": "Unknown", "color": "grey", "trend": "Unknown"},
                    "inp": {"value": "N/A", "label": "Unknown", "color": "grey", "trend": "Unknown"}
                }
            }

        # Download and parse log file from artifacts
        log_failed_transactions = []
        try:
            bucket = report_info['name'].replace(' ', '').replace('_', '').lower()
            log_content = self._download_log_file(bucket, report_uid)
            log_filename = f"log_{report_info['id']}_{report_uid}.log"
            with open(log_filename, 'wb') as f:
                f.write(log_content)
            print(f"[LOG DOWNLOAD] Saved log to: {log_filename}")
            parsed = self._parse_log_file(log_content)
            log_failed_transactions = parsed['failed_transactions']
            print(f"[LOG PARSE] Failed transactions: {[t['name'] for t in log_failed_transactions]}")
        except Exception as e:
            print(f"[LOG DOWNLOAD] Error: {e}")

        t_params = {
            "scenario": report_info['name'],
            "baseline_test_url": baseline_test_url,
            "baseline_test_date": baseline_test_date,
            "current_test_url": f"{self.gelloper_url}/-/performance/ui/results?result_id={report_info['id']}",
            "start_time": self.convert_short_date_to_cet(report_info["start_time"]),
            "status": status,
            "color": color,
            "missed_thresholds": missed_thresholds,
            "degradation_rate": degradation_rate,
            "duration": report_info['duration'],
            "env": report_info['environment'],
            "browser": report_info['browser'].capitalize(),
            "version": browser_version,
            "loops": report_info["loops"],
            "pages": len(results_info),
            "total_thresholds": thresholds_total,
            "performance_summary": performance_summary,
            "reasons_to_fail_report": reasons_to_fail_report
        }

        status_str = t_params["status"].lower()
        if status_str == "failed":
            emoji = "❌"
            status_word = "Failed"
        else:
            emoji = "✅"
            status_word = "Success"
        # Format subject line with date as DD-MM HH:MM CET
        subject_time = self.convert_short_date_to_cet(report_info["start_time"], '%d-%m %H:%M')
        subject = f"{emoji} {info['name']} {subject_time} CET"
        date = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
        email_body = self._get_email_body(
            t_params, results_info, page_comparison, action_comparison,
            baseline_comparison_pages, baseline_comparison_actions, degradation_rate,
            missed_thresholds, baseline_info, aggregated_baseline,
            failed_pages_lcp, failed_actions_inp,
            log_failed_transactions
        )

        charts = [
            self.create_ui_metrics_chart_pages(page_comparison),
            self.create_ui_metrics_chart_actions(action_comparison)
        ]

        return Email(self.test_name, subject, self.args['user_list'], email_body, charts, date)

    def _get_test_info(self):
        return self._get_url(f"/ui_performance/test/{self.galloper_project_id}/{self.test_id}?raw=1")

    def _get_baseline_report(self, name, env):
        return self._get_url(f"/ui_performance/baseline/{self.galloper_project_id}?test_name={name}&env={env}")

    def _get_last_report(self, name, count):
        return self._get_url(f"/ui_performance/reports/{self.galloper_project_id}?name={name}&count={count}")

    def _get_report_info(self):
        return self._get_url(f"/ui_performance/reports/{self.galloper_project_id}?report_id={self.report_id}")

    def _get_results_info(self, report_id):
        return self._get_url(f"/ui_performance/results/{self.galloper_project_id}/{report_id}?order=asc")
    
    def _download_log_file(self, bucket, report_uid):
        return self._get_url(f"/artifacts/artifact/{self.galloper_project_id}/{bucket}/{report_uid}.log", raw=True)

    @staticmethod
    def _parse_log_file(log_content):
        """Parse log content and extract failed transactions with their [ERROR] messages."""
        import re
        errors_by_transaction = {}
        failed_transactions = []
        seen_transactions = set()

        for raw_line in log_content.decode('utf-8', errors='replace').splitlines():
            line = raw_line.strip()
            if not line:
                continue

            if '[ERROR]' in line:
                # Strip leading: "2026-02-20 11:47:53\t[2026-02-20T11:47:44] "
                cleaned = re.sub(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s+\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\]\s+', '', line)
                # Extract transaction name and strip it from the end: "... on page TransactionName"
                if ' on page ' in cleaned:
                    msg_part, trans_name = cleaned.rsplit(' on page ', 1)
                    errors_by_transaction[trans_name.strip()] = msg_part.strip()

            # Pattern: <timestamp>\t[<ts>] TransactionName_Failed
            if line.endswith('_Failed'):
                token = line.split()[-1]
                name = token[:-len('_Failed')]
                if name not in seen_transactions:
                    seen_transactions.add(name)
                    failed_transactions.append(name)

            # Pattern: Status detected: FAILED for TransactionName
            if 'Status detected: FAILED for ' in line:
                name = line.split('Status detected: FAILED for ', 1)[1].strip()
                if name not in seen_transactions:
                    seen_transactions.add(name)
                    failed_transactions.append(name)

        result = [
            {'name': name, 'error': errors_by_transaction.get(name, '')}
            for name in failed_transactions
        ]
        return {'failed_transactions': result}

    def _get_email_body(self, t_params, results_info, page_comparison, action_comparison,
                        baseline_comparison_pages, baseline_comparison_actions, degradation_rate,
                        missed_thresholds, baseline_info, aggregated_baseline,
                        failed_pages_lcp, failed_actions_inp,
                        log_failed_transactions=None):
        env = Environment(loader=FileSystemLoader('./templates'))
        template = env.get_template("ui_email_template.html")
        return template.render(
            t_params=t_params, results=results_info, page_comparison=page_comparison,
            action_comparison=action_comparison, baseline_comparison_pages=baseline_comparison_pages,
            baseline_comparison_actions=baseline_comparison_actions,
            degradation_rate=degradation_rate, missed_thresholds=missed_thresholds,
            baseline_info=baseline_info, aggregated_baseline=aggregated_baseline,
            failed_pages_lcp=failed_pages_lcp, failed_actions_inp=failed_actions_inp,
            log_failed_transactions=log_failed_transactions or []
        )

    def _get_url(self, url, raw=False):
        full_url = f"{self.gelloper_url}/api/v1{url}"
        resp = requests.get(
            full_url,
            headers={
                'Authorization': f'bearer {self.gelloper_token}',
                'Content-type': 'application/json'
            }
        )
        if resp.status_code != 200:
            raise Exception(f"Error {resp}")
        return resp.content if raw else resp.json()

    @staticmethod
    def create_ui_metrics_chart_pages(builds):
        labels, x, ttfb, tbt, lcp = [], [], [], [], []
        ttfb_original, tbt_original, lcp_original = [], [], []

        for idx, test in enumerate(builds, 1):
            labels.append(test['date'])
            x.append(idx)

            ttfb_original.append(test['ttfb'])
            tbt_original.append(test['tbt'])
            lcp_original.append(test['lcp'])

            ttfb.append(round(test['ttfb'], 2) if isinstance(test['ttfb'], (int, float)) else 0)
            tbt.append(round(test['tbt'], 2) if isinstance(test['tbt'], (int, float)) else 0)
            lcp.append(round(test['lcp'], 2) if isinstance(test['lcp'], (int, float)) else 0)

        ttfb_has_data = any(isinstance(v, (int, float)) for v in ttfb_original)
        tbt_has_data = any(isinstance(v, (int, float)) for v in tbt_original)
        lcp_has_data = any(isinstance(v, (int, float)) for v in lcp_original)

        datapoints = {
            'title': 'UI metrics (p75)',
            'label': 'UI metrics (p75)',
            'x_axis': 'Test Runs',
            'y_axis': 'Time, sec',
            'width': 14,
            'height': 4,
            'path_to_save': '/tmp/ui_metrics_pages.png',
            'ttfb': ttfb[::-1],
            'tbt': tbt[::-1],
            'lcp': lcp[::-1],
            'ttfb_has_data': ttfb_has_data,
            'tbt_has_data': tbt_has_data,
            'lcp_has_data': lcp_has_data,
            'values': x,
            'labels': labels[::-1]
        }

        ui_metrics_chart_pages(datapoints)
        with open('/tmp/ui_metrics_pages.png', 'rb') as fp:
            image = MIMEImage(fp.read())
            image.add_header('Content-ID', '<ui_metrics_pages>')
        return image

    @staticmethod
    def create_ui_metrics_chart_actions(builds):
        labels, x, cls, tbt, inp = [], [], [], [], []
        cls_original, tbt_original, inp_original = [], [], []

        for idx, test in enumerate(builds, 1):
            labels.append(test['date'])
            x.append(idx)

            cls_original.append(test['cls'])
            tbt_original.append(test['tbt'])
            inp_original.append(test['inp'])

            cls.append(round(test['cls'], 2) if isinstance(test['cls'], (int, float)) else 0)
            tbt.append(round(test['tbt'], 2) if isinstance(test['tbt'], (int, float)) else 0)
            inp.append(round(test['inp'], 2) if isinstance(test['inp'], (int, float)) else 0)

        cls_has_data = any(isinstance(v, (int, float)) for v in cls_original)
        tbt_has_data = any(isinstance(v, (int, float)) for v in tbt_original)
        inp_has_data = any(isinstance(v, (int, float)) for v in inp_original)

        datapoints = {
            'title': 'UI metrics Actions (p75)',
            'label': 'UI metrics Actions (p75)',
            'x_axis': 'Test Runs',
            'y_axis': 'Time, sec',
            'width': 14,
            'height': 4,
            'path_to_save': '/tmp/ui_metrics_actions.png',
            'cls': cls[::-1],
            'tbt': tbt[::-1],
            'inp': inp[::-1],
            'cls_has_data': cls_has_data,
            'tbt_has_data': tbt_has_data,
            'inp_has_data': inp_has_data,
            'values': x,
            'labels': labels[::-1]
        }

        ui_metrics_chart_actions(datapoints)
        with open('/tmp/ui_metrics_actions.png', 'rb') as fp:
            image = MIMEImage(fp.read())
            image.add_header('Content-ID', '<ui_metrics_actions>')
        return image

    @staticmethod
    def convert_short_date_to_cet(short_date_str, output_format='%Y-%m-%d %H:%M:%S'):
        """Convert UTC datetime string to CET/CEST timezone."""
        utc_tz = pytz.UTC
        cet_tz = pytz.timezone('Europe/Paris')

        date_part = short_date_str.split('T')[0]
        year_part = date_part.split('-')[0]
        full_datetime_str = f"20{short_date_str}" if len(year_part) == 2 else short_date_str

        utc_dt = utc_tz.localize(datetime.strptime(full_datetime_str, '%Y-%m-%dT%H:%M:%S'))
        cet_dt = utc_dt.astimezone(cet_tz)

        return cet_dt.strftime(output_format)
