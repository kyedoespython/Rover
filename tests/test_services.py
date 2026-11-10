from unittest.mock import patch

from flask import Flask

from main.services.auth_service import SendVerificationConfirmationEmail
from main.services.user_service import Account_Exists_Validator


@patch("main.services.user_service.Accounts")
def test_phone_number_validator_finds_existing_number(accounts):
    accounts.query.filter_by.return_value.first.return_value = object()

    validator = Account_Exists_Validator("user@example.com", "User", "+441234567890")

    assert validator.Phone_number_Found()
    accounts.query.filter_by.assert_called_once_with(phone_number="+441234567890")


@patch("main.services.user_service.Accounts")
def test_phone_number_validator_skips_missing_number(accounts):
    validator = Account_Exists_Validator("user@example.com", "User")

    assert not validator.Phone_number_Found()
    accounts.query.filter_by.assert_not_called()


@patch("main.services.auth_service.mail.send")
def test_verification_confirmation_email_sends_html_and_text_alternatives(send):
    app = Flask(__name__)
    app.config["MAIL_USERNAME"] = "rover@example.com"
    user = type("User", (), {"username": "Alex <Rover>", "email": "alex@example.com"})()

    with app.app_context():
        sent, message = SendVerificationConfirmationEmail(user)

    assert sent
    assert "confirmation email has been sent" in message
    email = send.call_args.args[0]
    assert email.subject == "Your Rover account is verified"
    assert email.recipients == ["alex@example.com"]
    assert "Congratulations Alex <Rover>!" in email.body
    assert "Alex &lt;Rover&gt;" in email.html
    assert "Account verified" in email.html