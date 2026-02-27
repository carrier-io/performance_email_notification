# Status Parsing and Failed Transactions Logic for UI Notifications

This document describes the full lifecycle of `result.status` — from how it is assigned in the **observer-lighthouse-nodejs** container, through Galloper storage, to how it drives filtering and rendering in the UI email report — and how Failed Transactions are collected from the artifact log file and displayed separately.

## Table of Contents
- [Report-Level Status (summary)](#report-level-status-summary)
- [Upstream Origin of `result.status` (observer-lighthouse-nodejs)](#upstream-origin-of-resultstatus-observer-lighthouse-nodejs)
- [Row-Level Status (`result.status`)](#row-level-status-resultstatus)
- [Template Usage of Status](#template-usage-of-status)
  - [Row-level status: Results Overview tables](#row-level-status-results-overview-tables)
- [Failed Transactions Overview](#failed-transactions-overview)
- [Failed Transactions Data Source](#failed-transactions-data-source)
- [Log File Parsing Logic](#log-file-parsing-logic)
  - [Pattern 1 — `_Failed` suffix](#pattern-1--_failed-suffix)
  - [Pattern 2 — `Status detected: FAILED for`](#pattern-2--status-detected-failed-for)
  - [Error message association](#error-message-association)
- [Template Usage of Failed Transactions](#template-usage-of-failed-transactions)
- [Relationship Between Status and Failed Transactions](#relationship-between-status-and-failed-transactions)
- [Important Notes](#important-notes)

---

## Report-Level Status (summary)

`t_params.status` is sourced from `report_info["test_status"]["status"]` (Galloper API) and can be overridden to `"Failed"` by quality gate logic (`missed_threshold_rate`, `baseline_deviation`). It controls the email badge color, subject emoji, failed reasons list, and the Failed LCP/INP SLA sections in the template.

---

## Upstream Origin of `result.status` (observer-lighthouse-nodejs)

Before `result.status` ever reaches Galloper or this notification service, it is determined inside the **observer-lighthouse-nodejs** container that executes Lighthouse tests. Understanding this helps explain why certain values appear and what they mean.

### Detection logic

Status is assigned by inspecting the **next step** in the Lighthouse JSON test sequence:

```python
status = "undefined"  # default for every step

if index + 1 < len(json_data["steps"]):
    next_step = json_data["steps"][index + 1]
    if next_step["lhr"]["gatherMode"] == "snapshot":
        next_name = next_step.get("name", "").upper()

        if next_name.endswith("_SUCCESS"):
            status = "SUCCESS"
        elif next_name.endswith("_FAILED"):
            status = "FAILED"
```

### Key rules
1. **Default** — every step starts as `"undefined"` unless a qualifying next step exists.
2. **Convention** — the next step must be a Lighthouse snapshot (`gatherMode == "snapshot"`) whose name ends with `_SUCCESS` or `_FAILED` (case-insensitive match via `.upper()`).
3. **Look-ahead only** — the status of a step is derived from the step that immediately follows it, not from the step itself.

### Example test structure
```json
{ "name": "login_page",         "lhr": { "gatherMode": "navigation" } },
{ "name": "login_page_SUCCESS", "lhr": { "gatherMode": "snapshot" } }
```
The `login_page` step receives `status = "SUCCESS"` because the next step's name ends with `_SUCCESS`.

### Stored status values
| Value | Meaning |
|---|---|
| `SUCCESS` | Step completed successfully |
| `FAILED` | Step encountered a failure |
| `undefined` | No qualifying snapshot step followed — status unknown |

These values are written to the CSV summary and then stored in Galloper. The notification service reads them back via `/ui_performance/results/...`.

---

## Row-Level Status (`result.status`)

`result.status` is a field on each entry returned by the Galloper results API. It originates in observer-lighthouse-nodejs (see section above) and is **never modified** by the Python code — it flows straight into the Jinja2 template.

Possible values (set by observer-lighthouse-nodejs, stored in Galloper): `'SUCCESS'`, `'FAILED'`, `'undefined'`.

`result.status == "FAILED"` (uppercase) is used in two filtering places in Python before template rendering:

```python
# In _build_comparison_data — exclude FAILED rows from trend chart data
filtered_pages  = [p for p in test["pages"]   if p.get("status") != "FAILED"]
filtered_actions = [a for a in test["actions"] if a.get("status") != "FAILED"]

# In _process_baseline_comparison — exclude FAILED rows from baseline calc
filtered_baseline_info = [r for r in baseline_info  if r.get("status") != "FAILED"]
filtered_results_info  = [r for r in results_info   if r.get("status") != "FAILED"]

# In _calculate_p75_metrics — exclude FAILED rows from p75 summary calc
if result.get("status") == "FAILED":
    continue
```

So FAILED rows are still passed to the template (they appear in Results Overview with ❌), but they are excluded from all computed aggregations:

- **Trend chart data** (`_build_comparison_data`) — builds the last-5-runs comparison tables and the chart datapoints for TTFB/TBT/LCP (pages) and CLS/TBT/INP (actions). FAILED rows are stripped before p75 is calculated, so a failed page load doesn't drag down or distort the trend line.

- **Baseline comparison** (`_process_baseline_comparison`) — computes per-identifier p75 aggregations for both the current run and the baseline run, then diffs them to produce `degradation_rate`. FAILED rows are excluded from both sides so that a failed step doesn't inflate the perceived regression.

- **p75 summary metrics** (`_calculate_p75_metrics`) — computes the report-level LCP p75 and INP p75 used in the Execution Summary banner (`performance_summary`). FAILED rows are skipped so the headline numbers reflect only successful measurements.

---

## Template Usage of Status

### Row-level status: Results Overview tables

Location: Pages Results Overview and Actions Results Overview tables [`ui_email_template.html` lines ~230, ~264]

```html
<td>
    {% if result.status == 'SUCCESS' %}✅
    {% elif result.status == 'FAILED' %}❌
    {% else %}—
    {% endif %}
</td>
```

This renders per-row only, independent of the overall report status. A green-badge passing email can have ❌ rows in the results table.

---

## Failed Transactions Overview

**What is it?**
A separate failure signal sourced from the raw test execution **log file** stored in Galloper artifacts — not from the UI performance results API. It captures Lighthouse test runner transaction failures logged by observer-lighthouse-nodejs, regardless of what the UI metrics show.

**Key difference from SLA / baseline failures:**
- SLA failures (`failed_pages_lcp`, `failed_actions_inp`) come from Galloper's metrics API and are only rendered when `t_params.status == 'Failed'`
- Failed transactions come from a raw log artifact and are rendered **unconditionally** whenever the list is non-empty

---

## Failed Transactions Data Source

**API endpoint:**
```
GET /api/v1/artifacts/artifact/{project_id}/{bucket}/{uid}.log
```

**Bucket name derivation:**
```python
bucket = report_info['name'].replace(' ', '').replace('_', '').lower()
```

**Failure handling:**
The entire download-and-parse block is wrapped in `try/except`. Any failure (404, network error, parse error) results in `log_failed_transactions = []` and a `[LOG DOWNLOAD] Error:` print. The email always sends.

---

## Log File Parsing Logic

`_parse_log_file(log_content: bytes)` scans the decoded log line by line looking for two patterns that register a transaction failure, and one pattern that associates an error message.

### Pattern 1 — `_Failed` suffix

Matches any line whose last whitespace-separated token ends with `_Failed`:

```
2026-02-20 11:47:53    [2026-02-20T11:47:44] MyTransaction_Failed
                                              ↑ token[-7:] == '_Failed'
```

```python
if line.endswith('_Failed'):
    token = line.split()[-1]        # "MyTransaction_Failed"
    name  = token[:-len('_Failed')] # "MyTransaction"
    if name not in seen_transactions:
        seen_transactions.add(name)
        failed_transactions.append(name)
```

### Pattern 2 — `Status detected: FAILED for`

```
Status detected: FAILED for MyTransaction
```

```python
if 'Status detected: FAILED for ' in line:
    name = line.split('Status detected: FAILED for ', 1)[1].strip()
    if name not in seen_transactions:
        seen_transactions.add(name)
        failed_transactions.append(name)
```

Both patterns use a `seen_transactions` set for deduplication — the same transaction name is only appended once regardless of how many lines match it.

### Error message association

`[ERROR]` lines are scanned separately to build an `errors_by_transaction` lookup. The transaction name is extracted from the trailing ` on page <name>` suffix:

```
2026-02-20 11:47:53    [2026-02-20T11:47:44] [ERROR] Element not found on page MyTransaction
```

```python
if '[ERROR]' in line:
    # Strip timestamp prefix
    cleaned = re.sub(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s+\[...\]\s+', '', line)
    if ' on page ' in cleaned:
        msg_part, trans_name = cleaned.rsplit(' on page ', 1)
        errors_by_transaction[trans_name.strip()] = msg_part.strip()
```

**Final output:**
```python
result = [
    {'name': name, 'error': errors_by_transaction.get(name, '')}
    for name in failed_transactions
]
return {'failed_transactions': result}
```

`error` is an empty string `''` when no matching `[ERROR]` line was found for that transaction name.

---

## Template Usage of Failed Transactions

Location: Below Failed LCP/INP SLA sections [`ui_email_template.html` line ~143]

```html
{% if log_failed_transactions and log_failed_transactions|length > 0 %}
<div style="margin-top: 24px;">
    <p>Failed Transactions:</p>
    <ul>
    {% for item in log_failed_transactions %}
        <li>
            ✗ {{ item.name }}
            {% if item.error %}
                <span style="font-family: monospace; font-size: 12px; color: #525F7F;">
                    ({{ item.error }})
                </span>
            {% endif %}
        </li>
    {% endfor %}
    </ul>
</div>
{% endif %}
```

**No `t_params.status` guard** — this section renders on any email (passing, failing, or Finished) as long as `log_failed_transactions` is non-empty.

---

## Relationship Between Status and Failed Transactions

```
observer-lighthouse-nodejs
  └─ sets result.status per step ──► stored in Galloper ──► result.status
                                                               • Shown in Results Overview tables (✅/❌/—)
                                                               • Excluded from aggregations when FAILED

Galloper test_status.status ──► t_params.status ──► Controls:
                                                       • Status badge color/text
                                                       • Failed reasons list
                                                       • Failed LCP SLA list
                                                       • Failed INP SLA list
                                                       • Email subject emoji

Artifact log file (observer-lighthouse-nodejs output)
  └─────────────────────────► log_failed_transactions ──► Controls:
                                                              • "Failed Transactions:" section only
                                                              (always shown if non-empty)
```

---

## Important Notes

### ✅ `result.status` case sensitivity
Row-level status comparisons in Python use uppercase `"FAILED"`, but the template checks for `'FAILED'` (same) and `'SUCCESS'` (same). Values are set as uppercase strings by observer-lighthouse-nodejs (`SUCCESS`, `FAILED`, `undefined`) and stored that way in Galloper. A lowercase `"failed"` would not be filtered out by the Python exclusion logic and would render `—` (not ❌) in the template.

### ✅ Failed Transactions are always shown
Unlike `failed_pages_lcp` and `failed_actions_inp`, the Failed Transactions section has no wrapping `{% if t_params.status == 'Failed' %}` guard. This is intentional — log failures are an independent signal from a different data source.

### ✅ Log download is best-effort
If the artifact log file does not exist (test never wrote one, bucket name mismatch, network error), the exception is caught, `log_failed_transactions` stays `[]`, and the section is simply absent from the email. This never blocks sending.

### ⚠️ Bucket name derivation may mismatch
```python
bucket = report_info['name'].replace(' ', '').replace('_', '').lower()
```
Only spaces and underscores are removed. Other special characters (hyphens, dots, etc.) in the test name are preserved. The artifact must have been stored under exactly the same bucket name for the download to succeed.

### ⚠️ `reasons_to_fail_report` only populated by quality gates
If Galloper itself marks a test as `Failed`, `t_params.status` will be `"Failed"` and the red badge will show, but `reasons_to_fail_report` will be `[]` — so the "Failed reasons:" list will **not** render. The list only appears when a quality gate explicitly added a reason string.
