# Deviation Logic for SLA and Baseline

This document describes how deviation is applied to SLA thresholds and Baseline values in email reports.

## Table of Contents
- [Deviation Overview](#deviation-overview)
- [Deviation Source](#deviation-source)
- [Deviation Display Format](#deviation-display-format)
- [SLA Deviation Logic](#sla-deviation-logic)
- [Baseline Deviation Logic](#baseline-deviation-logic)
- [Deviation Warnings](#deviation-warnings)
- [Important Notes](#important-notes)

---

## Deviation Overview

**What is Deviation?**
Deviation is an acceptable tolerance range configured in Quality Gate settings. It allows test results to deviate slightly from thresholds or baseline values without triggering failures.

**Key Characteristics:**
- **Universal:** One deviation value applies to ALL aggregation types (pct50, pct95, pct99)
- **Independent:** Not stored in API thresholds, only in Quality Gate configuration
- **Metric-specific:** Separate deviation values for throughput, error_rate, and response_time
- **Scope-based:** Different deviations for 'all' (summary) and 'every' (per-request) scopes

---

## Deviation Source

### Storage Location
Deviation values are stored in Quality Gate configuration:

```
quality_gate_config
└── settings
    ├── summary_results
    │   ├── throughput_deviation (req/sec)
    │   ├── error_rate_deviation (%)
    │   └── response_time_deviation (ms)
    └── per_request_results
        ├── throughput_deviation (req/sec)
        ├── error_rate_deviation (%)
        └── response_time_deviation (ms)
```

### Retrieval Logic
```python
# For General metrics ('all' scope)
config_section = settings.get('summary_results', {})
rt_deviation = config_section.get('response_time_deviation', 0)

# For Request metrics ('every' scope)
config_section = settings.get('per_request_results', {})
rt_deviation = config_section.get('response_time_deviation', 0)
```

### ⚠️ NOT from API Thresholds
API thresholds have a `deviation` field that is **always 0**. Never use this field.

```
❌ WRONG: deviation = threshold.get('deviation', 0)
✅ CORRECT: deviation = quality_gate_config['settings']['summary_results']['response_time_deviation']
```

---

## Deviation Display Format

### Display Pattern
Values are shown as **"original (with deviation)"** in both SLA and Baseline tables:

```
SLA Threshold: 1.0 (1.2)
               ↑   ↑
          original with deviation

Baseline: 0.8 (1.0)
          ↑   ↑
     original with deviation
```

### Units
- **Throughput:** req/sec
- **Error Rate:** %
- **Response Time:** seconds (ms in config, displayed as sec after ÷1000)

---

## SLA Deviation Logic

### Application Direction
Deviation is applied to make thresholds **more lenient** (harder to fail):

```
For response_time (lower is better):
├─ Comparison: >
├─ Application: threshold + deviation
└─ Effect: Allows higher values to pass
    Example: threshold=1000ms, deviation=200ms
    → Display: 1.0 (1.2) sec
    → Fail if current > 1200ms

For throughput (higher is better):
├─ Comparison: <
├─ Application: threshold - deviation
└─ Effect: Allows lower values to pass
    Example: threshold=100, deviation=10
    → Display: 100 (90) req/sec
    → Fail if current < 90

For error_rate (lower is better):
├─ Comparison: >
├─ Application: threshold + deviation
└─ Effect: Allows higher values to pass
    Example: threshold=5%, deviation=1%
    → Display: 5.0 (6.0) %
    → Fail if current > 6%
```

### Code Implementation
```python
# Get deviation from Quality Gate config
quality_gate_config = args.get('quality_gate_config', {})
settings = quality_gate_config.get('settings', {})
config_section = settings.get('summary_results', {})  # or 'per_request_results'

rt_deviation = config_section.get('response_time_deviation', 0)

# Apply deviation
threshold_original = 1000  # ms
threshold_with_deviation = threshold_original + rt_deviation  # more lenient

# Display both values
sla_original = round(threshold_original / 1000, 2)  # 1.0 sec
sla_value = round(threshold_with_deviation / 1000, 2)  # 1.2 sec
```

---

## Baseline Deviation Logic

### Application Direction
Deviation is applied to make baseline comparison **more lenient** (allows current values to be worse):

```
For response_time (lower is better):
├─ Application: baseline + deviation
├─ Effect: Allows current to be higher
└─ Color: Green if current ≤ baseline+deviation, Red otherwise
    Example: baseline=800ms, deviation=200ms
    → Display: 0.8 (1.0) sec
    → Green if current ≤ 1000ms

For throughput (higher is better):
├─ Application: baseline - deviation
├─ Effect: Allows current to be lower
└─ Color: Green if current ≥ baseline-deviation, Red otherwise
    Example: baseline=100, deviation=10
    → Display: 100 (90) req/sec
    → Green if current ≥ 90

For error_rate (lower is better):
├─ Application: baseline + deviation
├─ Effect: Allows current to be higher
└─ Color: Green if current ≤ baseline+deviation, Red otherwise
    Example: baseline=5%, deviation=1%
    → Display: 5.0 (6.0) %
    → Green if current ≤ 6%
```

### Code Implementation
```python
# Get original baseline value
baseline_rt_original = baseline_all['pct95'] / 1000  # 0.8 sec

# Get deviation from Quality Gate config
quality_gate_config = args.get('quality_gate_config', {})
settings = quality_gate_config.get('settings', {})
config_section = settings.get('summary_results', {})

rt_deviation = config_section.get('response_time_deviation', 0)

# Apply deviation (more lenient for baseline)
baseline_rt_with_dev = baseline_rt_original + (rt_deviation / 1000)

# Display both values
baseline_original = round(baseline_rt_original, 2)  # 0.8 sec
baseline_value = round(baseline_rt_with_dev, 2)  # 1.0 sec

# Color comparison uses value WITH deviation
current_rt = 0.9
baseline_color = RED if current_rt > baseline_value else GREEN
```

---

## Deviation Warnings

### When to Show
Warnings are displayed when **any** deviation > 0 in Quality Gate config.

### Warning Conditions
```python
# Check if any deviation is configured
sla_enabled = quality_gate_config.get('sla', {}).get('checked')
baseline_enabled = quality_gate_config.get('baseline', {}).get('checked')

# For SLA
if sla_enabled:
    summary_config = settings.get('summary_results', {})
    per_request_config = settings.get('per_request_results', {})
    
    tp_dev = summary_config.get('throughput_deviation', 0) or per_request_config.get('throughput_deviation', 0)
    er_dev = summary_config.get('error_rate_deviation', 0) or per_request_config.get('error_rate_deviation', 0)
    rt_dev = summary_config.get('response_time_deviation', 0) or per_request_config.get('response_time_deviation', 0)
    
    if tp_dev > 0 or er_dev > 0 or rt_dev > 0:
        show_sla_deviation_warning = True

# For Baseline
if baseline_enabled and baseline:
    # Same logic as SLA
    if tp_dev > 0 or er_dev > 0 or rt_dev > 0:
        show_baseline_deviation_warning = True
```

### Warning Text
```
SLA: "SLA has configured acceptable deviation. Validation results take 
      into account the allowed deviation range when comparing actual 
      values against SLA thresholds."

Baseline: "Baseline has configured acceptable deviation. Validation 
           results take into account the allowed deviation range when 
           comparing actual values against baseline."
```

### Display Location
- **Baseline warning:** After Test Description section, before General Metrics table
- **SLA warning:** After SLA metric warnings, before Request Metrics table

---

## Important Notes

### ✅ Deviation is Universal
One deviation value applies to **ALL aggregation types**:
```
response_time_deviation = 200ms applies to:
├─ pct50 thresholds
├─ pct95 thresholds
├─ pct99 thresholds
└─ ALL percentiles equally
```

### ✅ Deviation is Independent
Deviation exists **independently** of:
- comparison_metric (pct50/pct95/pct99)
- API thresholds (may be empty)
- Specific aggregation configurations

### ✅ Always Use Quality Gate Config
```python
# ❌ WRONG: Using API threshold (always returns 0)
deviation = threshold.get('deviation', 0)

# ❌ WRONG: Fetching unfiltered thresholds from API
all_thresholds = requests.get(f"{galloper_url}/api/v1/thresholds/...")

# ✅ CORRECT: Using Quality Gate config directly
quality_gate_config = args.get('quality_gate_config', {})
deviation = quality_gate_config['settings']['summary_results']['response_time_deviation']
```

### ✅ Scope Matters
Use correct config section based on scope:
```
'all' scope → summary_results
'every' scope → per_request_results
Specific request → per_request_results (with 'all' fallback)
```

### ⚠️ Display vs Calculation
- **Display:** Show both original and with-deviation values
- **Calculation:** Use with-deviation value for pass/fail logic
- **Color:** Determined by comparing current value against with-deviation value

---

## Example Scenario

### Configuration
```json
{
  "quality_gate_config": {
    "settings": {
      "summary_results": {
        "response_time_deviation": 200
      }
    }
  }
}
```

### SLA Threshold
```
Threshold configured: 1000ms for pct95
Current value: 1150ms
Comparison metric: pct95

Display: "1.0 (1.2) sec"
Result: PASS (1150ms ≤ 1200ms)
Color: Green
```

### Baseline Comparison
```
Baseline value: 800ms for pct95
Current value: 950ms
Comparison metric: pct95

Display: "0.8 (1.0) sec"
Result: PASS (950ms ≤ 1000ms)
Color: Green
Diff: -0.05 sec (current - baseline_with_dev)
```

### Without Deviation
```
Same scenario with deviation = 0:

SLA: "1.0 (1.0) sec" → FAIL (1150ms > 1000ms)
Baseline: "0.8 (0.8) sec" → FAIL (950ms > 800ms)
```
