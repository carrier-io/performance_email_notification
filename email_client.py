import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class EmailClient(object):

    def __init__(self, arguments):
        self.host = arguments['smtp_host']
        self.port = int(arguments['smtp_port'])
        self.user = arguments['smtp_user']
        self.password = arguments['smtp_password']
        self.sender = arguments['smtp_sender']
        if self.sender is None:
            self.sender = self.user

    def send_email(self, email):
        s = smtplib.SMTP_SSL(host=self.host, port=self.port)
        s.ehlo()
        s.login(self.user, self.password)

        for recipient in email.users_to:
            if all(i in recipient for i in ["<mailto:", "|"]):
                recipient = recipient.split("|")[1].replace(">", "").replace("<", "")
            msg_root = MIMEMultipart('related')
            msg_root['Subject'] = email.subject
            msg_root['From'] = self.sender
            msg_root['To'] = recipient
            msg_alternative = MIMEMultipart('alternative')
            msg_alternative.attach(MIMEText(email.email_body, 'html'))
            msg_root.attach(msg_alternative)
            for chart in email.charts:
                msg_root.attach(chart)

            s.sendmail(self.sender, recipient, msg_root.as_string())
        s.quit()
