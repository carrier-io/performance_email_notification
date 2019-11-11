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

`'smpt_user': '<smpt_user_who_will_send_email>'` - required for all type of notifications

`'smpt_password': '<password>'` - required for all type of notifications

`'user_list': '<list of recipients>'` - required for all type of notifications

`'notification_type': '<test_type>'` - should be 'ui' or 'api'


`'smpt_host': 'smtp.gmail.com'` - optional, default - 'smtp.gmail.com'
 
`'smpt_port': 465` - optional, default - 465
 
`'influx_port': 8086` - optional, default - 8086

`'influx_thresholds_database': 'thresholds'` - optional, default - 'thresholds'

`'influx_ui_tests_database': 'perfui'` - optional, default - 'perfui'

`'influx_comparison_database': 'comparison'` - optional, default - 'comparison'

`'influx_user': ''` - optional, default - ''

`'influx_password': ''` - optional, default - ''

`'test_limit': 5` - optional, default - 5

`'comparison_metric': 'pct95'` - optional, only for api notifications, default - 'pct95'
 