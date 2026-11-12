import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import escape

import resend
from flask import current_app, render_template
from sqlalchemy import update
from werkzeug.security import generate_password_hash

from main.extensions import db
from main.models.user import Accounts, Authentication, PasswordResetToken

# set a max limit of auth code attempts to 5 via global variable
AUTH_CODE_MAX_ATTEMPTS = 5

# This function is reusable,
# This email sending function uses the resend api
def _send_email(to, subject, text, html=None):
    api_key = current_app.config.get("RESEND_API_KEY")

    # if the resend api key isnt used raise a runtime error
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not configured")

    resend.api_key = api_key

    # create the email body setup
    email = {
        "from": current_app.config.get(
            "RESEND_FROM_EMAIL",
            "Rover <noreply@rover-solutions.com>",
        ),
        "to": to,
        "subject": subject,
        "text": text,
    }
    if html is not None:
        email["html"] = html

    # return the email
    return resend.Emails.send(email)

# This is a reusable function for notifying the user via email that their email has been associated with a signup attempt,
def SignupAttemptMail(email):
    user = Accounts.query.filter_by(email=email).first() # query for first instance of the users email address in the database

    # if no email instance found return that value
    if not user:
        return

    # if user email instance found then send the email to let the user know that their email has been used on a signup attempt
    try:
        _send_email(
            to=[user.email],
            subject="Rover signup attempt",
            text=(
                f"Hello {user.username},\n\n"
                "Someone just tried to create a Rover account with this email address. "
                "If this was you, log in instead, if not ignore this message. "
                "\nRover - Support"
            ),
        )

    # except email sending error
    except Exception:
        current_app.logger.exception(
            "Failed to send duplicate email notification to %s",
            user.email,
        )

# Function to create the authentication code for the user account straight after signup,
def Create_Auth_Code(user_account):

    # if users account has no authentication data in the database, make the commit to add
    if not user_account.authentication_data:
        auth_row = Authentication(user_id=user_account.user_id)
        db.session.add(auth_row)
    else:
        auth_row = user_account.authentication_data

    # using secrets module to generate a 7 digit auth code
    auth_code_ = str(secrets.randbelow(9_000_000) + 1_000_000)

    # Store only a password hash, plaintext auth code is sent only to the account email address
    auth_row.auth_code = generate_password_hash(auth_code_) # generate a password hash for auth code
    auth_row.auth_code_expires = datetime.now(timezone.utc) + timedelta(minutes=10) # set an auth code expiry to 10 minutes
    auth_row.last_code_sent_at = datetime.now(timezone.utc) # mark a current timestamp for instance of start for 10 minutes
    auth_row.failed_attempts = 0 # set failed authenticated attempts to 0
    db.session.commit() # makes the commit to the database for the above data

    # return the values for user_account and the auth code to the send auth code function to send the auth code to the users email address
    return SendAuthCode_EMAIL(user_account, auth_code_)

# Function to send the auth code in plain text to the users email address
def SendAuthCode_EMAIL(user_account, auth_code_):
    try:
        _send_email(
            to=[user_account.email],
            subject="Rover Auth Code",
            text=(
                f"Welcome to Rover {user_account.username}!\n\n"
                f"Your auth code is: {auth_code_}\n\n"
                "This code expires in 10 minutes"
            ),
        )

        # return true for a success instance to mark the email sent
        return True, "Auth code sent to your email."

    # except error, then return false instance value
    except Exception:
        current_app.logger.exception(
            "Failed to send authentication code email to %s",
            user_account.email,
        )
        return False, "Failed to send email."

# This function sends an email to the user when their account has been successfully verified
def SendVerificationConfirmationEmail(user_account):
    username = user_account.username

    text = (
        f"Congratulations {username}!\n\n"
        "Your Rover account has been successfully verified. "
        "You can now log in and start using Rover.\n\n"
        "Thanks for joining us,\n"
        "The Rover Team"
    )
    html = render_template(
        "Emails/VerificationConfirmation.html",
        username=username,
    )

    try:
        _send_email(
            to=[user_account.email],
            subject="Your Rover account is verified",
            text=text,
            html=html,
        )
    except Exception:
        current_app.logger.exception(
            "Failed to send verification confirmation email to %s",
            user_account.email,
        )
        return (
            False,
            "Your account is verified, but the confirmation email could not be sent.",
        )

    return True, "Your account is verified. A confirmation email has been sent."


def Create_Password_Reset_Token(user_account):
    token = secrets.token_urlsafe(32)
    token_hash = sha256(token.encode("ascii")).hexdigest()
    now = datetime.now(timezone.utc)
    reset_record = (
        PasswordResetToken.query.filter_by(user_id=user_account.user_id)
        .with_for_update()
        .first()
    )

    if reset_record is None:
        reset_record = PasswordResetToken(
            user_id=user_account.user_id,
            token_hash=token_hash,
            created_at=now,
            expires_at=now + timedelta(minutes=30),
        )
        db.session.add(reset_record)
    else:
        reset_record.token_hash = token_hash
        reset_record.created_at = now
        reset_record.expires_at = now + timedelta(minutes=30)
        reset_record.used_at = None

    db.session.commit()
    return token


def Is_Password_Reset_Token_Valid(token):
    if not isinstance(token, str) or not 32 <= len(token) <= 128:
        return False

    try:
        token_bytes = token.encode("ascii")
    except UnicodeEncodeError:
        return False

    token_hash = sha256(token_bytes).hexdigest()
    reset_record = PasswordResetToken.query.filter_by(token_hash=token_hash).first()
    if reset_record is None or reset_record.used_at is not None:
        return False

    expires_at = reset_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) < expires_at


def Consume_Password_Reset_Token(token, new_password):
    if not isinstance(token, str) or not 32 <= len(token) <= 128:
        return False

    try:
        token_bytes = token.encode("ascii")
    except UnicodeEncodeError:
        return False

    token_hash = sha256(token_bytes).hexdigest()
    reset_record = PasswordResetToken.query.filter_by(token_hash=token_hash).first()
    if reset_record is None or reset_record.used_at is not None:
        return False

    now = datetime.now(timezone.utc)
    expires_at = reset_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if now >= expires_at:
        return False

    password_hash = generate_password_hash(new_password)
    update_result = db.session.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.reset_id == reset_record.reset_id,
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    if update_result.rowcount != 1:
        db.session.rollback()
        return False

    user_account = db.session.get(Accounts, reset_record.user_id)
    if user_account is None:
        db.session.rollback()
        return False

    user_account.password = password_hash
    user_account.session_version += 1
    user_account.failed_login_attempts = 0
    user_account.last_login_attempt = None
    db.session.commit()
    return True


def SendPasswordResetEmail(user_account, reset_url):
    safe_reset_url = escape(reset_url, quote=True)
    text = (
        "We received a request to reset your Rover password.\n\n"
        f"Reset your password using this link:\n{reset_url}\n\n"
        "This link expires in 30 minutes and can only be used once. "
        "If you did not request a reset, you can ignore this email."
    )
    html = f"""\
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font-family:Arial,Helvetica,sans-serif;color:#202124;">
    <h1>Reset your Rover password</h1>
    <p>We received a request to reset your Rover password.</p>
    <p><a href="{safe_reset_url}">Reset your password</a></p>
    <p>This link expires in 30 minutes and can only be used once. If you did not request a reset, you can ignore this email.</p>
</body>
</html>"""

    try:
        _send_email(
            to=[user_account.email],
            subject="Reset your Rover password",
            text=text,
            html=html,
        )
    except Exception:
        current_app.logger.exception(
            "Failed to send password reset email for account %s",
            user_account.user_id,
        )
        return False

    return True


def AuthCode_check(auth_code):
    """Validate the format of a submitted verification code."""
    if not auth_code:
        return False, "auth code cannot hold an empty value"

    if not auth_code.isdigit():
        return False, "auth code must be a whole 7 digit number"

    if len(auth_code) != 7:
        return False, "auth code must be 7 digits long"

    return True, "Valid code"
