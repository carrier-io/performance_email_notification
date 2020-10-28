from datetime import datetime

import requests
from jinja2 import Environment, FileSystemLoader

from email_notifications import Email


class UIEmailNotification(object):

    def __init__(self, arguments):
        self.test_id = arguments['test_id']
        self.gelloper_url = arguments['galloper_url']
        self.gelloper_token = arguments['token']
        self.galloper_project_id = arguments['project_id']
        self.report_id = arguments['report_id']
        self.test_name = arguments['test']

    def ui_email_notification(self):
        info = self.__get_test_info()
        user_list = self.__extract_recipient_emails(info)

        date = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
        subject = f"[UI] Test results for {info['name']}. From {date}."

        t_params = {
            "scenario": "DEMO",
            "start_time": "12-2012",
            "status": "PASSED",
            "duration": 24,
            "env": "DEV",
            "browser": "Chrome",
            "version": "86.0",
            "view_port": "1920x1080"
        }

        email_body = self.__get_email_body(t_params)

        charts = []

        return Email(self.test_name, subject, user_list, email_body, charts, date)

    def __extract_recipient_emails(self, info):
        return info['emails'].split(',')

    def __get_test_info(self):
        resp = requests.get(
            f"{self.gelloper_url}/api/v1/tests/{self.galloper_project_id}/frontend/{self.test_id}?raw=1", headers={
                'Authorization': f'bearer {self.gelloper_token}',
                'Content-type': 'application/json'
            })

        if resp.status_code != 200:
            raise Exception(f"Error {resp}")

        return resp.json()

    def __get_email_body(self, t_params):
        env = Environment(
            loader=FileSystemLoader('/home/sergey/SynologyDrive/Github/performance_email_notification/templates'))
        template = env.get_template("ui_email_template.html")
        return template.render(t_params=t_params)
