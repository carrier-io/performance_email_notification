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

import json
from os import environ
from email_client import EmailClient
from email_notifications import ApiEmailNotification
from ui_email_notification import UIEmailNotification
from time import sleep


def lambda_handler(event, context):
    try:
        args = parse_args(event)
        print(args)
        if not args['notification_type']:
            raise Exception('notification_type parameter is not passed')

        # Send notification
        if args['notification_type'] == 'api':
            # Check required params
            if not all([args['influx_host'], args['smtp_user'], args['test'], args['test_type'],
                        args['notification_type'], args['smtp_password'], args['user_list']]):
                raise Exception('Some required parameters not passed')

            email = ApiEmailNotification(args).email_notification()
        elif args['notification_type'] == 'ui':
            if not all([args['test_id'], args['report_id']]):
                raise Exception('test_id and report_id are required for UI reports')

            email = UIEmailNotification(args).ui_email_notification()
        else:
            raise Exception('Incorrect value for notification_type: {}. Must be api or ui'
                            .format(args['notification_type']))

        EmailClient(args).send_email(email)

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

    # Galloper
    args['galloper_url'] = environ.get("galloper_url") if not event.get('galloper_url') else event.get('galloper_url')
    args['token'] = environ.get("token") if not event.get('token') else event.get('token')
    args['project_id'] = environ.get("project_id") if not event.get('project_id') else event.get('project_id')

    # Influx Config
    args['influx_host'] = environ.get("influx_host") if not event.get('influx_host') else event.get('influx_host')
    args['influx_port'] = event.get("influx_port", 8086)
    args['influx_user'] = event.get("influx_user", "")
    args['influx_password'] = event.get("influx_password", "")

    # Influx DBs
    args['comparison_db'] = event.get("comparison_db")
    args['influx_db'] = event.get("influx_db")

    # SMTP Config
    args['smtp_port'] = environ.get("smtp_port", 465) if not event.get('smtp_port') else event.get('smtp_port')
    args['smtp_host'] = environ.get("smtp_host", "smtp.gmail.com") if not event.get('smtp_host') else event.get(
        'smtp_host')
    args['smtp_user'] = environ.get('smtp_user') if not event.get('smtp_user') else event.get('smtp_user')
    args['smtp_sender'] = args['smtp_user'] if not event.get('smtp_sender') else event.get('smtp_sender')
    if not event.get('smtp_password').get("value"):
        args['smtp_password'] = environ.get("smtp_password")
    else:
        args['smtp_password'] = event.get('smtp_password')["value"]

    # Test Config
    args['users'] = event.get('users', 1)
    args['test'] = event.get('test')
    args['simulation'] = event.get('test')
    args['env'] = event.get('env')

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

    # Thresholds
    args['error_rate'] = int(environ.get("error_rate", 10)) if not event.get('error_rate') else event.get('error_rate')
    args['performance_degradation_rate'] = int(environ.get("performance_degradation_rate", 20)) \
        if not event.get('performance_degradation_rate') else event.get('performance_degradation_rate')
    args['missed_thresholds'] = int(environ.get("missed_thresholds", 50)) \
        if not event.get('missed_thresholds') else event.get('missed_thresholds')

    # ui data
    args['test_id'] = event.get('test_id')
    args['report_id'] = event.get('report_id')

    return args
