# Working With performance_email_notification

This repo provides an AWS Lambda-style entrypoint that generates and sends
HTML performance test email notifications for API (backend) and UI tests using
data from a Galloper instance.

**Development Principles**: See `.specify/memory/constitution.md` (v2.0.0) for core principles:
1. Results Post-Processing Accuracy (threshold matching, baseline comparison, quality gates)
2. Code Quality & Maintainability (DRY, method size, complexity limits)
3. Chart Generation & Visual Consistency (centralized colors, data integrity)
4. Email Template Development & Cross-Client Compatibility (Jinja2, HTML tables, debug sections)
5. API vs UI Notification Feature Parity (maintain consistency or document divergence)
6. Results Presentation Clarity (human-readable, actionable warnings)
7. Backward Compatibility for Event Contracts (no breaking changes without migration)
8. Error Handling & Debugging Support (actionable errors, structured logging)

## Quick map
- Entrypoint: `lambda_function.py` (`lambda_handler`)
- API notifications: `api_email_notification.py` -> `report_builder.py`
- UI notifications: `ui_email_notification.py` -> `thresholds_comparison.py`
- Email transport: `email_client.py`
- Charts: `chart_generator.py`
- Templates: `templates/backend_email_template.html`, `templates/ui_email_template.html`
- Docs for logic: `THRESHOLD_MATCHING_LOGIC.md`, `DEVIATION_LOGIC.md`
- Tests: `tests/test_lamda.py` (typo in filename, but runnable with pytest)

## Execution flow (Lambda)
1. `lambda_function.lambda_handler(event, context)` parses the event into `args`.
2. `notification_type` decides the flow:
   - `api`: builds backend report and charts, then sends email.
   - `ui`: builds UI report and charts, then sends email.
3. `email_client.EmailClient.send_email` sends per-recipient emails via SMTP.

## Event/args contract (important)
The Lambda expects a JSON payload (direct event or `{"body": "...json..."}`).

Common keys used by `lambda_function.py`:
- `notification_type`: `api` or `ui`
- `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `smtp_sender`
- `user_list`: list of recipients (supports Slack-style `<mailto:...|...>` format)
- `galloper_url`, `token`, `project_id`
- `users`, `test`, `env`, `test_limit`, `comparison_metric`

API-specific keys:
- `test_type` (e.g., load, stress)
- `quality_gate_config` (baseline/SLA logic)
- `performance_degradation_rate`, `missed_threshold_rate`
- `reasons_to_fail_report` (fallback for comparison metric parsing)

UI-specific keys:
- `test_id`, `report_id`
- `test_suite` (mapped into `test_type`)
- `smtp_password` is expected to be a dict for UI: `{"value": "..."}`

Note: README mentions `smpt_*` keys, but the code uses `smtp_*` keys. Align new
payloads with code unless you plan to update the parser.

### AI Analysis Parameters (Backend Only)

Backend (API) notifications support optional AI-powered performance analysis. **All parameters are optional and backward-compatible.**

AI-specific keys (backend only):
- `enable_ai_analysis`: `true`/`false` (default: `false`) - Enable AI analysis section
- `ai_provider`: `'azure_openai'` (default) - AI provider type
- `azure_openai_api_key`: Azure OpenAI API key (required if AI enabled)
- `azure_openai_endpoint`: Azure resource URL (required if AI enabled)
- `azure_openai_api_version`: API version (default: `'2024-02-15-preview'`)
- `ai_model`: Model deployment name (default: `'gpt-4o'`)
- `ai_temperature`: Temperature setting (default: `0.0`)

**Graceful Degradation**: If AI analysis fails (invalid credentials, timeout, API errors), the email sends successfully without the AI Analysis section. Core reporting functionality is never blocked by AI service issues.

**Constitution Compliance (Principle V - API vs UI Feature Parity)**:

This feature intentionally creates **API vs UI divergence** as part of a phased rollout strategy:

- **Backend (API) notifications**: Include AI Analysis section when `enable_ai_analysis=true`
- **UI notifications**: Do not support AI analysis (not implemented in this iteration)

**Justification**: Phased rollout allows validation of AI analysis on backend notifications before expanding to UI. Backend notifications have more structured performance data (transaction-level metrics, SLA thresholds) making them better suited for initial AI analysis implementation.

**Future Work**: UI notifications may receive AI analysis in a future iteration after backend validation is complete.

## Dependencies and runtime
- Python dependencies in `requirements.txt`
  - `perfreporter` (from GitHub) provides `DataManager` for Galloper data.
- Charts are rendered with `matplotlib` using `Agg` backend (headless).

## Templates and rendering
- Email bodies are Jinja2 templates in `templates/`.
- API path uses `ReportBuilder.create_api_email_body` to assemble the context
  and charts, then renders `templates/backend_email_template.html`.
- UI path uses `UIEmailNotification` to render `templates/ui_email_template.html`.
- Charts are saved to disk and attached as inline images (MIME).

## Threshold and baseline logic
- API thresholds/baseline matching is documented in `THRESHOLD_MATCHING_LOGIC.md`
  and `DEVIATION_LOGIC.md`.
- UI thresholds are fetched via Galloper API in `thresholds_comparison.py`.
- Metric selection for API comparisons can auto-adjust based on SLA settings;
  see `ReportBuilder.create_api_email_body`.

## Common pitfalls to check when debugging
- SMTP config: `smtp_password` type differs between API and UI flows.
- Event shapes: API expects `test_type`, UI expects `test_id` + `report_id`.
- README vs code param names: `smpt_*` in README is outdated.
- Galloper auth: `galloper_url`, `token`, `project_id` must be valid.
- Comparison metric: auto-detected from `quality_gate_config` when missing.

## Local dev tips
- Quick call to the handler:
  ```python
  from lambda_function import lambda_handler
  lambda_handler({"notification_type": "ui", "test_id": "...", "report_id": 123}, {})
  ```
- Run tests:
  ```bash
  pytest -q
  ```

## When adding features
- Keep event parsing in `lambda_function.py` the single source of truth.
- Update README if you change payload names or required fields.
- Adjust templates and `ReportBuilder`/`UIEmailNotification` together so
  context keys stay in sync.
