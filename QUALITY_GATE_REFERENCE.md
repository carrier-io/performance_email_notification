# Quality Gate Warnings & Data Display Reference

This document describes all warning messages that can appear in performance test email notifications and how data is displayed in report tables.

---

## Table of Contents
- [Overview](#overview)
- [SLA Warnings](#sla-warnings)
- [Baseline Warnings](#baseline-warnings)
- [Deviation Warnings](#deviation-warnings)
- [Warning Priority Rules](#warning-priority-rules)
- [Important Notes](#important-notes)

---

## Overview

Quality Gate provides two independent comparison features:
- **SLA (Service Level Agreement)**: Compare test results against predefined thresholds
- **Baseline**: Compare test results against a previous test run

Each warning includes:
- **Condition**: When this warning appears
- **Warning Message**: Exact text shown to user
- **Data Display**: What appears in report tables (General metrics table and Request metrics table)

**Settings:**
- **"Summary results enabled"** = at least ONE of three checkboxes (Response Time, Error Rate, Throughput) is checked
- **"Summary results disabled"** = ALL THREE checkboxes are unchecked
- **"Per request results enabled"** = at least ONE of three checkboxes is checked
- **"Per request results disabled"** = ALL THREE checkboxes are unchecked

---

## SLA Warnings

### Priority 0: SLA Disabled
**Condition:** SLA checkbox is unchecked in Quality Gate configuration, but SLA thresholds exist in the system (at least one metric: Response Time, Error Rate, or Throughput is configured).

**Warning:** "SLA comparison is disabled in Quality Gate configuration. Enable SLA to see comparison with configured thresholds."

**Data Display:**
- **General metrics table**: SLA columns hidden
- **Request metrics table**: SLA columns hidden for all rows
- Thresholds exist in system but not shown to user

**Note:** This is the highest priority warning. When SLA is disabled, no other SLA warnings are shown.

---

### Priority 1: Both Settings Disabled
**Condition:** SLA is enabled, but both "Summary results" AND "Per request results" are disabled (all 6 checkboxes are unchecked).

**Warning:** "SLA is enabled, but both 'Summary results' and 'Per request results' options are disabled in Quality Gate configuration. Enable at least one option to see SLA data."

**Data Display:**
- **General metrics table**: SLA columns hidden
- **Request metrics table**: SLA columns hidden for all rows

---

### Priority 2: No Thresholds Configured
**Condition:** SLA is enabled, but NO thresholds are configured for ANY metric (no response_time AND no error_rate AND no throughput).

**Warning:** "SLA is enabled but no thresholds are configured. Please configure SLA for at least one metric (response time, error rate, or throughput)."

**Data Display:**
- **General metrics table**: SLA columns hidden
- **Request metrics table**: SLA columns hidden for all rows

**Note:** If at least one metric has thresholds configured, this warning is NOT shown and SLA works normally for configured metrics.

---

### Priority 3b-3g (REMOVED): Metric-Specific Disabled Scenarios
**Status:** REMOVED - all cases now covered by Independent Informational Warning (see below).

**Rationale:** Priority 3b-3g checked for discrepancies between Summary and Per Request settings. This created dependency between sections and duplicated information from Independent info. Removed to allow independent processing of Summary and Per Request configurations.

**Previous Priorities:**
- 3b: Response Time disabled in Summary, enabled in Per Request
- 3c: Response Time enabled in Summary, disabled in Per Request  
- 3d: Throughput disabled in Summary, enabled in Per Request
- 3e: Throughput enabled in Summary, disabled in Per Request
- 3f: Error Rate disabled in Summary, enabled in Per Request
- 3g: Error Rate enabled in Summary, disabled in Per Request

---

### Priority 3h (REMOVED): Summary ON, Per Request OFF, Some Metrics Disabled
**Status:** REMOVED - cases now covered by Independent Informational Warning.

---

### Priority 3i (REMOVED): Summary OFF, Per Request ON, Some Metrics Disabled
**Status:** REMOVED - cases now covered by Independent Informational Warning.

---

### Priority 3j: Summary ON, Per Request OFF (All Metrics Enabled)
**Condition:** SLA is enabled, Summary results is ON with all metrics enabled, Per request results is completely OFF (all 3 checkboxes unchecked).

**Warning:** "Per request SLA is disabled. Enable 'Per request results' in Quality Gate configuration to see SLA for individual requests."

**Data Display:**
- **General metrics table**: 
  - Response Time row: SLA value shown
  - Error Rate row: SLA value shown
  - Throughput row: SLA value shown
- **Request metrics table**:
  - "All" row: SLA value shown (inherits from General metrics)
  - Individual requests: "SLA disabled" (gray, italic text)

**Note:** Can appear together with Priority 4 (metric mismatch) or Priority 5 (multiple metrics).

---

### Priority 3: Summary OFF, Per Request ON (All Metrics Enabled)
**Condition:** SLA is enabled, Summary results is completely OFF (all 3 checkboxes unchecked), Per request results is ON with all metrics enabled.

**Warning:** "General metrics SLA is disabled. Enable 'Summary results' in Quality Gate configuration to see SLA for general metrics."

**Data Display:**
- **General metrics table**: SLA columns hidden
- **Request metrics table**:
  - "All" row: "SLA disabled" (requires Summary results)
  - Individual requests: SLA values shown or "Set SLA" if not configured

**Note:** Can appear together with Priority 4 (metric mismatch) or Priority 5 (multiple metrics).

---

### Priority 4: SLA Metric Mismatch (Response Time only)
**Condition:** SLA is enabled, SLA is configured for the comparison metric, but there are issues with scope configuration.

**Warning (Case 4a1a - has "every", no "all"):** "SLA for [METRIC] uses 'Every' scope (applies to all requests by default). No general 'All' SLA is configured. Configure 'All' SLA to see aggregated metrics in General metrics table."

**Warning (Case 4a1b - has "every", no "all", some requests covered by specific SLA):** "SLA for [METRIC] uses 'Every' scope and some are configured for individual requests. No general 'All' SLA is configured. Configure 'All' SLA to see aggregated metrics in General metrics table."

**Warning (Case 4a2a - no "every", no "all", all requests covered by specific SLA):** "SLA for [METRIC] is configured for individual requests. No general 'All' SLA is configured. Configure 'All' SLA to see aggregated metrics in General metrics table."

**Warning (Case 4a2b - no "every", no "all", some requests missing SLA):** "SLA for [METRIC] is configured only for specific requests. Some requests show 'Set SLA'. Configure 'Every' SLA to cover all requests and/or 'All' SLA to see aggregated metrics."

**Warning (Case 4a3 - has "all", no "every", has specific but not all covered):** "Some requests show 'Set SLA' for [METRIC] metric. Configure SLA thresholds for individual requests in Thresholds section or use 'Every' scope to apply SLA to all requests automatically."

**Data Display:**
- SLA values shown for configured requests
- "Set SLA" for unconfigured requests
- General metrics table shows aggregated values when "all" scope is configured

**Note:** This priority handles ONLY cases where SLA exists for selected metric but scope configuration is incomplete. Case 4b (wrong metric) is handled by Informational Warning below.

---

### Priority 5: Multiple SLA Metrics
**Condition:** SLA is enabled, multiple SLA metrics are configured (e.g., PCT95, PCT50), and Per request Response Time checkbox is OFF.

**Warning:** "Multiple SLA metrics configured ([METRICS]). Report uses [SELECTED_METRIC]. To select a different metric, enable 'Per request results' in Quality Gate configuration."

**Data Display:**
- **General metrics table**: Shows SLA using selected metric (e.g., PCT95)
- **Request metrics table**: Shows SLA using selected metric
- System auto-selected highest priority metric: pct99 > pct95 > pct90 > pct50 > mean

**Note:** Informs user which metric was automatically chosen. Can appear together with Priority 3j or Priority 3.

---

### Additional Warning: Summary Results SLA Disabled
**Condition:** Summary results is completely OFF (all 3 checkboxes unchecked), "All" row in Request metrics shows "SLA disabled", AND no Priority SLA warning is shown.

**Warning:** "Summary results SLA thresholds are disabled. Enable 'Summary results' in Quality Gate configuration to see SLA thresholds for general metrics."

**Data Display:**
- **General metrics table**: SLA columns hidden
- **Request metrics table**: "All" row shows "SLA disabled"

---

### Additional Warning: Per Request SLA Disabled
**Condition:** Per request results is completely OFF (all 3 checkboxes unchecked), individual requests show "SLA disabled", AND no Priority SLA warning is shown.

**Warning:** "Per request SLA thresholds are disabled. Enable 'Per request results' in Quality Gate configuration to see SLA thresholds for individual requests."

**Data Display:**
- **General metrics table**: May show SLA if Summary enabled
- **Request metrics table**: Individual requests show "SLA disabled"

---

### Informational Warning: Disabled Metrics
**Condition:** SLA is enabled, at least one section (Summary or Per request) is enabled, and one or more metrics are disabled in Summary, Per request, or both.

**Warning Examples:**
- "Response Time SLA is disabled for both general metrics and individual requests. Enable 'Response time' in Quality Gate configuration to see SLA for response time metrics."
- "Response Time SLA is disabled for general metrics. Enable 'Response time' in Quality Gate configuration to see SLA for response time metrics."
- "Response Time SLA is disabled for individual requests. Enable 'Response time' in Quality Gate configuration to see SLA for individual request metrics."
- "Response Time SLA is disabled for general metrics. Enable 'Response time' in Quality Gate configuration to see SLA for response time metrics. Throughput SLA is disabled for general metrics. Enable 'Throughput' in Quality Gate configuration to see SLA for throughput metrics."

**Data Display:**
- **Disabled metrics**: Not shown in their respective sections
- **Enabled metrics**: Display normally with SLA values
- Each section (Summary/Per Request) processes independently

**Note:** This warning is shown in addition to Priority warnings and lists all disabled metrics with detailed SLA information. Each metric gets a complete sentence.

---

### Informational Warning: SLA Comparison Metric Info
**Condition:** SLA is enabled, Summary Response Time OR Per request Response Time is enabled (when RT data is displayed).

**Warning (Per request OFF, default metric configured):** "SLA comparison uses default metric (PCT95). To select different metric..."

**Warning (Per request OFF, default metric NOT configured):** "SLA uses default PCT95, but no PCT95 SLA is configured. SLA values will be hidden..."

**Warning (Per request OFF, no RT SLA at all):** "SLA uses default PCT95, but no Response Time SLA is configured..."

**Warning (Per request ON, selected metric NOT configured):** "SLA comparison uses PCT50, but no PCT50 SLA is configured. SLA values will be hidden..."

**Warning (Per request ON, no RT SLA at all):** "SLA comparison uses PCT50, but no Response Time SLA is configured..."

**Data Display:**
- **When metric configured**: Response time rows show SLA values
- **When metric NOT configured**: Response time rows show "N/A" or "Set SLA"
- Alerts user about which metric is being used and if it's available

**Note:** Shown only when Response Time data is visible.

---

## Baseline Warnings

### Priority 0: Baseline Disabled
**Condition:** Baseline checkbox is unchecked in Quality Gate configuration, but baseline data exists in the system.

**Warning:** "Baseline comparison is disabled in Quality Gate configuration. Enable Baseline to see comparison with previous test results."

**Data Display:**
- **General metrics table**: Baseline columns hidden
- **Request metrics table**: Baseline columns hidden for all rows
- Baseline data exists but not shown to user

**Note:** This is the highest priority warning. When Baseline is disabled, no other Baseline warnings are shown.

---

### Priority 1: Both Settings Disabled
**Condition:** Baseline is enabled, but both "Summary results" AND "Per request results" are disabled (all 6 checkboxes are unchecked).

**Warning:** "Baseline comparison is enabled, but both 'Summary results' and 'Per request results' options are disabled in Quality Gate configuration. Enable at least one option to see baseline data."

**Data Display:**
- **General metrics table**: Baseline columns hidden
- **Request metrics table**: Baseline columns hidden for all rows

---

### Priority 1b: Summary ON (Only ER/TP), Per Request OFF
**Condition:** Baseline is enabled, Summary results is ON but only Error Rate and/or Throughput are enabled (Response Time OFF), Per request results is completely OFF.

**Warning:** None (this is a valid configuration)

**Data Display:**
- **General metrics table**: 
  - Error Rate row: Baseline value shown (if ER enabled)
  - Throughput row: Baseline value shown (if TP enabled)
  - Response Time row: Not shown (RT checkbox OFF)
- **Request metrics table**: All rows show "Baseline disabled" (Per request OFF)

**Note:** Baseline works for Error Rate and Throughput without Response Time.

---

### Priority 2b-2g (REMOVED): Metric-Specific Disabled Scenarios
**Status:** REMOVED - all cases now covered by Independent Informational Warning (see below).

**Rationale:** Priority 2b-2g checked for discrepancies between Summary and Per Request settings. This created dependency between sections and duplicated information. Removed to allow independent processing.

**Previous Priorities:**
- 2b: Response Time disabled in Summary, enabled in Per Request
- 2c: Response Time enabled in Summary, disabled in Per Request
- 2d: Throughput disabled in Summary, enabled in Per Request
- 2e: Throughput enabled in Summary, disabled in Per Request
- 2f: Error Rate disabled in Summary, enabled in Per Request
- 2g: Error Rate enabled in Summary, disabled in Per Request

---

### Priority 2h (REMOVED): Summary ON, Per Request OFF, Some Metrics Disabled
**Status:** REMOVED - cases now covered by Independent Informational Warning.

---

### Priority 2i (REMOVED): Summary OFF, Per Request ON, Some Metrics Disabled
**Status:** REMOVED - cases now covered by Independent Informational Warning.

---

### Priority 3j: Summary ON, Per Request OFF (All Metrics Enabled)
**Condition:** Baseline is enabled, Summary results is ON with all metrics enabled, Per request results is completely OFF (all 3 checkboxes unchecked).

**Warning:** "Per request baseline is disabled. Enable 'Per request results' in Quality Gate configuration to see baseline for individual requests."

**Data Display:**
- **General metrics table**: 
  - Response Time row: Baseline value shown (uses default pct95)
  - Error Rate row: Baseline value shown
  - Throughput row: Baseline value shown
- **Request metrics table**:
  - "All" row: Baseline value shown (inherits from General metrics)
  - Individual requests: "Baseline disabled" (gray, italic text)

**Note:** Uses default pct95 for response time because Per request OFF means no metric selection available.

---

### Priority 3: Summary OFF, Per Request ON (All Metrics Enabled)
**Condition:** Baseline is enabled, Summary results is completely OFF (all 3 checkboxes unchecked), Per request results is ON with all metrics enabled.

**Warning:** "General metrics baseline is disabled. Enable 'Summary results' in Quality Gate configuration to see baseline for general metrics."

**Data Display:**
- **General metrics table**: Baseline columns hidden
- **Request metrics table**:
  - "All" row: "Baseline disabled" (requires Summary results)
  - Individual requests: Baseline values shown

**Note:** Can use selected comparison metric if Per request RT is enabled.

---

### Additional Warning: Summary Results Baseline Disabled
**Condition:** Summary results is completely OFF (all 3 checkboxes unchecked), "All" row in Request metrics shows "Baseline disabled", AND no Priority Baseline warning is shown.

**Warning:** "Summary results baseline comparison is disabled. Enable 'Summary results' in Quality Gate configuration to see baseline for general metrics."

**Data Display:**
- **General metrics table**: Baseline columns hidden
- **Request metrics table**: "All" row shows "Baseline disabled"

---

### Additional Warning: Per Request Baseline Disabled
**Condition:** Per request results is completely OFF (all 3 checkboxes unchecked), individual requests show "Baseline disabled", AND no Priority Baseline warning is shown.

**Warning:** "Per request baseline comparison is disabled. Enable 'Per request results' in Quality Gate configuration to see baseline for individual requests."

**Data Display:**
- **General metrics table**: May show baseline if Summary enabled
- **Request metrics table**: Individual requests show "Baseline disabled"

---

### Informational Warning: Disabled Metrics
**Condition:** Baseline is enabled, at least one section (Summary or Per request) is enabled, and one or more metrics are disabled in Summary, Per request, or both.

**Warning Examples:**
- "Response Time baseline is disabled for both general metrics and individual requests. Enable 'Response time' in Quality Gate configuration to see baseline for response time metrics."
- "Response Time baseline is disabled for general metrics. Enable 'Response time' in Quality Gate configuration to see baseline for response time metrics."
- "Response Time baseline is disabled for individual requests. Enable 'Response time' in Quality Gate configuration to see baseline for individual request metrics."
- "Response Time baseline is disabled for general metrics. Enable 'Response time' in Quality Gate configuration to see baseline for response time metrics. Throughput baseline is disabled for general metrics. Enable 'Throughput' in Quality Gate configuration to see baseline for throughput metrics."

**Data Display:**
- **Disabled metrics**: Not shown in their respective sections
- **Enabled metrics**: Display normally with baseline values
- Each section (Summary/Per Request) processes independently

**Note:** This warning is shown in addition to Priority warnings and lists all disabled metrics with detailed baseline information. Each metric gets a complete sentence.

---

### Informational Warning: Baseline Comparison Metric Info
**Condition:** Baseline is enabled, Per request results is completely OFF (all 3 checkboxes unchecked), and Summary Response Time is ON.

**Warning:** "Baseline comparison uses default PCT95. To select a different percentile, enable 'Per request results' in Quality Gate configuration."

**Data Display:**
- **General metrics table**: Response time uses default pct95
- **Request metrics table**: When enabled, response time uses default pct95

**Note:** Percentile selection requires Per request to be enabled (any metric). This warning shown only when using default metric.

---

## Deviation Warnings

### SLA Deviation Warning
**Condition:** SLA is enabled, at least one section (Summary or Per request) is enabled, and any deviation value > 0 is configured.

**Warning:** "SLA has configured acceptable deviation. Validation results take into account the allowed deviation range when comparing actual values against SLA thresholds."

**Data Display:**
- SLA validation considers deviation range
- Values within deviation range may show as passed
- No visual changes to table display

**Note:** Not shown when SLA is disabled (Priority 0) or when both Summary and Per request results are disabled (Priority 1).

---

### Baseline Deviation Warning
**Condition:** Baseline is enabled, baseline data exists, at least one section (Summary or Per request) is enabled, and any deviation value > 0 is configured.

**Warning:** "Baseline has configured acceptable deviation. Validation results take into account the allowed deviation range when comparing actual values against baseline."

**Data Display:**
- Baseline validation considers deviation range
- Values within deviation range may show as passed
- No visual changes to table display

**Note:** Not shown when Baseline is disabled (Priority 0) or when both Summary and Per request results are disabled (Priority 1).

---

## Warning Priority Rules

1. **Only ONE Priority warning is shown per feature** (SLA or Baseline). The highest priority (lowest number) warning wins.

2. **SLA and Baseline Priority warnings are independent** and can appear together (one from each category).

3. **Priority 4 and 5 use independent `if` checks** (not `elif`) allowing them to appear together with Priority 3j/3.

4. **Informational warnings appear in addition to Priority warnings** and provide supplementary information.

5. **Additional warnings are suppressed** when a Priority warning already explains the situation.

6. **Disabled metrics informational warnings are always shown** when applicable, regardless of Priority warnings.

7. **Deviation warnings are shown only when data is visible** - they are suppressed for Priority 0 (feature disabled) and Priority 1 (both sections disabled).

---

## Important Notes

### Display Messages
- `"Set SLA"` - No threshold configured for this request (gray, italic, 12px)
- `"SLA disabled"` - Per request results disabled (gray, italic, 12px)
- `"Baseline disabled"` - Per request results disabled (gray, italic, 12px)
- `"N/A"` - No baseline data or threshold not found for General metrics
- `[value]` - Actual threshold or baseline value when matched

### Section Independence
- **Summary and Per Request process independently**: Each section checks own metrics without cross-referencing
- Disabled metrics in one section don't affect the other
- "All" row is special case requiring Summary enabled

### Response Time Requirements
- **Response Time NOT required for SLA/Baseline**: Can have SLA with only Error Rate and/or Throughput
- Can have Baseline with only Error Rate and/or Throughput
- Priority 1b (Baseline) explicitly validates this as acceptable

### Metric Selection
- **Percentile selection** (pct95, pct50, etc.) requires Per request Response Time enabled
- If Per request OFF, system uses default pct95
- If Per request ON but only ER/TP enabled, still uses default pct95 for response time

### Warning Combinations
**Can appear together:**
- Priority 3j + Priority 5 (Summary ON, Per request OFF + multiple SLA metrics)
- Priority 3 + Priority 4 (Summary OFF, Per request ON + metric mismatch)
- SLA Priority 0 + Baseline Priority 0 (both features disabled)
- SLA Priority 3j + Baseline Priority 3j (both show Per request unavailable)

**Cannot appear together:**
- Priority 0 + any other priority in same feature (Priority 0 blocks all others)
- Priority 1 + Priority 3/3j in same feature (contradictory configurations)

### Table Visibility
| Summary Results | Per Request Results | General Metrics | Request Metrics "All" Row | Request Metrics Individual |
|-----------------|---------------------|-----------------|---------------------------|----------------------------|
| OFF (all 3 OFF) | OFF (all 3 OFF)     | Hidden          | Hidden                    | Hidden                     |
| ON (any 1+)     | OFF (all 3 OFF)     | Shown           | Shown                     | "SLA/Baseline disabled"    |
| ON (any 1+)     | ON (any 1+)         | Shown           | Shown                     | Shown                      |
| OFF (all 3 OFF) | ON (any 1+)         | Hidden          | "SLA/Baseline disabled"   | Shown                      |

---

*Last Updated: January 2026*
