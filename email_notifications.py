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

from perfreporter.data_manager import DataManager

from report_builder import ReportBuilder


class Email(object):

    def __init__(self, test_name, subject, users_to, email_body, charts, date):
        self.test_name = test_name
        self.subject = subject
        self.email_body = email_body
        self.charts = charts
        self.date = date
        self.users_to = users_to


class ApiEmailNotification:
    def __init__(self, arguments):
        self.args = arguments
        self.data_manager = DataManager(arguments, arguments["galloper_url"], arguments["token"],
                                        arguments["project_id"])
        self.report_builder = ReportBuilder()

    def email_notification(self):
        tests_data, last_test_data, baseline, violation, compare_with_thresholds = self.data_manager.get_api_test_info()
        email_body, charts, date = self.report_builder.create_api_email_body(self.args, tests_data, last_test_data,
                                                                             baseline,
                                                                             self.args['comparison_metric'],
                                                                             violation, compare_with_thresholds)

        subject = "[" + str(self.args['notification_type']) + "] "
        subject += "Test results for \"" + str(self.args['test'])
        subject += "\". Users count: " + str(self.args['users']) + ". From " + str(date) + "."

        return Email(self.args['test'], subject, self.args['user_list'], email_body, charts, date)
