class PerformanceReportGenerator:
    """
    Generates executive performance summaries based on Google Core Web Vitals standards
    and custom threshold configurations.
    
    The generator uses a 6-case decision matrix that balances:
    - User-defined threshold compliance (CI/CD gates)
    - Google CWV standards (User Experience benchmarks)
    - Historical trend analysis (Performance trajectory)
    """
    
    def __init__(self):
        # Google Core Web Vitals Constants (as of 2024)
        self.LCP_GOOD_THRESHOLD = 2.5  # seconds
        self.LCP_POOR_THRESHOLD = 4.0  # seconds
        self.INP_GOOD_THRESHOLD = 0.2  # seconds (200ms)
        self.INP_POOR_THRESHOLD = 0.5  # seconds (500ms)

    def _get_cwv_label(self, value, metric_type):
        """
        Returns Google CWV label based on metric value.
        
        Args:
            value (float): Metric value in seconds
            metric_type (str): 'LCP' or 'INP'
            
        Returns:
            tuple: (label, color) e.g., ("Good", "green")
        """
        if metric_type == 'LCP':
            if value <= self.LCP_GOOD_THRESHOLD: 
                return "Good", "green"
            if value <= self.LCP_POOR_THRESHOLD: 
                return "Needs Improvement", "orange"
            return "Poor", "red"
        elif metric_type == 'INP':
            if value <= self.INP_GOOD_THRESHOLD: 
                return "Good", "green"
            if value <= self.INP_POOR_THRESHOLD: 
                return "Needs Improvement", "orange"
            return "Poor", "red"
        return "Unknown", "grey"

    def _analyze_trend(self, current, previous, tolerance_percent=10.0):
        """
        Determines if the metric is Improving, Stable, or Degrading.
        Uses a configurable tolerance buffer to avoid noise from minor fluctuations.
        
        Args:
            current (float): Current metric value
            previous (float): Previous metric value
            tolerance_percent (float): Tolerance percentage (default: 10.0)
            
        Returns:
            str: "Improving", "Stable", or "Degrading"
        """
        if previous == 0:
            if current == 0: 
                return "Stable"
            return "Degrading"  # Any increase from 0 is degrading

        diff = current - previous
        threshold = previous * (tolerance_percent / 100.0)

        if abs(diff) <= threshold:
            return "Stable"
        elif diff < 0:
            return "Improving"  # Lower is better for web vitals
        else:
            return "Degrading"

    def generate_summary(self, 
                         threshold_status: str, 
                         lcp_p75: float, 
                         inp_p75: float, 
                         prev_lcp_p75: float, 
                         prev_inp_p75: float,
                         degradation_rate: float = 10.0):
        """
        Generates the Executive Summary based on the 6-case logic matrix.
        
        Decision Matrix:
        ┌─────────────────┬──────────────┬──────────────┐
        │                 │ CWV Good     │ CWV Poor     │
        ├─────────────────┼──────────────┼──────────────┤
        │ No Thresholds   │ SUCCESS (1)  │ WARNING (2)  │
        │ Thresholds Pass │ SUCCESS (3)  │ WARNING (4)  │
        │ Thresholds Fail │ FAILURE (5)  │ FAILURE (6)  │
        └─────────────────┴──────────────┴──────────────┘
        
        Args:
            threshold_status (str): "Success", "Failed", or "Finished" (No thresholds set)
            lcp_p75 (float): Current 75th percentile LCP in seconds
            inp_p75 (float): Current 75th percentile INP in seconds
            prev_lcp_p75 (float): Previous run's p75 LCP in seconds
            prev_inp_p75 (float): Previous run's p75 INP in seconds
            degradation_rate (float): Tolerance percentage for trend analysis (default: 10.0)
            
        Returns:
            dict: Summary containing status, verdict, and metric details
        """

        # 1. Evaluate Google CWV Standards
        lcp_label, lcp_color = self._get_cwv_label(lcp_p75, 'LCP')
        inp_label, inp_color = self._get_cwv_label(inp_p75, 'INP')
        
        # Both must be Good to count as "CWV Good"
        is_cwv_good = (lcp_label == "Good") and (inp_label == "Good")

        # 2. Analyze Trends
        lcp_trend = self._analyze_trend(lcp_p75, prev_lcp_p75, degradation_rate)
        inp_trend = self._analyze_trend(inp_p75, prev_inp_p75, degradation_rate)

        # 3. Determine Final Status & Verdict (The 6 Cases)
        # Map input status to boolean logic
        thresholds_set = threshold_status != "Finished"
        threshold_passed = threshold_status == "Success"

        final_status = ""
        status_color = ""
        verdict_text = ""

        # Logic Matrix Implementation
        if not thresholds_set:
            if is_cwv_good:
                # Case 1: No thresholds, CWV Good
                final_status = "SUCCESS"
                status_color = "green"
                verdict_text = "✅ All pages meet Google Core Web Vitals (CWV) standards at the 75th percentile."
            else:
                # Case 2: No thresholds, CWV Poor
                final_status = "WARNING"
                status_color = "orange"
                verdict_text = "⚠️ All pages fall below Google CWV standards. Optimize to ensure the 75th percentile meets 'Good' status."
        
        elif thresholds_set and threshold_passed:
            if is_cwv_good:
                # Case 3: Thresholds pass, CWV Good
                final_status = "SUCCESS"
                status_color = "green"
                verdict_text = "✅ Custom thresholds passed. All pages meet Google CWV standards at the 75th percentile."
            else:
                # Case 4: Thresholds pass, CWV Poor (The Legacy Trap)
                final_status = "WARNING"
                status_color = "orange"
                verdict_text = "⚠️ Custom thresholds passed, but all pages fall below Google CWV standards at the 75th percentile. Tighten thresholds to align with Google benchmarks."
        
        elif thresholds_set and not threshold_passed:
            # Cases 5 & 6 are both Failures
            final_status = "FAILURE"
            status_color = "red"
            if is_cwv_good:
                # Case 5: Thresholds fail, CWV Good (Strict SLA Breach)
                verdict_text = "❌ Custom thresholds failed, though all pages meet Google CWV standards at the 75th percentile. Your thresholds are stricter than Google benchmarks."
            else:
                # Case 6: Thresholds fail, CWV Poor (Total Failure)
                verdict_text = "❌ Custom thresholds failed, and all pages fall below Google CWV standards at the 75th percentile. Immediate optimization is required."

        # 4. Construct Output
        return {
            "status": final_status,
            "status_color": status_color,
            "verdict": verdict_text,
            "metrics": {
                "lcp": {
                    "value": f"{lcp_p75}s",
                    "label": lcp_label,
                    "color": lcp_color,
                    "trend": lcp_trend
                },
                "inp": {
                    "value": f"{inp_p75}s",
                    "label": inp_label,
                    "color": inp_color,
                    "trend": inp_trend
                }
            }
        }
