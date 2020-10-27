from email_notifications import Email


class UIEmailNotification(object):

    def __init__(self, arguments):
        self.test_name = arguments['test']
        self.smtp_config = {'host': arguments['smtp_host'],
                            'port': arguments['smtp_port'],
                            'user': arguments['smtp_user'],
                            'password': arguments['smtp_password'],
                            'sender': arguments['smtp_sender']}

    def ui_email_notification(self):
        subject = ""
        email_body = ""
        date = ""
        charts = ""
        user_list = []
        return Email(self.test_name, user_list, subject, email_body, charts, date)
