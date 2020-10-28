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

        report_info = self.__get_report_info()
        results_info = self.__get_results_info()

        status = "PASSED"
        if not report_info['passed']:
            status = "FAILED"

        t_params = {
            "scenario": report_info['name'],
            "start_time": report_info["start_time"],
            "status": status,
            "duration": report_info['duration'],
            "env": report_info['environment'],
            "browser": report_info['browser'].capitalize(),
            "version": report_info['browser_version'],
            "view_port": "1920x1080",
            "loops": report_info["loops"],
            "pages": len(results_info)
        }

        email_body = self.__get_email_body(t_params, results_info)

        charts = []

        return Email(self.test_name, subject, user_list, email_body, charts, date)

    def __extract_recipient_emails(self, info):
        return info['emails'].split(',')

    def __get_test_info(self):
        return self.__get_url(
            f"/tests/{self.galloper_project_id}/frontend/{self.test_id}?raw=1")

    def __get_report_info(self):
        return self.__get_url(f"/observer/{self.galloper_project_id}?report_id={self.report_id}")

    def __get_results_info(self):
        return self.__get_url(f"/visual/{self.galloper_project_id}/{self.report_id}?order=asc")

    def __get_email_body(self, t_params, results_info):
        env = Environment(
            loader=FileSystemLoader('./templates'))
        template = env.get_template("ui_email_template.html")
        return template.render(t_params=t_params, results=results_info)

    def __get_url(self, url):
        resp = requests.get(
            f"{self.gelloper_url}/api/v1{url}", headers={
                'Authorization': f'bearer {self.gelloper_token}',
                'Content-type': 'application/json'
            })

        if resp.status_code != 200:
            raise Exception(f"Error {resp}")

        return resp.json()
