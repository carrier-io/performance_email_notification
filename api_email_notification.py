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

from datetime import datetime
import requests
from perfreporter.data_manager import DataManager
from report_builder import ReportBuilder
from email_notifications import Email


GREEN = '#028003'
YELLOW = '#FFA400'
RED = '#FF0000'
GRAY = '#CCCCCC'

STATUS_COLOR = {
    "success": GREEN,
    "failed": RED,
    "finished": GRAY
}


class ApiEmailNotification:
    """
    Email notification generator for API performance tests.
    Handles data collection, report generation, and email formatting for backend tests.
    """

    def __init__(self, arguments):
        """
        Initialize API email notification generator.
        
        Args:
            arguments (dict): Configuration dictionary containing:
                - galloper_url: URL of the Galloper instance
                - token: Authentication token
                - project_id: Project identifier
                - test: Test name
                - users: Number of virtual users
                - notification_type: Type of notification (e.g., 'API', 'Backend')
                - user_list: Comma-separated list of recipient emails
                - comparison_metric: Metric to use for baseline comparison (e.g., 'pct95', 'pct90')
                - env: Environment name
                - test_type: Type of test (e.g., 'load', 'stress')
                - performance_degradation_rate: Threshold for performance degradation
                - missed_threshold_rate: Threshold for missed SLA
        """
        self.args = arguments
        self.data_manager = DataManager(
            arguments, 
            arguments["galloper_url"], 
            arguments["token"],
            arguments["project_id"]
        )
        self.report_builder = ReportBuilder()

    def api_email_notification(self):
        """
        Generate email notification for API test results.
        
        Orchestrates the entire email generation process:
        1. Fetches test data from Galloper
        2. Compares with baseline and thresholds
        3. Generates email body and charts
        4. Returns Email object ready to send
        
        Returns:
            Email: Email object containing subject, body, recipients, and charts
        """
        # Fetch test data, baseline, and threshold violations
        tests_data, last_test_data, baseline, violation, compare_with_thresholds = \
            self.data_manager.get_api_test_info()

        # Fetch report data for start_time and end_time
        report_data = self._get_report_data()

        # Generate email body with charts
        email_body, charts, date = self.report_builder.create_api_email_body(
            self.args, 
            tests_data, 
            last_test_data,
            baseline,
            self.args['comparison_metric'],
            violation, 
            compare_with_thresholds,
            report_data
        )

        # Create email subject
        subject = self._create_email_subject(date)

        # Return Email object
        return Email(
            self.args['test'], 
            subject, 
            self.args['user_list'], 
            email_body, 
            charts, 
            date
        )

    def _create_email_subject(self, date):
        """
        Create formatted email subject line.
        
        Args:
            date (str): Test execution date
            
        Returns:
            str: Formatted subject line
        """
        subject = f"[{self.args['notification_type']}] "
        subject += f"Test results for \"{self.args['test']}\". "
        subject += f"Users count: {self.args['users']}. "
        subject += f"From {date}."
        return subject

    def _get_report_data(self):
        """
        Fetch report data from Galloper API to get accurate start_time and end_time.
        
        Returns:
            dict: Report data containing start_time and end_time, or None if request fails
        """
        headers = {'Authorization': f'bearer {self.args["token"]}'} if self.args.get("token") else {}
        report_url = f"{self.args['galloper_url']}/api/v1/backend_performance/reports/{self.args['project_id']}?"
        report_url += f"name={self.args['test']}&limit=1"
        
        try:
            response = requests.get(report_url, headers={**headers, 'Content-type': 'application/json'})
            response.raise_for_status()
            data = response.json()
            
            if data.get('rows') and len(data['rows']) > 0:
                return data['rows'][0]
            return None
        except Exception as e:
            print(f"Failed to fetch report data: {e}")
            return None
