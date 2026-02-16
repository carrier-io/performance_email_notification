class PerformanceReportGenerator:
    """
    Generates performance metrics evaluation based on Google Core Web Vitals standards
    and historical trend analysis.
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
        Generates performance metrics summary with trend analysis.
        
        Args:
            threshold_status (str): Not used in simplified version, kept for compatibility
            lcp_p75 (float): Current 75th percentile LCP in seconds
            inp_p75 (float): Current 75th percentile INP in seconds
            prev_lcp_p75 (float): Previous run's p75 LCP in seconds
            prev_inp_p75 (float): Previous run's p75 INP in seconds
            degradation_rate (float): Tolerance percentage for trend analysis (default: 10.0)
            
        Returns:
            dict: Metrics summary containing LCP and INP data with trends
        """

        # Evaluate Google CWV Standards
        lcp_label, lcp_color = self._get_cwv_label(lcp_p75, 'LCP')
        inp_label, inp_color = self._get_cwv_label(inp_p75, 'INP')

        # Analyze Trends
        lcp_trend = self._analyze_trend(lcp_p75, prev_lcp_p75, degradation_rate)
        inp_trend = self._analyze_trend(inp_p75, prev_inp_p75, degradation_rate)

        # Return simplified metrics-only summary
        return {
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
