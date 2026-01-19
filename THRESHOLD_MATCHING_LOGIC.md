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
├─ Priority 3: Fallback to 'all' (case-insensitive)
└─ Final: Show "Set SLA" if no threshold found
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
**Condition:** SLA checkbox unchecked in Quality Gate, but thresholds exist in system

```
Action:  All SLA columns hidden (General metrics + Request metrics)
         Thresholds exist but not displayed
Warning: "SLA is disabled in Quality Gate configuration. Enable SLA to see 
          threshold values and validation results."
```

**Note:** This is the highest priority warning. When SLA is disabled, no other SLA warnings are shown.

### Scenario 1: Settings Disabled
**Condition:** SLA enabled but both Summary and Per request results disabled

```
Action:  All SLA columns hidden (General metrics + Request metrics)
Warning: "SLA is enabled, but both 'Summary results' and 'Per request results' 
          options are disabled in Quality Gate configuration. Enable at least 
          one option to see SLA data."
```

### Scenario 2: No Response Time SLA
**Condition:** SLA enabled but no `response_time` thresholds configured

```
Action:  Keeps default pct95, SLA columns hidden
Warning: "SLA is enabled but no response time thresholds are configured. 
          Please configure SLA for response time metrics."
```

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
| OFF             | OFF                 | All SLA hidden + Warning             |
| ON              | OFF                 | General metrics only                 |
| ON              | ON                  | All metrics (per-request logic)      |
| OFF             | ON                  | Per-request logic only               |

**Note:** Even with Summary ON, General metrics SLA requires `request_name='all'` threshold configured. Same logic applies for Request metrics - requires appropriate thresholds per the matching rules.

---

## Baseline Comparison Logic

Baseline displays comparison against a previous test run using selected metric.  
**Unlike SLA:** Baseline doesn't use 'all'/'every' scopes - only percentile matters.

### General Metrics vs Baseline
**Table:** Response time row in "General metrics vs Baseline"

**Rule:** Requires "Summary results" enabled in Quality Gate

```
IF Baseline.checked AND Summary results.check_response_time:
    └─ Show baseline data for "All" request using comparison_metric

IF Baseline.checked BUT Summary results disabled:
    ├─ Hide baseline column
    └─ Show warning

Metric: Uses comparison_metric (default pct95 or user-selected)
```

---

### Request Metrics vs Baseline
**Table:** Individual requests/transactions in "Request metrics" table

**Rule:** Requires "Per request results" enabled in Quality Gate

#### When Per Request Results is DISABLED:
```
IF Baseline.checked AND NOT Per request results.check_response_time:
    ├─ Show: "Baseline disabled" (gray, italic, 12px) for individual requests
    └─ Warning Banner (triggered only when individual requests have "Baseline disabled"):
       "Per request baseline comparison is disabled. Enable 'Per request results' 
        in Quality Gate configuration to see baseline for individual requests."

Note: Warning is NOT shown if only "All" row has "Baseline disabled" 
      (e.g., when Summary OFF but Per request ON)
```

#### When Per Request Results is ENABLED:
```
Show baseline data for each request using comparison_metric

Metric: Uses comparison_metric (default pct95 or user-selected)
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

**Note:** This is the highest priority warning. When Baseline is disabled, no other Baseline warnings are shown.

| Summary Results | Per Request Results | Result                               |
|-----------------|---------------------|--------------------------------------|
| OFF             | OFF                 | All baseline hidden + Warning        |
| ON              | OFF                 | General metrics only (pct95)         |
| ON              | ON                  | All metrics (selected pct)           |
| OFF             | ON                  | Request metrics only + Warning       |

#### Case 1: Both Disabled
**Condition:** Baseline enabled, both Summary and Per request results disabled

```
Action:  All baseline columns hidden (General metrics + Request metrics)
Warning: "Baseline comparison is enabled, but both 'Summary results' and 
          'Per request results' options are disabled in Quality Gate 
          configuration. Enable at least one option to see baseline data."
```

#### Case 2: Summary ON, Per Request OFF
**Condition:** Baseline enabled, Summary ON, Per request OFF

```
Action:  General metrics baseline shown, Request metrics baseline hidden
         Individual requests show "Baseline disabled" (requires Per request results)
Warning: "Baseline comparison uses default PCT95. To select a different 
          percentile, enable 'Per request results' in Quality Gate configuration."
Note:    Individual requests in Request metrics show "Baseline disabled" because 
         Per request results is disabled
```

#### Case 3: Summary OFF, Per Request ON
**Condition:** Baseline enabled, Per request ON but Summary OFF

```
Action:  General metrics baseline hidden, Request metrics baseline shown
         "All" row shows "Baseline disabled" (requires Summary results)
Warning: "General metrics baseline is disabled. Enable 'Summary results' in 
          Quality Gate configuration to see baseline for general metrics."
Note:    "All" row in Request metrics shows "Baseline disabled" because it requires 
         Summary results to be enabled (conceptually belongs to General metrics)
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
2. No response_time thresholds configured
3. Summary OFF, Per request ON (General metrics SLA disabled)
4. SLA metric mismatch (no "all" SLA or wrong metric)
5. Multiple SLA metrics exist (when Per request OFF)

**Note:** All warnings (1-5) require SLA to be **enabled**. Priority 0 is shown only when SLA is **disabled** but thresholds exist in the system.

**Baseline Warnings (priority order):**
0. **Baseline disabled** (Baseline checkbox unchecked, but baseline data exists)
1. Settings disabled (both Summary and Per request OFF)
2. Summary ON, Per request OFF (uses default pct95)
3. Summary OFF, Per request ON (General metrics baseline disabled)

**Note:** All warnings (1-3) require Baseline to be **enabled**. Priority 0 is shown only when Baseline is **disabled** but data exists.

**Important:** Only ONE warning per feature shown (highest priority wins), but SLA and Baseline warnings can appear together.

**Additional Warnings (shown independently):**
- "Per request SLA thresholds are disabled" when:
  - Per request results is OFF AND
  - Individual requests (not "All" row) have "SLA disabled"
  - NOT shown when only "All" row has "SLA disabled" (e.g., Summary OFF + Per request ON)

- "Per request baseline comparison is disabled" when:
  - Per request results is OFF AND
  - Individual requests (not "All" row) have "Baseline disabled"
  - NOT shown when only "All" row has "Baseline disabled" (e.g., Summary OFF + Per request ON)

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
