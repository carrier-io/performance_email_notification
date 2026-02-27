# email notifications
Lambda function that provide email notifications

To run the lambda function, you need to create a task in the Galloper and specify a lambda handler in it.

`lambda_function.email_lambda_handler` - handler for API tests notifications

`lambda_function.ui_email_lambda_handler` - handler for UI tests notifications

You can use curl to invoke a task, example below

```
curl -XPOST -H "Content-Type: application/json"
    -d '{"param1": "value1", "param2": "value2", ...}' <host>:5000/task/<task_id>
```

`<host>` - Galloper host DNS or IP

`<task_id>` - ID of the created task in Galloper

You can pass the necessary parameters with the -d option. List of available parameters:

`'test': '<ui_scenario_name>'` - required for ui email notifications

`'test_suite': '<ui_suite_name>'` - required for ui email notifications

`'test': '<simulation_name>'` - required for api email notifications

`'test_type': '<test_type>'` - required for api email notifications

`'users': '<count_of_vUsers>'` - required for all type of notifications

`'influx_host': '<influx_host_DNS_or_IP>'` - required for all type of notifications

`'smpt_user': '<smpt_user_who_will_login_to_the_the_host>'` - required for all type of notifications - note: parameter name `smpt` instead of `smtp`

`'smpt_password': '<password>'` - required for all type of notifications - note: parameter name `smpt` instead of `smtp`

`'smpt_sender': '<sender_who_email_will_be_FROM>'` - optional: if not included then 'smpt_user' will be used - note: parameter name `smpt` instead of `smtp`

`'user_list': '<list of recipients>'` - required for all type of notifications

`'notification_type': '<test_type>'` - should be 'ui' or 'api'

`'smpt_host': 'smtp.gmail.com'` - optional, default - 'smtp.gmail.com' - note: parameter name `smpt` instead of `smtp`

`'smpt_port': 465` - optional, default - 465 - note: parameter name `smpt` instead of `smtp`

`'influx_port': 8086` - optional, default - 8086

`'influx_thresholds_database': 'thresholds'` - optional, default - 'thresholds'

`'influx_ui_tests_database': 'perfui'` - optional, default - 'perfui'

`'influx_comparison_database': 'comparison'` - optional, default - 'comparison'

`'influx_user': ''` - optional, default - ''

`'influx_password': ''` - optional, default - ''

`'test_limit': 5` - optional, default - 5

`'comparison_metric': 'pct95'` - optional, only for api notifications, default - 'pct95'

---

## AI-Powered Performance Analysis (Backend Notifications)

Backend (API) email notifications support AI-powered performance analysis using Azure OpenAI. When enabled, emails include an "AI Analysis" section with automated insights based on test results and SLA thresholds.

### Features

- **Key Findings**: 3-5 bullet points highlighting critical performance issues
- **Performance Observations**: Markdown table with problematic transactions/requests
- **Actionable Items**: 3-5 numbered, data-specific recommendations

### AI Analysis Parameters

All AI parameters are **optional** and backward-compatible. Emails send successfully even if AI analysis fails (graceful degradation).

`'enable_ai_analysis': true/false` - **optional**, default: `false` - Enable AI-powered analysis section

`'ai_provider': 'azure_openai'` - **optional**, default: `'azure_openai'` - AI provider type (currently only Azure OpenAI supported)

`'azure_openai_api_key': '<your-api-key>'` - **required if AI enabled** - Azure OpenAI API key for authentication

`'azure_openai_endpoint': 'https://your-resource.openai.azure.com/'` - **required if AI enabled** - Azure OpenAI endpoint URL

`'azure_openai_api_version': '2024-02-15-preview'` - **optional**, default: `'2024-02-15-preview'` - API version

`'ai_model': 'gpt-4o'` - **optional**, default: `'gpt-4o'` - Model deployment name (must match Azure deployment)

`'ai_temperature': 0.0` - **optional**, default: `0.0` - Temperature for LLM output (0.0 = deterministic, 2.0 = creative)

### Example Usage

```bash
curl -XPOST -H "Content-Type: application/json" -d '{
  "test": "checkout_flow_test",
  "test_type": "backend",
  "notification_type": "api",
  "enable_ai_analysis": true,
  "azure_openai_api_key": "sk-...",
  "azure_openai_endpoint": "https://my-resource.openai.azure.com/",
  "ai_model": "gpt-4o",
  "influx_host": "influxdb.example.com",
  "smtp_user": "notifications@example.com",
  "smtp_password": "password",
  "user_list": "team@example.com"
}' <host>:5000/task/<task_id>
```

### Graceful Degradation

If AI analysis fails (invalid credentials, timeout, API errors), the email **will still send successfully** without the AI Analysis section. This ensures core reporting functionality is never blocked by AI service issues.

### Requirements

- Azure OpenAI resource with GPT-4o model deployment
- API key with appropriate permissions
- Lambda timeout configured to at least 120 seconds (AI generation adds ~10s per email)

### Provider Extensibility

The implementation uses provider abstraction to support future AI providers (OpenAI, Anthropic Claude, etc.) without code changes. See `specs/002-backend-ai-analysis/quickstart.md` for details on adding new providers.

