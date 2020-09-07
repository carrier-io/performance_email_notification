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

from os import environ
from email_notifications import EmailNotification
import json


def lambda_handler(event, context):
    try:
        args = parse_args(event)

        # Check required params
        if not all([args['influx_host'], args['smtp_user'], args['test'], args['test_type'],
                    args['notification_type'], args['smtp_password'], args['user_list']]):
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

    # Influx Config
    args['influx_host'] = environ.get("influx_host") if not event.get('influx_host') else event.get('influx_host')
    args['influx_port'] = event.get("influx_port", 8086)
    args['influx_user'] = event.get("influx_user", "")
    args['influx_password'] = event.get("influx_password", "")

    # Influx DBs
    # TODO: Deprecate influx_thresholds_database influx_comparison_database and influx_ui_tests_database
    args['influx_thresholds_database'] = event.get("influx_thresholds_database", "thresholds")
    args['influx_comparison_database'] = event.get("influx_comparison_database", "comparison")
    args['comparison_db'] = event.get("influx_comparison_database", event.get("comparison_db", "comparison"))
    args['thresholds_db'] = event.get("influx_thresholds_database", event.get("thresholds_db", "thresholds"))
    args['influx_db'] = event.get("influx_db")

    # SMTP Config
    args['smtp_port'] = environ.get("smtp_port", 465) if not event.get('smtp_port') else event.get('smtp_port')
    args['smtp_host'] = environ.get("smtp_host", "smtp.gmail.com") if not event.get('smtp_host') else event.get('smtp_host')
    args['smtp_user'] = environ.get('smtp_user') if not event.get('smtp_user') else event.get('smtp_user')
    args['smtp_sender'] = args['smtp_user'] if not environ.get('smtp_sender') else environ.get('smtp_sender')
    if not event.get('smtp_password'):
        args['smtp_password'] = environ.get("smtp_password")
    else:
        args['smtp_password'] = event.get('smtp_password')

    # Test Config
    args['users'] = event.get('users', 1)
    args['test'] = event.get('test')
    args['simulation'] = event.get('test')

    # Notification Config
    args['user_list'] = event.get('user_list')
    args['test_limit'] = event.get("test_limit", 5)
    args['comparison_metric'] = event.get("comparison_metric", 'pct95')
    if not event.get('notification_type'):
        args['notification_type'] = environ.get('notification_type')
    else:
        args['notification_type'] = event.get('notification_type')
    if args['notification_type'] == 'ui':
        args['test_type'] = event.get('test_suite')
    if args['notification_type'] == 'api':
        args['test_type'] = event.get('test_type')
    args['type'] = args['test_type']

    return args
