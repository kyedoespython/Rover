from unittest.mock import patch

from flask import Flask

from main.services.auth_service import (
    SendAuthCode_EMAIL,
    SendVerificationConfirmationEmail,
    resend,
)
from main.services.user_service import Account_Exists_Validator, Contents_Checker


def test_phone_number_validator_accepts_local_number_for_selected_country():
    checker = Contents_Checker("", "", "", "020 8366 1177", "United Kingdom")

    assert checker.Check_Phone_Number_Contents() == (True, "Phone number is valid")


def test_phone_number_validator_rejects_number_from_different_country():
    checker = Contents_Checker("", "", "", "+442083661177", "France")

    assert checker.Check_Phone_Number_Contents() == (
        False,
        "phone number and country doesnt match",
    )


def test_phone_number_validator_detects_region_inside_shared_calling_code():
    checker = Contents_Checker("", "", "", "+14165550123", "United States")

    assert checker.Check_Phone_Number_Contents() == (
        False,
        "phone number and country doesnt match",
    )


def test_phone_number_validator_rejects_unsupported_country():
    checker = Contents_Checker("", "", "", "+442083661177", "Canada")

    assert checker.Check_Phone_Number_Contents() == (False, "Select a valid country")


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


@patch("main.services.auth_service.resend.Emails.send")
def test_verification_confirmation_email_sends_html_and_text_alternatives(send):
    app = Flask(__name__)
    app.config["RESEND_API_KEY"] = "test-resend-key"
    app.config["RESEND_FROM_EMAIL"] = "rover@example.com"
    user = type("User", (), {"username": "Alex <Rover>", "email": "alex@example.com"})()

    with app.app_context():
        sent, message = SendVerificationConfirmationEmail(user)

    assert sent
    assert "confirmation email has been sent" in message
    email = send.call_args.args[0]
    assert email["from"] == "rover@example.com"
    assert email["to"] == ["alex@example.com"]
    assert email["subject"] == "Your Rover account is verified"
    assert "Congratulations Alex <Rover>!" in email["text"]
    assert "Alex &lt;Rover&gt;" in email["html"]
    assert "Account verified" in email["html"]


@patch("main.services.auth_service.resend.Emails.send")
def test_auth_code_email_uses_resend_api_key_from_app_config(send):
    app = Flask(__name__)
    app.config["RESEND_API_KEY"] = "test-resend-key"
    user = type("User", (), {"username": "Alex", "email": "alex@example.com"})()

    with app.app_context():
        sent, message = SendAuthCode_EMAIL(user, "1234567")

    assert sent
    assert message == "Auth code sent to your email."
    assert resend.api_key == "test-resend-key"
    assert send.call_args.args[0]["from"] == "Rover <noreply@rover-solutions.com>"
    assert send.call_args.args[0]["to"] == ["alex@example.com"]
    assert "1234567" in send.call_args.args[0]["text"]