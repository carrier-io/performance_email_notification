# SLA Threshold & Baseline Matching Logic

This document describes the complete logic for SLA threshold and baseline matching in API performance email reports.

## Table of Contents
- [Test Status Logic](#test-status-logic)
- [SLA Threshold Matching](#sla-threshold-matching)
  - [General Metrics vs SLA](#general-metrics-vs-sla)
  - [Request Metrics - All Row](#request-metrics---all-row)
  - [Request Metrics - Individual Requests](#request-metrics---individual-requests)
  - [SLA Configuration Example](#sla-configuration-example)
- [Comparison Metric Selection](#comparison-metric-selection)
- [Baseline Comparison Logic](#baseline-comparison-logic)
  - [General Metrics vs Baseline](#general-metrics-vs-baseline)
  - [Request Metrics vs Baseline](#request-metrics-vs-baseline)
  - [Baseline Configuration Cases](#baseline-configuration-cases)

---

## Test Status Logic

The test status displayed in "Execution Summary" depends on enabled quality gate checks:

### Status: FINISHED (Gray)
**Condition:** All quality gate checks disabled

```
Checks:
├─ error_rate = -1 (disabled)
├─ performance_degradation_rate = -1 (disabled)
└─ missed_thresholds = -1 (disabled)

Result: Test completed without quality validation
Display: Gray badge, no SLA/Baseline metrics shown
```

### Status: SUCCESS (Green)
**Condition:** At least one check enabled, all passed

```
Possible checks:
├─ error_rate < threshold
├─ performance_degradation_rate < threshold (Baseline)
└─ missed_thresholds < threshold (SLA)

Result: Test passed all enabled quality checks
Display: Green badge, metrics shown for enabled checks
```

### Status: FAILED (Red)
**Condition:** At least one check enabled, at least one failed

```
Failed if ANY:
├─ error_rate ≥ threshold
├─ performance_degradation_rate ≥ threshold (Baseline)
└─ missed_thresholds ≥ threshold (SLA)

Result: Test failed one or more quality checks
Display: Red badge, failed reasons listed
```

**Important:** Status reflects quality gate validation, not test execution. Even if test runs successfully, status can be FAILED if quality thresholds are not met.

---

## Quality Gate Settings

### Summary Results and Per Request Results

Both **Summary Results** and **Per Request Results** have three independent checkboxes:
- `check_response_time`: Enable/disable response time validation
- `check_error_rate`: Enable/disable error rate validation  
- `check_throughput`: Enable/disable throughput validation

**Enabled Logic:**
- **Summary Results** is considered **enabled** if ANY of the three checkboxes is checked
- **Per Request Results** is considered **enabled** if ANY of the three checkboxes is checked
- If ALL three checkboxes are unchecked, the setting is considered **disabled**

**Impact:**
- Summary Results controls visibility of **General metrics** tables (baseline & SLA)
- Per Request Results controls visibility of **individual requests** data in Request metrics table
- Both settings affect which warnings are displayed

**Metric Selection for Response Time:**
- Percentile selection (pct95, pct50, pct99, etc.) is only available when `check_response_time` is enabled in Per Request Results
- If only `check_error_rate` or `check_throughput` are enabled, response time uses default pct95
- This is independent of whether Per Request Results is considered "enabled"

---

## SLA Threshold Matching

### General Metrics vs SLA
**Table:** Response time row in "General metrics vs SLA"

**Rule:** ONLY use threshold with `request_name='all'` (lowercase, strict match)

```
Match Criteria:
├─ request_name = 'all' (exact, lowercase)
├─ target = 'response_time'
└─ aggregation = comparison_metric

Fallback: None (show N/A if no match)

Excludes:
├─ 'All' (capital) - This is per-request aggregation
├─ 'every' - Per-request default
└─ Specific request names
```

---

### Request Metrics - All Row
**Table:** "All" row in "Request metrics" table

**Rule:** ONLY use threshold with `request_name='all'` (lowercase, strict match)

```
Match Criteria:
├─ request_name = 'all' (exact, lowercase)
├─ target = 'response_time'
└─ aggregation = comparison_metric

Fallback: None (show N/A if no match)

Excludes:
├─ 'All' (capital)
└─ 'every'
```

**Important:** Backend may send 'All' (capital) which represents per-request metrics aggregated using 'every' scope, NOT the general 'all' scope.

---

### Request Metrics - Individual Requests
**Table:** Individual requests/transactions in "Request metrics" table

**Rule:** Check Per request results setting first, then apply fallback chain

#### When Per Request Results is DISABLED:
```
IF SLA.checked AND NOT Per request results.check_response_time:
    ├─ Show: "SLA disabled" (gray, italic, 12px) for individual requests
    └─ Warning Banner (triggered only when individual requests have "SLA disabled"):
       "Per request SLA thresholds are disabled. Enable 'Per request results' 
        in Quality Gate configuration to see SLA thresholds for individual requests."

Note: Warning is NOT shown if only "All" row has "SLA disabled" 
      (e.g., when Summary OFF but Per request ON)
```

#### When Per Request Results is ENABLED:
```
Fallback Chain (in order):
├─ Priority 1: Exact match by request_name
├─ Priority 2: Fallback to 'every' (case-insensitive)
└─ Final: Show "Set SLA" if no threshold found

Note: 'all' scope is NOT used as fallback for individual requests.
      'all' is exclusively for aggregated metrics (General metrics table 
      and "All" row in Request metrics table).
```

---

### SLA Configuration Example

| Scope        | Metric | Usage                                      |
|--------------|--------|--------------------------------------------|
| all          | pct50  | General metrics + All row (for pct50)      |
| all          | pct95  | General metrics + All row (for pct95)      |
| every        | pct50  | Individual requests fallback (for pct50)   |
| every        | pct95  | Individual requests fallback (for pct95)   |
| <req_name>   | pct50  | Specific request (for pct50)               |
| <req_name>   | pct95  | Specific request (for pct95)               |

---

## Comparison Metric Selection

### Scenario 0: SLA Disabled
**Condition:** SLA checkbox unchecked in Quality Gate, but thresholds exist in system (at least one metric: Response Time, Error Rate, or Throughput is configured)

```
Action:  All SLA columns hidden (General metrics + Request metrics)
         Thresholds exist but not displayed
Warning: "SLA comparison is disabled in Quality Gate configuration. Enable SLA 
          to see comparison with configured thresholds."
```

**Note:** This is the highest priority warning. When SLA is disabled, no other SLA warnings are shown. The system checks if at least one SLA metric exists (not all three `sla_no_*` flags are true), regardless of whether Quality Gate is enabled or disabled.

### Scenario 1: Settings Disabled
**Condition:** SLA enabled but both Summary and Per request results disabled

```
Action:  All SLA columns hidden (General metrics + Request metrics)
Warning: "SLA is enabled, but both 'Summary results' and 'Per request results' 
          options are disabled in Quality Gate configuration. Enable at least 
          one option to see SLA data."
```

### Scenario 2: No SLA Thresholds Configured
**Condition:** SLA enabled but NO thresholds configured at all (no response_time, no error_rate, no throughput)

```
Action:  All SLA columns hidden (no data to display)
Warning: "SLA is enabled but no thresholds are configured. Please configure 
          SLA for at least one metric (response time, error rate, or throughput)."
```

**Note:** If ANY metric has thresholds configured (e.g., only error_rate and throughput), no warning is shown and SLA works normally for those metrics. Response time is NOT required - you can have SLA with only error_rate and/or throughput.

### Scenario 3: Summary OFF, Per Request ON
**Condition:** SLA enabled, Per request ON but Summary OFF

```
Action:  General metrics SLA hidden, Request metrics SLA shown
         "All" row shows "SLA disabled" (requires Summary results)
Warning: "General metrics SLA is disabled. Enable 'Summary results' in Quality 
          Gate configuration to see SLA for general metrics."
Note:    "All" row in Request metrics shows "SLA disabled" because it requires 
         Summary results to be enabled (conceptually belongs to General metrics)
```

### Scenario 4: Single SLA Metric
**Condition:** SLA with single metric (e.g., pct50), Per request results disabled

```
Action:  Auto-switches to pct50 (single SLA metric)
Warning: None
```

### Scenario 5: Multiple SLA Metrics
**Condition:** SLA with multiple metrics, Per request results disabled

```
Action:  Uses pct95 (or highest available: pct99 > pct95 > pct90 > pct50 > mean)
Warning: "Multiple SLA metrics configured (PCT95, PCT50). Report uses PCT95. 
          To select a different metric, enable 'Per request results' in Quality 
          Gate configuration."
```

### Scenario 6: Metric Mismatch
**Condition:** SLA configured for pct95, user selected pct50 via Per request results

```
Action:  Uses pct50 (user selection takes priority)
Warning: "SLA configured for PCT95, but report uses PCT50. SLA columns hidden."
```

### Metric Selection Priority
1. User selection via `quality_gate_config.baseline.rt_baseline_comparison_metric`
2. Single SLA metric (auto-switch if default pct95 not in SLA)
3. Highest available SLA metric (when multiple exist and Per request disabled)
4. Default: pct95

### SLA Configuration Cases

| Summary Results | Per Request Results | Result                               |
|-----------------|---------------------|--------------------------------------|
| OFF (all 3 OFF) | OFF (all 3 OFF)     | All SLA hidden + Warning             |
| ON (any 1 ON)   | OFF (all 3 OFF)     | General metrics only                 |
| ON (any 1 ON)   | ON (any 1 ON)       | All metrics (per-request logic)      |
| OFF (all 3 OFF) | ON (any 1 ON)       | Per-request logic only + Warning     |

**Note:** 
- "ON" means at least one of three metrics (response_time, error_rate, throughput) is enabled
- "OFF" means all three metrics are disabled
- Even with Summary ON, General metrics SLA requires `request_name='all'` threshold configured
- Same logic applies for Request metrics - requires appropriate thresholds per the matching rules

---

## Baseline Comparison Logic

Baseline displays comparison against a previous test run using selected metric.  
**Unlike SLA:** Baseline doesn't use 'all'/'every' scopes - only percentile matters.

### General Metrics vs Baseline
**Table:** Response time, Error rate, and Throughput rows in "General metrics vs Baseline"

**Rule:** Requires "Summary results" enabled in Quality Gate

```
IF Baseline.checked AND Summary results enabled (any metric):
    └─ Show baseline data for "All" request
    ├─ Response time: uses comparison_metric (default pct95 or user-selected)
    ├─ Error rate: percentage
    └─ Throughput: requests per second

IF Baseline.checked BUT Summary results disabled (all three metrics OFF):
    ├─ Hide baseline column
    └─ Show warning

Summary results enabled = check_response_time OR check_error_rate OR check_throughput
```

---

### Request Metrics vs Baseline
**Table:** Individual requests/transactions in "Request metrics" table

**Rule:** Requires "Per request results" enabled in Quality Gate

#### When Per Request Results is DISABLED:
```
IF Baseline.checked AND NOT Per request results enabled (all three metrics OFF):
    ├─ Show: "Baseline disabled" (gray, italic, 12px) for individual requests
    └─ Warning Banner (triggered only when individual requests have "Baseline disabled"):
       "Per request baseline comparison is disabled. Enable 'Per request results' 
        in Quality Gate configuration to see baseline for individual requests."

Note: Warning is NOT shown if only "All" row has "Baseline disabled" 
      (e.g., when Summary OFF but Per request ON)

Per request results enabled = check_response_time OR check_error_rate OR check_throughput
```

#### When Per Request Results is ENABLED:
```
Show baseline data for each request

Metric: Response time uses comparison_metric (default pct95 or user-selected)
        Error rate and Throughput use their standard calculations
```

---

### Baseline Configuration Cases

#### Scenario 0: Baseline Disabled
**Condition:** Baseline checkbox unchecked in Quality Gate, but baseline data exists

```
Action:  All Baseline columns hidden (General metrics + Request metrics)
         Baseline data exists but not displayed
Warning: "Baseline comparison is disabled in Quality Gate configuration. 
          Enable Baseline to see comparison with previous test results."
```

**Note:** This is the highest priority warning. When Baseline is disabled, no other Baseline warnings are shown. The system checks if baseline data exists, regardless of whether Quality Gate is enabled or disabled.

| Summary Results | Per Request Results | Result                               |
|-----------------|---------------------|--------------------------------------|
| OFF (all 3 OFF) | OFF (all 3 OFF)     | All baseline hidden + Warning        |
| ON (any 1 ON)   | OFF (all 3 OFF)     | General metrics only (pct95)         |
| ON (any 1 ON)   | ON (any 1 ON)       | All metrics (selected pct*)          |
| OFF (all 3 OFF) | ON (any 1 ON)       | Request metrics only + Warning       |

**Note:**
- "ON" means at least one of three metrics (response_time, error_rate, throughput) is enabled
- "OFF" means all three metrics are disabled
- *Percentile selection requires `check_response_time` enabled in Per Request Results
- If only error_rate or throughput enabled, response time defaults to pct95

#### Case 1: Both Disabled
**Condition:** Baseline enabled, both Summary and Per request results disabled (all 6 checkboxes OFF)

```
Action:  All baseline columns hidden (General metrics + Request metrics)
Warning: "Baseline comparison is enabled, but both 'Summary results' and 
          'Per request results' options are disabled in Quality Gate 
          configuration. Enable at least one option to see baseline data."

Note: This occurs when ALL three metrics are disabled in BOTH Summary results 
      AND Per request results (total 6 checkboxes all unchecked)
```

#### Case 1b: Summary ON (only ER/TP), Per Request OFF
**Condition:** Baseline enabled, Summary ON (only error_rate or throughput), Per request OFF (all 3 OFF)

```
Action:  General metrics baseline shown for enabled metrics (ER/TP only)
         Request metrics baseline hidden (Per request OFF)
         Response time NOT shown in General metrics (RT checkbox OFF)
Warning: None (this is a valid configuration)

Note: This is a valid use case - baseline comparison works for error_rate and 
      throughput without response_time. No warning is shown because the feature 
      is working as expected for the enabled metrics.
```

#### Case 2: Summary ON (all 3 metrics), Per Request OFF
**Condition:** Baseline enabled, Summary ON (all three metrics), Per request OFF (all 3 OFF)

```
Action:  General metrics baseline shown for all three metrics
         Request metrics baseline hidden (Per request OFF)
Warning: "Per request results Baseline is disabled in Quality Gate settings. 
          Enable this option to see per-request baseline comparisons."

Note: Response time is required for per-request baseline. The warning 
      specifically checks that Summary has response_time enabled AND Per request 
      has response_time enabled. If Summary RT is OFF, no warning is shown.
```

#### Case 3: Summary OFF, Per Request ON
**Condition:** Baseline enabled, Per request ON (any metric), Summary OFF (all 3 metrics OFF)

```
Action:  General metrics baseline hidden, Request metrics baseline shown
         "All" row shows "Baseline disabled" (requires Summary results)
Warning: "General metrics baseline is disabled. Enable 'Summary results' in 
          Quality Gate configuration to see baseline for general metrics."

Note: "All" row in Request metrics shows "Baseline disabled" because all three 
      metrics are disabled in Summary results. The "All" row conceptually belongs 
      to General metrics and requires Summary results to be enabled (at least one 
      of the three metrics).
```

---

## Important Notes

### 1. Independent Operation
**SLA and Baseline work independently:**
- Both can be enabled simultaneously
- Both can show warnings simultaneously
- Each has its own warning chain with priority order
- Settings (Summary/Per request results) affect both features the same way

### 2. Warning Priority
**SLA Warnings (priority order):**
0. **SLA disabled** (SLA checkbox unchecked, but thresholds exist)
1. Settings disabled (both Summary and Per request OFF)
2. No thresholds configured (no response_time AND no error_rate AND no throughput)
3b-3g. REMOVED (now covered by Independent Informational Warning)
3h. REMOVED (now covered by Independent Informational Warning)
3i. REMOVED (now covered by Independent Informational Warning)
3j. Summary ON, Per request OFF, all metrics enabled (Per request SLA disabled)
3. Summary OFF, Per request ON, all metrics enabled (General metrics SLA disabled)
4. SLA metric mismatch (no "all" SLA or wrong metric) - only shown when not caused by intentionally disabled RT checkbox
5. Multiple SLA metrics exist (when Per request OFF)

**Note:** All warnings (1-5) require SLA to be **enabled**. Priority 0 is shown only when SLA is **disabled** but thresholds exist in the system. Priority 2 is shown only when ALL three metrics are missing - if at least one metric (RT, ER, or TP) has thresholds, SLA works normally for that metric. Priority 3b-3i removed - metric-specific disabled scenarios now handled by Independent Informational Warning with detailed, independent processing of Summary and Per Request configurations.

**Baseline Warnings (priority order):**
0. **Baseline disabled** (Baseline checkbox unchecked, but baseline data exists)
1. Settings disabled (both Summary and Per request OFF)
1b. Summary ON (only ER/TP), Per request OFF - valid configuration, no warning
2b-2g. REMOVED (now covered by Independent Informational Warning)
2h. REMOVED (now covered by Independent Informational Warning)
2i. REMOVED (now covered by Independent Informational Warning)
3j. Summary ON, Per request OFF, all metrics enabled (Per request baseline disabled)
3. Summary OFF, Per request ON, all metrics enabled (General metrics baseline disabled)

**Note:** All warnings (1-3) require Baseline to be **enabled**. Priority 0 is shown only when Baseline is **disabled** but data exists. Priority 2b-2i removed - metric-specific disabled scenarios now handled by Independent Informational Warning with detailed, independent processing of Summary and Per Request configurations.

**Informational Warnings (shown in addition to Priority warnings):**
- **Baseline Info**: "Baseline comparison uses default PCT95..." - shown when **Per request is completely OFF** (all checkboxes OFF) and **Summary RT is ON**. Note: Percentile selection requires Per request enabled (any metric), but this info only shown when using default.
- **SLA Info**: Shows information about comparison metric usage and validates if selected metric has SLA configured. **Shown if Summary RT OR Per Request RT is enabled** (when RT data is displayed). Note: Comparison metric selection requires Per request enabled (any metric), but this warning validates the chosen metric regardless of which checkbox enabled it.
  - **Check priority:**
    1. First checks if specific comparison_metric (e.g., PCT50) exists in thresholds
    2. Then checks if ANY Response Time SLA exists (checked BEFORE filtering by comparison_metric to avoid false negatives)
    3. Shows most specific message based on findings
  - **Technical note:** The check for "ANY Response Time SLA exists" is performed on unfiltered thresholds before they are filtered by comparison_metric. This ensures that if you have PCT95 SLA but select PCT50, the system correctly reports "no PCT50 SLA configured" instead of "no Response Time SLA configured".
  - **Per request OFF** (default metric usage):
    - If default metric IS configured: "SLA comparison uses default metric (PCT95). To select different metric..."
    - If default metric NOT configured but other RT SLA exists: "SLA uses default PCT95, but no PCT95 SLA is configured. SLA values will be hidden..."
    - If no Response Time SLA at all: "SLA uses default PCT95, but no Response Time SLA is configured..."
  - **Per request ON** (user-selected metric):
    - If selected metric NOT configured but other RT SLA exists: "SLA comparison uses PCT50, but no PCT50 SLA is configured. SLA values will be hidden..."
    - If no Response Time SLA at all: "SLA comparison uses PCT50, but no Response Time SLA is configured..."
    - If selected metric IS configured: no warning (only shown when Per request OFF)

**Important:** Only ONE Priority warning per feature shown (highest priority wins), but SLA and Baseline Priority warnings can appear together. Informational warnings appear in addition to Priority warnings.

**Additional Warnings (shown independently):**
- "Summary results SLA thresholds are disabled" when:
  - Summary results is OFF (all 3 checkboxes OFF) AND
  - "All" row has "SLA disabled" AND
  - No Priority SLA warning is already shown

- "Per request SLA thresholds are disabled" when:
  - Per request results is OFF (all 3 checkboxes OFF) AND
  - Individual requests (not "All" row) have "SLA disabled" AND
  - No Priority SLA warning is already shown (e.g., Priority 3c for RT disabled in Per Request)
  - NOT shown when only "All" row has "SLA disabled" (e.g., Summary OFF + Per request ON)

- "Summary results baseline comparison is disabled" when:
  - Summary results is OFF (all 3 checkboxes OFF) AND
  - "All" row has "Baseline disabled" AND
  - No Priority Baseline warning is already shown

- "Per request baseline comparison is disabled" when:
  - Per request results is OFF (all 3 checkboxes OFF) AND
  - Individual requests (not "All" row) have "Baseline disabled" AND
  - No Priority Baseline warning is already shown (e.g., Priority 2c for RT disabled in Per Request)
  - NOT shown when only "All" row has "Baseline disabled" (e.g., Summary OFF + Per request ON)

**Note:** Additional warnings are suppressed when a more specific Priority warning already explains the situation. This prevents duplicate or redundant notifications. "Baseline disabled"/"SLA disabled" are shown only when the entire section is disabled (all 3 checkboxes OFF), not when individual metrics are disabled. Summary warnings (`has_disabled_summary_*`) and Per request warnings (`has_disabled_*`) are separate and can appear together if both sections are completely disabled.

### 3. Case Sensitivity
'all' (lowercase) and 'All' (capital) are different:
- `'all'` = General SLA scope
- `'All'` = Backend artifact (per-request aggregation)

### 4. Metric Control
Baseline metric selection is controlled by Per request results setting. When disabled, always uses default pct95 regardless of desired metric.

### 5. Column Visibility
- Columns hide automatically when no data available
- When both Summary and Per request results disabled, both SLA and Baseline columns hide
- Settings control visibility independently for each feature

### 6. Display Messages
- `"Set SLA"` - No threshold configured
- `"SLA disabled"` - Per request results disabled
- `"N/A"` - No baseline data or threshold not found
- Gray, italic, 12px - Style for "Set SLA" and "SLA disabled"

---

*Last Updated: December 2025*
