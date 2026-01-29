# Warnings Reference Guide

This document describes all warning messages that can appear in performance test email notifications.

---

## SLA Warnings

### Priority 0: SLA Disabled
**Conditions:** SLA checkbox is unchecked in Quality Gate configuration, but SLA thresholds exist in the system (at least one metric: Response Time, Error Rate, or Throughput is configured).

**Warning:** "SLA comparison is disabled in Quality Gate configuration. Enable SLA to see comparison with configured thresholds."

**Note:** This is the highest priority warning. When SLA is disabled, no other SLA warnings are shown. The system checks if at least one SLA metric exists, regardless of whether Quality Gate is enabled or disabled.

---

### Priority 1: Both Settings Disabled
**Conditions:** SLA is enabled, but both "Summary results" AND "Per request results" are disabled (all 6 checkboxes are unchecked).

**Warning:** "SLA is enabled, but both 'Summary results' and 'Per request results' options are disabled in Quality Gate configuration. Enable at least one option to see SLA data."

---

### Priority 2: No Thresholds Configured
**Conditions:** SLA is enabled, but NO thresholds are configured for ANY metric (no response_time AND no error_rate AND no throughput).

**Warning:** "SLA is enabled but no thresholds are configured. Please configure SLA for at least one metric (response time, error rate, or throughput)."

**Note:** If at least one metric has thresholds configured, this warning is NOT shown and SLA works normally for configured metrics.

---

### Priority 3b-3g (REMOVED): Metric-Specific Disabled Scenarios
**Status:** REMOVED - all cases now covered by Independent Informational Warning (see below).

**Rationale:** Priority 3b-3g checked for discrepancies between Summary and Per Request settings (e.g., Response Time OFF in Summary but ON in Per Request). This created dependency between sections and duplicated information from Independent info. Removed to allow independent processing of Summary and Per Request configurations.

**Previous Priorities:**
- 3b: Response Time disabled in Summary, enabled in Per Request
- 3c: Response Time enabled in Summary, disabled in Per Request  
- 3d: Throughput disabled in Summary, enabled in Per Request
- 3e: Throughput enabled in Summary, disabled in Per Request
- 3f: Error Rate disabled in Summary, enabled in Per Request
- 3g: Error Rate enabled in Summary, disabled in Per Request

---

### Priority 3h (REMOVED): Summary ON, Per Request OFF, Some Metrics Disabled
**Status:** REMOVED - cases now covered by Independent Informational Warning (see below).

**Rationale:** Priority 3h duplicated the information provided by Independent info and blocked Priority 4/5 from being checked. Removed to eliminate redundancy and allow higher priority warnings to be shown.

---

### Priority 3i (REMOVED): Summary OFF, Per Request ON, Some Metrics Disabled
**Status:** REMOVED - cases now covered by Independent Informational Warning (see below).

**Rationale:** Priority 3i duplicated the information provided by Independent info and blocked Priority 4/5 from being checked. Removed to eliminate redundancy and allow higher priority warnings to be shown.

---

### Priority 3j: Summary ON, Per Request OFF (All Metrics Enabled)
**Conditions:** SLA is enabled, Summary results is ON with all metrics enabled, Per request results is completely OFF (all 3 checkboxes unchecked).

**Warning:** "Per request SLA is disabled. Enable 'Per request results' in Quality Gate configuration to see SLA for individual requests."

---

### Priority 3: Summary OFF, Per Request ON (All Metrics Enabled)
**Conditions:** SLA is enabled, Summary results is completely OFF (all 3 checkboxes unchecked), Per request results is ON with all metrics enabled.

**Warning:** "General metrics SLA is disabled. Enable 'Summary results' in Quality Gate configuration to see SLA for general metrics."

---

### Priority 4: SLA Metric Mismatch (No "All" Scope)
**Conditions:** SLA is enabled, SLA is configured for the comparison metric (response time only), but there are issues with scope configuration.

**Warning (Case 4a1 - has "every", no "all"):** "SLA for [METRIC] uses 'Every' scope (applies to all requests by default). No general 'All' SLA is configured. Configure 'All' SLA to see aggregated metrics in General metrics table."

**Warning (Case 4a2a - no "every", no "all", all requests covered by specific SLA):** "SLA for [METRIC] is configured for individual requests. No general 'All' SLA is configured. Configure 'All' SLA to see aggregated metrics in General metrics table."

**Warning (Case 4a2b - no "every", no "all", some requests missing SLA):** "SLA for [METRIC] is configured only for specific requests. Some requests show 'Set SLA'. Configure 'Every' SLA to cover all requests and/or 'All' SLA to see aggregated metrics."

**Warning (Case 4a3 - has "all", no "every", has specific but not all covered):** "Some requests show 'Set SLA' for [METRIC] metric. Configure SLA thresholds for individual requests in Thresholds section or use 'Every' scope to apply SLA to all requests automatically."

**Note:** This priority handles ONLY cases where SLA exists for selected metric but scope configuration is incomplete. Case 4b (wrong metric) is handled by Informational Warning below. Case 4a2 is split into two variants: 4a2a (all requests have specific SLA, message focuses only on missing 'All' for aggregated metrics) and 4a2b (some requests missing SLA, message mentions 'Set SLA' and suggests 'Every' scope).

---

### Priority 5: SLA Metric Selection Info
**Conditions:** SLA is enabled, at least one SLA Response Time metric is configured, and Per request results is completely disabled (all 3 checkboxes OFF).

**Warning (Single metric):** "SLA comparison uses default metric ([COMPARISON_METRIC]). To select a different comparison metric, enable 'Per request results' in Quality Gate configuration."

**Warning (Multiple metrics):** "Multiple SLA metrics configured ([METRICS]). Report uses [SELECTED_METRIC] (default). To select a different metric, enable 'Per request results' in Quality Gate configuration."

**Note:** This warning replaces the previous "SLA comparison uses default metric" informational warning. It now handles both single and multiple metric cases with the same priority level. Shown only when Per request section is completely disabled (user has no metric selection available).

---

### Informational Warning: Disabled Metrics
**Conditions:** SLA is enabled, at least one section (Summary or Per request) is enabled, and one or more metrics are disabled in Summary, Per request, or both.

**Warning Examples:**
- "Response Time SLA is disabled for both general metrics and individual requests. Enable 'Response time' in Quality Gate configuration to see SLA for response time metrics."
- "Response Time SLA is disabled for general metrics. Enable 'Response time' in Quality Gate configuration to see SLA for response time metrics."
- "Response Time SLA is disabled for individual requests. Enable 'Response time' in Quality Gate configuration to see SLA for individual request metrics."
- "Error Rate SLA is disabled for general metrics. Enable 'Error rate' in Quality Gate configuration to see SLA for error rate metrics."
- "Throughput SLA is disabled for general metrics. Enable 'Throughput' in Quality Gate configuration to see SLA for throughput metrics."

**Note:** This warning is shown in addition to Priority warnings and lists all disabled metrics with their specific locations and detailed SLA information. Each metric gets a complete sentence with full context about what is disabled and how to enable it. Multiple disabled metrics will be combined in one message, separated by ". ".

---

### Informational Warning: SLA Metric Not Configured
**Conditions:** SLA is enabled, Summary Response Time OR Per request Response Time is enabled, Per request results is enabled (user CAN select metric), but selected comparison metric has no SLA configured.

**Warning (selected metric NOT configured - single alternative):** "SLA thresholds are not configured for [COMPARISON_METRIC] metric. SLA is available only for [CONFIGURED_METRIC]. Configure SLA thresholds in Thresholds section to see threshold values and differences in Request metrics and General metrics tables or select a different metric to see data."

**Warning (selected metric NOT configured - multiple alternatives):** "SLA thresholds are not configured for [COMPARISON_METRIC] metric. SLA is available only for [METRIC1, METRIC2, ...]. Configure SLA thresholds in Thresholds section to see threshold values and differences in Request metrics and General metrics tables or select a different metric to see data."

**Warning (no RT SLA configured at all):** "SLA comparison uses [COMPARISON_METRIC], but Response Time is not configured in Thresholds. SLA values will be hidden. Configure Response Time SLA to see data."

**Note:** This warning is shown independently (not blocked by Priority 4). It handles the case when user actively selected a metric that has no SLA configured. Shows detailed message with all available metrics. [COMPARISON_METRIC] can be any metric: PCT95, PCT99, PCT90, PCT75, PCT50, MEAN.

---

## Baseline Warnings

### Priority 0a: Baseline Disabled
**Conditions:** Baseline checkbox is unchecked in Quality Gate configuration, but baseline data exists in the system.

**Warning:** "Baseline comparison is disabled in Quality Gate configuration. Enable Baseline to see comparison with previous test results."

**Note:** This is the highest priority warning. When Baseline is disabled, no other Baseline warnings are shown. The system checks if baseline data exists, regardless of whether Quality Gate is enabled or disabled.

---

### Priority 0b: No Baseline Test Set
**Conditions:** Baseline is enabled in Quality Gate, but no baseline test is defined in the system.

**Warning:** "Baseline check is enabled but no baseline is set. Please set a baseline test first."

**Note:** This warning appears when baseline comparison is configured but there's no baseline test to compare against. This takes precedence over Priority 1 - if no baseline test exists, this warning is shown instead of configuration warnings. User needs to set a baseline test first.

---

### Priority 1: Both Settings Disabled
**Conditions:** Baseline is enabled, baseline data EXISTS, but both "Summary results" AND "Per request results" are disabled (all 6 checkboxes are unchecked).

**Warning:** "Baseline comparison is enabled, but both 'Summary results' and 'Per request results' options are disabled in Quality Gate configuration. Enable at least one option to see baseline data."

**Note:** This warning is only shown when baseline data exists. If no baseline test is set, Priority 0b takes precedence.

---

### Priority 1b: Summary ON (Only ER/TP), Per Request OFF
**Conditions:** Baseline is enabled, Summary results is ON but only Error Rate and/or Throughput are enabled (Response Time OFF), Per request results is completely OFF.

**Warning:** None (this is a valid configuration, but informational warnings about disabled Response Time and default metric may appear)

**Note:** Baseline works for Error Rate and Throughput without Response Time. However, informational messages about disabled Response Time may appear as part of the Disabled Metrics informational warning, and a warning about using the default metric may appear when Per request results is disabled.

---

### Priority 2b-2g (REMOVED): Metric-Specific Disabled Scenarios
**Status:** REMOVED - all cases now covered by Independent Informational Warning (see below).

**Rationale:** Priority 2b-2g checked for discrepancies between Summary and Per Request settings (e.g., Response Time OFF in Summary but ON in Per Request). This created dependency between sections and duplicated information from Independent info. Removed to allow independent processing of Summary and Per Request configurations.

**Previous Priorities:**
- 2b: Response Time disabled in Summary, enabled in Per Request
- 2c: Response Time enabled in Summary, disabled in Per Request
- 2d: Throughput disabled in Summary, enabled in Per Request
- 2e: Throughput enabled in Summary, disabled in Per Request
- 2f: Error Rate disabled in Summary, enabled in Per Request
- 2g: Error Rate enabled in Summary, disabled in Per Request

---

### Priority 2h (REMOVED): Summary ON, Per Request OFF, Some Metrics Disabled
**Status:** REMOVED - cases now covered by Independent Informational Warning (see below).

**Rationale:** Priority 2h duplicated the information provided by Independent info. Removed to eliminate redundancy and allow consistent warning behavior with SLA.

---

### Priority 2i (REMOVED): Summary OFF, Per Request ON, Some Metrics Disabled
**Status:** REMOVED - cases now covered by Independent Informational Warning (see below).

**Rationale:** Priority 2i duplicated the information provided by Independent info. Removed to eliminate redundancy and allow consistent warning behavior with SLA.

---

### Priority 3j: Summary ON, Per Request OFF (All Metrics Enabled)
**Conditions:** Baseline is enabled, Summary results is ON with all metrics enabled, Per request results is completely OFF (all 3 checkboxes unchecked).

**Warning:** "Per request baseline is disabled. Enable 'Per request results' in Quality Gate configuration to see baseline for individual requests."

---

### Priority 3: Summary OFF, Per Request ON (All Metrics Enabled)
**Conditions:** Baseline is enabled, Summary results is completely OFF (all 3 checkboxes unchecked), Per request results is ON with all metrics enabled.

**Warning:** "General metrics baseline is disabled. Enable 'Summary results' in Quality Gate configuration to see baseline for general metrics."

---

### Informational Warning: Disabled Metrics
**Conditions:** Baseline is enabled, at least one section (Summary or Per request) is enabled, and one or more metrics are disabled in Summary, Per request, or both.

**Warning Examples:**
- "Response Time baseline is disabled for both general metrics and individual requests. Enable 'Response time' in Quality Gate configuration to see baseline for response time metrics."
- "Response Time baseline is disabled for general metrics. Enable 'Response time' in Quality Gate configuration to see baseline for response time metrics."
- "Response Time baseline is disabled for individual requests. Enable 'Response time' in Quality Gate configuration to see baseline for individual request metrics."
- "Response Time baseline is disabled for general metrics. Enable 'Response time' in Quality Gate configuration to see baseline for response time metrics. Throughput baseline is disabled for general metrics. Enable 'Throughput' in Quality Gate configuration to see baseline for throughput metrics."

**Note:** This warning is shown in addition to Priority warnings and lists all disabled metrics with their specific locations and detailed baseline information. Each metric gets a complete sentence with full context about what is disabled and how to enable it.

---

### Informational Warning: Baseline Comparison Metric Info
**Conditions:** Baseline is enabled, Per request results is completely OFF (all 3 checkboxes unchecked), and baseline data exists.

**Warning:** "Baseline comparison uses default metric ([COMPARISON_METRIC]). To select a different comparison metric, enable 'Per request results' in Quality Gate configuration."

**Note:** Comparison metric selection requires Per request to be enabled (any metric). This informational warning is shown only when using the default metric. [COMPARISON_METRIC] can be any metric: PCT95, PCT99, PCT90, PCT75, PCT50, MEAN.

---

## Warning Priority Rules

1. **Only ONE Priority warning is shown per feature** (SLA or Baseline). The highest priority (lowest number) warning wins.

2. **SLA and Baseline Priority warnings are independent** and can appear together (one from each category).

3. **Informational warnings appear in addition to Priority warnings** and provide supplementary information.

4. **Additional warnings are suppressed** when a Priority warning already explains the situation.

5. **Disabled metrics informational warnings are always shown** when applicable, regardless of Priority warnings.

6. **Deviation warnings are shown only when data is visible** - they are suppressed for Priority 0 (feature disabled) and Priority 1 (both sections disabled).

---

## Deviation Warnings

### SLA Deviation Warning
**Conditions:** SLA is enabled, at least one section (Summary or Per request) is enabled, and any deviation value > 0 is configured.

**Warning:** "SLA has configured acceptable deviation. Validation results take into account the allowed deviation range when comparing actual values against SLA thresholds."

**Note:** Not shown when SLA is disabled (Priority 0) or when both Summary and Per request results are disabled (Priority 1), because no data is visible.

---

### Baseline Deviation Warning
**Conditions:** Baseline is enabled, baseline data exists, at least one section (Summary or Per request) is enabled, and any deviation value > 0 is configured.

**Warning:** "Baseline has configured acceptable deviation. Validation results take into account the allowed deviation range when comparing actual values against baseline."

**Note:** Not shown when Baseline is disabled (Priority 0) or when both Summary and Per request results are disabled (Priority 1), because no data is visible.

---

## Important Notes

- **"Summary results enabled"** means at least ONE of three checkboxes (Response Time, Error Rate, Throughput) is checked.
- **"Summary results disabled"** means ALL THREE checkboxes are unchecked.
- **"Per request results enabled"** means at least ONE of three checkboxes is checked.
- **"Per request results disabled"** means ALL THREE checkboxes are unchecked.
- **Priority warnings** focus on configuration conflicts or missing data.
- **Informational warnings** provide context about metric selection and usage.
- **Additional warnings** notify about completely disabled sections.
- **Disabled metrics warnings** list specific metrics that are turned off.
- **Deviation warnings** are informational and only shown when comparison data is visible.


