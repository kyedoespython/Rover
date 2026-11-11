from html import escape
from hashlib import sha256
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta, timezone
from main.extensions import db
from flask import current_app
from main.models.user import Accounts, Authentication, PasswordResetToken
import resend
import secrets
from sqlalchemy import update

def _send_email(to, subject, text, html=None):
    api_key = current_app.config.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not configured")

    resend.api_key = api_key
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

    return resend.Emails.send(email)

# This function is a reusable signup attempt checker
# It works by querying the database for the current sessions email address looking for the first instance
# It then checks if the user var is false meaning no user with that email exists
# If the email exists it sends the user an email.
def SignupAttemptMail(email):
    user = Accounts.query.filter_by(email=email).first()

    if not user:
        return

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

    except Exception:
        current_app.logger.exception(
            "Failed to send duplicate email notification to %s",
            user.email,
        )



# Create the auth code via secrets
def Create_Auth_Code(user_account):

    # if the user has no authenctication data, make sure they do by commiting
    if not user_account.authentication_data:
        auth_row = Authentication(user_id=user_account.user_id)
        db.session.add(auth_row)
        db.session.commit()
    
    else:
        auth_row = user_account.authentication_data

    auth_code_ = str(secrets.randbelow(9000000) + 1000000) # generate an auth code 7 digits long via randint

    auth_row.auth_code = generate_password_hash(auth_code_) # generate a hash for the auth code via werkzeug
    auth_row.auth_code_expires = datetime.now(timezone.utc) + timedelta(minutes=10) # save the 10 minutes time to the database to ensure limit is 10 minutes
    auth_row.last_code_sent_at = datetime.now(timezone.utc) # save the copy of the timestamp showing when the last authentication attempt was
    db.session.commit()

    # Send the auth code to the user's email.
    return SendAuthCode_EMAIL(user_account, auth_code_) # return / send values into the function call to be used to send the email with the auth code inside of it

# send the auth code in an email message, 
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

        return True, "Auth code sent to your email."
    
    except Exception:
        current_app.logger.exception(
            "Failed to send authentication code email to %s",
            user_account.email,
        )
        return False, "Failed to send email."


def SendVerificationConfirmationEmail(user_account):
    username = user_account.username
    safe_username = escape(username)

    text = (
        f"Congratulations {username}!\n\n"
        "Your Rover account has been successfully verified. "
        "You can now log in and start using Rover.\n\n"
        "Thanks for joining us,\n"
        "The Rover Team"
    )
    html = f"""\
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Your Rover account is verified</title>
</head>
<body style="margin:0;padding:0;background-color:#f2f2f2;font-family:Arial,Helvetica,sans-serif;color:#202124;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#f2f2f2;padding:32px 12px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background-color:#ffffff;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
                    <tr>
                        <td style="padding:28px 32px;background-color:#111111;color:#ffffff;">
                            <p style="margin:0;font-size:13px;letter-spacing:2px;text-transform:uppercase;">Rover</p>
                            <h1 style="margin:12px 0 0;font-size:24px;line-height:1.3;">Account verified</h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:32px;">
                            <p style="margin:0 0 16px;font-size:17px;line-height:1.6;">Congratulations <strong>{safe_username}</strong>!</p>
                            <p style="margin:0 0 24px;font-size:15px;line-height:1.7;color:#4b5563;">
                                Your Rover account has been successfully verified. You can now log in and start using Rover.
                            </p>
                            <p style="margin:0;font-size:15px;line-height:1.7;color:#4b5563;">
                                Thanks for joining us,<br><strong style="color:#202124;">The Rover Team</strong>
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:16px 32px;border-top:1px solid #e5e7eb;color:#6b7280;font-size:12px;line-height:1.5;">
                            This message confirms a change to your Rover account.
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

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
        return False, "Your account is verified, but the confirmation email could not be sent."

    return True, "Your account is verified. A confirmation email has been sent."


def Create_Password_Reset_Token(user_account):
    token = secrets.token_urlsafe(32)
    token_hash = sha256(token.encode("ascii")).hexdigest()
    now = datetime.now(timezone.utc)
    reset_record = PasswordResetToken.query.filter_by(
        user_id=user_account.user_id
    ).with_for_update().first()

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


# check if the auth code field from the web page is a valid input
def AuthCode_check(auth_code):
    if not auth_code:
        return False, "auth code cannot hold an empty value"
    
    if not auth_code.isdigit():
        return False, "auth code must be a whole 7 digit number"

    if not len(auth_code) == 7:
        return False, "auth code must be 7 digits long"

    return True, "Valid code"