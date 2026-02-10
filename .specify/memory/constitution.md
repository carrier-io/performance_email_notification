<!--
Sync Impact Report - Constitution v2.0.0
=========================================
Version change: 1.0.0 → 2.0.0
Updated: 2026-02-10
Modified principles: Complete rewrite focused on actual workflows
- Removed: Generic principles (Data Integrity, Backward Compatibility, etc.)
- Added: Workflow-specific principles (Results Post-Processing, Chart Quality, etc.)
- Reorganized: Focused on email notification development workflow
Added sections:
- Results Processing Pipeline (new major focus)
- Chart Generation & Visual Consistency (new)
- API vs UI Notification Parity (new)
- Code Quality & Maintainability (new)
Removed sections: None (reorganized into new structure)
Templates requiring updates:
  ✅ .specify/templates/plan-template.md (updated Constitution Check with all 8 principles)
  ✅ .specify/templates/spec-template.md (added email notification guidance)
  ✅ .specify/templates/tasks-template.md (updated compliance checklist with all sections)
  ✅ AGENTS.md (updated with v2.0.0 principles summary)
Follow-up TODOs: None - all templates synchronized
-->

# Performance Email Notification Constitution

**Project Mission**: Generate accurate, actionable HTML email reports for API (backend) and UI (frontend) performance test results, enabling teams to quickly identify performance regressions and threshold violations.

## Core Principles

### I. Results Post-Processing Accuracy (NON-NEGOTIABLE)

The results processing pipeline (Galloper/InfluxDB → DataManager → ReportBuilder → Email) is the core business logic. All threshold matching, baseline comparison, deviation calculation, and quality gate evaluation MUST:

- Produce mathematically correct results traceable to source data
- Follow documented logic in `THRESHOLD_MATCHING_LOGIC.md`, `DEVIATION_LOGIC.md`, `QUALITY_GATE_REFERENCE.md`
- Handle edge cases explicitly (missing data, zero values, threshold boundaries, disabled SLA scenarios)
- Preserve calculation context for debugging (include intermediate values when reporting violations)
- Be validated by automated tests covering all documented scenarios

**Specific Rules:**
- General metrics MUST use ONLY lowercase 'all' threshold (strict match)
- Individual request metrics follow documented fallback chain (per-request → 'all' → no threshold)
- Baseline comparison respects Summary/Per-request results settings independently
- Metric selection follows hierarchy: User-specified → Single SLA → Highest SLA → Default pct95
- When calculations change, update documentation BEFORE code

**Rationale:** Users make critical go/no-go decisions based on these reports. Incorrect threshold matching or baseline comparisons lead to wrong conclusions about performance. The complex logic requires strict adherence to documented rules to maintain correctness.

### II. Code Quality & Maintainability

This codebase processes complex performance data and generates visual reports. Code MUST be readable, maintainable, and avoid unnecessary complexity:

- **Method Size**: Keep methods under 100 lines; extract complex logic into named helper methods
- **Cyclomatic Complexity**: Limit to 10 decision points per method; use early returns and guard clauses
- **Magic Numbers**: Extract constants to module-level (e.g., `GREEN = '#028003'`) and consolidate duplicates
- **DRY (Don't Repeat Yourself)**: Shared logic between API and UI flows goes into base classes or utilities
- **Naming**: Use descriptive names that reveal intent (`calculate_baseline_deviation` not `calc_bd`)
- **Comments**: Explain *why* for non-obvious logic, not *what* (code should be self-documenting)

**Specific Anti-Patterns to Avoid:**
- Duplicating color constants across multiple files (`report_builder.py`, `api_email_notification.py`, `chart_generator.py`)
- Deeply nested conditionals (flatten with guard clauses or strategy pattern)
- Large data transformation methods doing fetching + processing + formatting (separate concerns)
- Copy-paste code between API and UI notification classes (extract shared behavior)

**Rationale:** Complex threshold and baseline logic is inherently difficult. Poor code quality compounds this difficulty, making bugs hard to find and changes risky. Maintainability enables confident modification of calculation rules.

### III. Chart Generation & Visual Consistency

Charts (`matplotlib` via `chart_generator.py`) are critical for understanding performance trends. Charts MUST be consistent, professional, and informative:

- **Consistent Styling**: Use centralized color palette (SUCCESS_GREEN, WARNING_YELLOW, ERROR_RED, NEUTRAL_GRAY)
- **Readable Fonts**: Minimum 14pt font size; axis labels and legends must be legible when embedded in email
- **Data Integrity**: Chart data MUST match table data exactly (no rounding discrepancies)
- **Accessibility**: Color alone insufficient; use patterns/shapes for colorblind accessibility when practical
- **Format**: Generate at appropriate DPI (300 for bar charts, 72 for line charts) to balance quality and file size
- **Error Handling**: When chart generation fails, email MUST still send with placeholder or error message

**Chart Types:**
- **Line charts** (`alerts_linechart`): Trend over time, max 20 data points to maintain readability
- **Bar charts** (`barchart`): Comparison across requests, color-coded by status (green=improved, red=degraded, yellow=warning)
- **UI comparison line charts** (`ui_comparison_linechart`): Dual-axis charts for baseline comparison

**Rationale:** Charts provide immediate visual insight that tables cannot. Inconsistent or misleading charts undermine report credibility. Users scan charts first; tables second.

### IV. Email Template Development & Cross-Client Compatibility

Email templates (Jinja2 HTML in `templates/`) render on diverse clients (Gmail, Outlook, Slack). Templates MUST:

- **HTML Compatibility**: Use table-based layouts (not flexbox/grid); inline styles (not external CSS)
- **Context Synchronization**: Every `{{ t_params.variable }}` MUST have corresponding data in ReportBuilder/UIEmailNotification
- **Graceful Degradation**: Handle missing optional data with Jinja2 defaults (`{{ t_params.value | default('N/A') }}`)
- **Visual Consistency**: Maintain color scheme, typography, spacing across `backend_email_template.html` and `ui_email_template.html`
- **Debug Sections**: Keep debug blocks (quality gate config, threshold processing, baseline calculation) for troubleshooting production issues
- **Test Rendering**: Validate template changes with sample data in multiple email clients before merging

**Template Structure:**
- **Header**: Branding, report type, test identification
- **Summary Section**: High-level status, key metrics, pass/fail determination
- **Charts**: Embedded inline images (MIME attachments)
- **Metrics Tables**: General metrics (summary) + Request metrics (detailed)
- **Warnings Section**: Quality gate warnings, SLA/baseline info messages (from `QUALITY_GATE_REFERENCE.md`)
- **Debug Sections**: Conditional rendering of troubleshooting data (enabled via args)

**Rationale:** Email clients have strict rendering constraints. Broken templates frustrate users who rely on timely performance feedback. Debug sections enable production troubleshooting without code access.

### V. API vs UI Notification Feature Parity

This system supports two notification types (API for backend tests, UI for frontend tests). Both flows MUST maintain feature parity unless explicitly documented otherwise:

- **Common Features**: Both support baseline comparison, threshold matching, quality gates, chart embedding
- **Divergence Points**: Document differences in `AGENTS.md` (e.g., `smtp_password` format, test identification parameters)
- **Parallel Development**: When adding features to one notification type, evaluate applicability to the other
- **Shared Code**: Extract common logic to base classes or utilities (`ReportBuilder` methods, `chart_generator` functions)
- **Testing**: Verify both notification types after changes to shared code (`lambda_function.py`, `data_manager.py`, `chart_generator.py`)

**Current Known Differences** (from `AGENTS.md`):
- API uses `test_type` parameter; UI uses `test_id` + `report_id`
- UI expects `smtp_password` as dict `{"value": "..."}` (API uses string)
- Threshold fetching differs (API thresholds via parameters, UI thresholds via Galloper API)

**Rationale:** Users expect consistent reporting experience across test types. Feature drift between API and UI notifications creates confusion and maintenance burden.

### VI. Results Presentation Clarity

Email recipients range from engineers to product managers. Reports MUST be understandable without deep performance testing knowledge:

- **Status Indicators**: Use color + emoji + text (✅ success, ❌ failed, not just color alone)
- **Warning Messages**: Follow patterns in `QUALITY_GATE_REFERENCE.md` - explain what's wrong AND how to fix it
- **Metric Labels**: Use human-readable names ("Response Time (95th percentile)" not "pct95")
- **Contextual Help**: Include baseline comparison context ("10% slower than baseline #42")
- **Actionable Summaries**: Lead with decision-relevant info (pass/fail, violations count, affected requests)
- **Progressive Disclosure**: Summary first, then general metrics, then detailed per-request breakdown

**Warning Message Requirements** (from `QUALITY_GATE_REFERENCE.md`):
- **Condition**: When this warning appears
- **Message**: Exact user-facing text explaining the issue
- **Action**: What user should do (enable setting, configure threshold, etc.)
- **Data Display**: What appears in tables (hidden columns, N/A values, etc.)

**Rationale:** Performance reports inform critical decisions but not all stakeholders are performance experts. Clear presentation enables faster triage and reduces support burden.

### VII. Backward Compatibility for Event Contracts

The Lambda event schema (`lambda_function.parse_args`) is a public API consumed by Galloper and automation. Changes MUST maintain backward compatibility:

- **Required Parameters**: Never remove or rename required parameters without major version bump and migration path
- **Optional Parameters**: New parameters MUST be optional with sensible defaults
- **Type Changes**: Parameter type changes are BREAKING (string → dict for `smtp_password` was a violation)
- **Validation**: Tighten validation only with minor version bump and clear error messages
- **Deprecation**: Announce deprecated parameters 2 releases before removal; support both old and new during transition
- **Documentation**: Update README.md parameter list when adding/modifying parameters

**Critical Event Contract Parameters:**
- `notification_type`: 'api' or 'ui' (required, routing decision)
- `smtp_*`: Email transport config (required)
- `galloper_url`, `token`, `project_id`: Data source authentication (required)
- `test`, `users`, `env`: Test identification (required for API)
- `test_id`, `report_id`: Test identification (required for UI)

**Rationale:** Breaking event contracts cause silent failures in production pipelines. Galloper invocations expect stable interfaces. Backward compatibility enables gradual rollout.

### VIII. Error Handling & Debugging Support

Lambda failures in production are debugged via CloudWatch logs. Errors MUST provide actionable context:

- **Missing Parameters**: Specify which parameters, their expected type/format, and example values
- **API Failures**: Include URL, status code, response body snippet (mask sensitive data)
- **Calculation Errors**: Include input values that caused the error (thresholds, metrics, configuration)
- **SMTP Failures**: Include SMTP host, port, authentication status (mask password)
- **Structured Logging**: Use consistent format `[COMPONENT] ACTION: details` (e.g., `[DataManager] Fetching baseline: url=...`)
- **Debug Mode**: Support debug parameters that enable verbose logging and embed debug sections in templates

**Error Message Template:**
```
[Component] Error: <brief description>
Context: <what was being attempted>
Input: <relevant input values, masked if sensitive>
Expected: <what should have happened>
Action: <what user should check or fix>
```

**Rationale:** Lambda failures are investigated remotely via logs. Cryptic errors slow incident response and frustrate users. Good error messages enable self-service debugging.

## Quality Standards

### Code Organization
- **Separation of Concerns**: Data fetching (`data_manager.py`), report building (`report_builder.py`), rendering (`templates/`), transport (`email_client.py`)
- **Chart Generation**: Isolated in `chart_generator.py` with reusable functions
- **Event Parsing**: Centralized in `lambda_function.py` (single source of truth)
- **Business Logic**: Never in templates (use Python for calculations, templates for presentation only)

### Testing Strategy
- **Unit Tests**: All calculation methods (threshold matching, baseline deviation, quality gate evaluation)
- **Integration Tests**: End-to-end notification flows (API and UI paths)
- **Edge Cases**: Missing data, zero values, threshold boundaries, SLA disabled scenarios
- **Smoke Tests**: Email rendering with sample data (verify no template errors)
- **Regression Tests**: Capture known calculation bugs as test cases before fixing

### Documentation Requirements
- **Logic Documentation**: Complex algorithms in dedicated .md files (`THRESHOLD_MATCHING_LOGIC.md`, etc.)
- **Agent Guidance**: Keep `AGENTS.md` current with code structure, event contracts, common pitfalls
- **Warning Reference**: Maintain `QUALITY_GATE_REFERENCE.md` with all warning messages and conditions
- **README**: Document all event parameters, their types, defaults, and whether required/optional
- **Code Comments**: Explain *why* for non-obvious logic; link to documentation for complex workflows

## Development Workflow

### Template Changes
1. Read template context structure in `ReportBuilder` or `UIEmailNotification`
2. Make template modifications with proper Jinja2 syntax
3. Test rendering with sample data covering edge cases (missing values, disabled features, etc.)
4. Verify rendering in multiple email clients (Gmail web, Outlook, Slack)
5. Update both API and UI templates if feature applies to both
6. Update template context provider if new variables needed

### Calculation Logic Changes
1. Read existing documentation (`THRESHOLD_MATCHING_LOGIC.md`, `DEVIATION_LOGIC.md`, etc.)
2. Write or update documentation with new logic BEFORE coding
3. Write failing tests covering new behavior and edge cases
4. Implement logic changes
5. Verify tests pass and check for unintended side effects
6. Update both API and UI flows if logic is shared
7. Add debug output to templates for troubleshooting

### Event Contract Changes
1. Check if change is backward compatible (optional parameter vs required parameter change)
2. If breaking: plan migration path, update major version, document in README
3. Update `lambda_function.parse_args` with new parameter handling
4. Add validation with clear error messages
5. Update README.md parameter documentation
6. Update `AGENTS.md` event contract section
7. Test with old and new parameter formats (if maintaining compatibility)

### Code Review Checklist
- [ ] Calculation logic matches documentation
- [ ] Tests cover edge cases (missing data, zero values, boundaries)
- [ ] Both API and UI flows updated if shared code changed
- [ ] Error messages are actionable and include context
- [ ] Template-context alignment verified
- [ ] Event contract changes are backward compatible or documented as breaking
- [ ] Color constants use centralized definitions (no duplication)
- [ ] Methods under 100 lines with clear single responsibility
- [ ] README/AGENTS.md updated if public interfaces changed

## Governance

### Amendment Process
1. Propose constitution changes via pull request with clear rationale
2. Update this file with new version number (semantic versioning below)
3. Identify affected templates (.specify/templates/) and update Constitution Check sections
4. Update AGENTS.md reference if principle names or count changed
5. Document migration impact for any removed or significantly changed principles

### Versioning Policy
- **MAJOR**: Principle removals, complete rewrites, changes that invalidate existing compliance checks
- **MINOR**: New principles added, significant expansions to existing principles
- **PATCH**: Clarifications, examples, typo fixes, formatting improvements

### Compliance Verification
- **PRs touching calculation logic**: MUST reference documentation updates and include tests
- **PRs changing event contract**: MUST document backward compatibility impact in PR description
- **PRs modifying templates**: MUST include rendering verification (screenshots or test output)
- **PRs affecting both API and UI**: MUST test both notification flows end-to-end
- **PRs with debug output**: Should add corresponding template debug sections for production troubleshooting

**Version**: 2.0.0 | **Ratified**: 2026-02-10 | **Last Amended**: 2026-02-10
