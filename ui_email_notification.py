from email_client import send_email


class UIEmailNotification(object):

    def __init__(self, arguments):
        self.smtp_config = {'host': arguments['smtp_host'],
                            'port': arguments['smtp_port'],
                            'user': arguments['smtp_user'],
                            'password': arguments['smtp_password'],
                            'sender': arguments['smtp_sender']}

    def ui_email_notification(self):
        raise NotImplemented()
        # send_email(self.smtp_config, self.args['user_list'], email_body, charts, date, self.args)
