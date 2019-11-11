# Copyright 2019 getcarrier.io

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from email_notifications import EmailNotification
import json


def lambda_handler(event, context):
    try:
        args = parse_args(event)

        # Check required params
        if not all([args['influx_host'], args['smpt_user'], args['test'], args['test_type'],
                    args['notification_type'], args['smpt_password'], args['user_list']]):
            raise Exception('Some required parameters not passed')

        # Send notification
        if args['notification_type'] == 'api':
            EmailNotification(args).email_notification()
        elif args['notification_type'] == 'ui':
            EmailNotification(args).ui_email_notification()
        else:
            raise Exception('Incorrect value for notification_type: {}. Must be api or ui'
                            .format(args['notification_type']))
    except Exception as e:
        from traceback import format_exc
        print(format_exc())
        return {
            'statusCode': 500,
            'body': json.dumps(str(e))
        }
    return {
        'statusCode': 200,
        'body': json.dumps('Email has been sent')
    }


def parse_args(_event):
    args = {}

    # Galloper or AWS Lambda service
    event = _event if not _event.get('body') else json.loads(_event['body'])

    # Optional params
    args['influx_port'] = event.get("influx_port", 8086)
    args['smpt_port'] = event.get("smpt_port", 465)
    args['smpt_host'] = event.get("smpt_host", "smtp.gmail.com")
    args['influx_thresholds_database'] = event.get("influx_thresholds_database", "thresholds")
    args['influx_thresholds_database'] = event.get("influx_thresholds_database", "thresholds")
    args['influx_ui_tests_database'] = event.get("influx_ui_tests_database", "perfui")
    args['influx_comparison_database'] = event.get("influx_comparison_database", "comparison")
    args['influx_user'] = event.get("influx_user", "")
    args['influx_password'] = event.get("influx_password", "")
    args['test_limit'] = event.get("test_limit", 5)
    args['comparison_metric'] = event.get("comparison_metric", 'pct95')
    args['users'] = event.get('users', 1)

    # Required params
    args['influx_host'] = event.get('influx_host')
    args['smpt_user'] = event.get('smpt_user')
    args['smpt_password'] = event.get('smpt_password')
    args['user_list'] = event.get('user_list')
    args['notification_type'] = event.get('notification_type')
    args['test'] = event.get('test')

    if args['notification_type'] == 'ui':
        args['test_type'] = event.get('test_suite')
    if args['notification_type'] == 'api':
        args['test_type'] = event.get('test_type')

    return args
