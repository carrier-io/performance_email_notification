from datetime import datetime

import requests
from jinja2 import Environment, FileSystemLoader
from chart_generator import ui_metrics_chart_pages, ui_metrics_chart_actions
from email.mime.image import MIMEImage
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
        last_reports = self.__get_last_report(info['name'], 5)
        tests_data = []
        for each in last_reports:
            report = {"pages": [], "actions": []}
            results_info = self.__get_results_info(each["uid"])
            for result in results_info:
                if result["type"] == "page":
                    report["pages"].append(result)
                else:
                    report["actions"].append(result)
            tests_data.append(report)

        page_comparison, action_comparison = [], []
        for index, test in enumerate(tests_data):
            aggregated_test_data = {}
            for metric in ["total_time", "tti", "fvc", "lvc"]:
                if metric == "total_time":
                    _arr = [each[metric] * 1000 for each in test["pages"]]
                else:
                    _arr = [each[metric] for each in test["pages"]]
                aggregated_test_data[metric] = int(sum(_arr) / len(_arr))
            aggregated_test_data["date"] = last_reports[index]["start_time"][2:-3]
            aggregated_test_data["report"] = f"{self.gelloper_url}/visual/report?report_id={last_reports[index]['id']}"
            page_comparison.append(aggregated_test_data)

            aggregated_test_data = {}
            for metric in ["cls", "tbt"]:
                _arr = [each[metric] for each in test["actions"]]
                aggregated_test_data[metric] = float(sum(_arr) / len(_arr))
            aggregated_test_data["date"] = last_reports[index]["start_time"][2:-3]
            aggregated_test_data["report"] = f"{self.gelloper_url}/visual/report?report_id={last_reports[index]['id']}"
            action_comparison.append(aggregated_test_data)

        user_list = self.__extract_recipient_emails(info)

        date = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
        subject = f"[UI] Test results for {info['name']}. From {date}."

        report_info = self.__get_report_info()
        results_info = self.__get_results_info(self.report_id)
        for each in results_info:
            each["report"] = f"{self.gelloper_url}{each['report']}"

        status = "PASSED"
        if not report_info['passed']:
            status = "FAILED"

        baseline_id = self.__get_baseline_report(report_info['name'], report_info['environment'])
        base_id = baseline_id["baseline_id"]
        baseline_info = []
        if base_id:
            baseline_info = self.__get_results_info(base_id)
        baseline_comparison_pages = []
        baseline_comparison_actions = []
        if baseline_info:
            for current_result in results_info:
                for baseline_result in baseline_info:
                    if current_result["identifier"] == baseline_result["identifier"]:
                        comparison = {"name": current_result["name"]}
                        if current_result["type"] == "page":
                            for each in ["total_time", "fvc", "lvc", "tti"]:
                                comparison[each] = current_result[each]
                                if isinstance(current_result[each], float):
                                    comparison[f"{each}_diff"] = round(current_result[each] - baseline_result[each], 2)
                                else:
                                    comparison[f"{each}_diff"] = current_result[each] - baseline_result[each]
                                if comparison[f"{each}_diff"] > 0:
                                    comparison[f"{each}_diff"] = f'+{comparison[f"{each}_diff"]}'
                                    comparison[f"{each}_diff_color"] = "color:red;"
                                else:
                                    comparison[f"{each}_diff_color"] = "color:green;"
                            baseline_comparison_pages.append(comparison)
                        else:
                            for each in ["tbt", "cls"]:
                                comparison[each] = current_result[each]
                                if isinstance(current_result[each], float):
                                    comparison[f"{each}_diff"] = round(current_result[each] - baseline_result[each], 4)
                                else:
                                    comparison[f"{each}_diff"] = current_result[each] - baseline_result[each]
                                if comparison[f"{each}_diff"] > 0:
                                    comparison[f"{each}_diff"] = f'+{comparison[f"{each}_diff"]}'
                                    comparison[f"{each}_diff_color"] = "color:red;"
                                else:
                                    comparison[f"{each}_diff_color"] = "color:green;"
                            baseline_comparison_actions.append(comparison)

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
        email_body = self.__get_email_body(t_params, results_info, page_comparison, action_comparison,
                                           baseline_comparison_pages, baseline_comparison_actions)

        charts = []
        charts.append(self.create_ui_metrics_chart_pages(page_comparison))
        charts.append(self.create_ui_metrics_chart_actions(action_comparison))

        return Email(self.test_name, subject, user_list, email_body, charts, date)

    def __extract_recipient_emails(self, info):
        return info['emails'].split(',')

    def __get_test_info(self):
        return self.__get_url(
            f"/tests/{self.galloper_project_id}/frontend/{self.test_id}?raw=1")

    def __get_baseline_report(self, name, env):
        return self.__get_url(
            f"/ui_baseline/{self.galloper_project_id}?test_name={name}&env={env}")

    def __get_last_report(self, name, count):
        return self.__get_url(f"/observer/{self.galloper_project_id}?name={name}&count={count}")

    def __get_report_info(self):
        return self.__get_url(f"/observer/{self.galloper_project_id}?report_id={self.report_id}")

    def __get_results_info(self, report_id):
        return self.__get_url(f"/visual/{self.galloper_project_id}/{report_id}?order=asc")

    def __get_email_body(self, t_params, results_info, page_comparison, action_comparison,
                         baseline_comparison_pages, baseline_comparison_actions):
        env = Environment(
            loader=FileSystemLoader('./templates'))
        template = env.get_template("ui_email_template.html")
        return template.render(t_params=t_params, results=results_info, page_comparison=page_comparison,
                               action_comparison=action_comparison, baseline_comparison_pages=baseline_comparison_pages,
                               baseline_comparison_actions=baseline_comparison_actions)

    def __get_url(self, url):
        resp = requests.get(
            f"{self.gelloper_url}/api/v1{url}", headers={
                'Authorization': f'bearer {self.gelloper_token}',
                'Content-type': 'application/json'
            })

        if resp.status_code != 200:
            raise Exception(f"Error {resp}")

        return resp.json()

    @staticmethod
    def create_ui_metrics_chart_pages(builds):
        labels, x, total_time, tti, fvc, lvc = [], [], [], [], [], []
        count = 1
        for test in builds:
            labels.append(test['date'])
            total_time.append(round(test['total_time'], 2))
            tti.append(round(test['tti'], 2))
            fvc.append(round(test['fvc'], 2))
            lvc.append(round(test['lvc'], 2))
            x.append(count)
            count += 1
        datapoints = {
            'title': 'UI metrics',
            'label': 'UI metrics',
            'x_axis': 'Test Runs',
            'y_axis': 'Time, ms',
            'width': 14,
            'height': 4,
            'path_to_save': '/tmp/ui_metrics_pages.png',
            'total_time': total_time[::-1],
            'tti': tti[::-1],
            'fvc': fvc[::-1],
            'lvc': lvc[::-1],
            'values': x,
            'labels': labels[::-1]
        }
        ui_metrics_chart_pages(datapoints)
        fp = open('/tmp/ui_metrics_pages.png', 'rb')
        image = MIMEImage(fp.read())
        image.add_header('Content-ID', '<ui_metrics_pages>')
        fp.close()
        return image

    @staticmethod
    def create_ui_metrics_chart_actions(builds):
        labels, x, cls, tbt = [], [], [], []
        count = 1
        for test in builds:
            labels.append(test['date'])
            cls.append(round(test['cls'], 6))
            tbt.append(round(test['tbt'], 2))
            x.append(count)
            count += 1
        datapoints = {
            'title': 'UI metrics Actions',
            'label': 'UI metrics Actions',
            'x_axis': 'Test Runs',
            'y_axis': 'Time, ms',
            'width': 14,
            'height': 4,
            'path_to_save': '/tmp/ui_metrics_actions.png',
            'cls': cls[::-1],
            'tbt': tbt[::-1],
            'values': x,
            'labels': labels[::-1]
        }
        ui_metrics_chart_actions(datapoints)
        fp = open('/tmp/ui_metrics_actions.png', 'rb')
        image = MIMEImage(fp.read())
        image.add_header('Content-ID', '<ui_metrics_actions>')
        fp.close()
        return image
