from lambda_function import lambda_handler


def test_lambda():
    event = {
        "notification_type": "ui",
        "test_id": "d3caeeb7-32bd-4b4b-824d-702708a7116c",
        "report_id": 176,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_user": "serhii.pirohov@gmail.com",
        "smtp_password": "Semen4ik20#12345"
    }
    lambda_handler(event, {})
