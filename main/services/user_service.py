from main.extensions import db, mail
from main.models.user import Accounts, Authentication
from flask import current_app
from flask_mail import Message
from werkzeug.security import generate_password_hash
import random
import re
from datetime import datetime, timedelta, timezone

class Contents_Checker:
    def __init__(self, email, username, password, phone_number, country):
        self.email = email
        self.username = username
        self.password = password
        self.phone_number = phone_number
        self.country = country

    def Check_Email_Contents(self):
        if len(self.email) < 3:
            return False, "Email address must contain more than 3 characters"
        if not "@" in self.email:
            return False, "Email address must contain an @ symbol"
        return True, "Email is valid"

    def Check_Username_Contents(self):
        if len(self.username) < 3:
            return False, "Username must contain more than 3 characters"
        if self.username[0] != self.username[0].upper():
            return False, "Username must start with a capital letter"
        if " " in self.username:
            return False, "Username must not contain empty spaces"
        return True, "Username is valid"

    def Check_Password_Contents(self):
        if len(self.password) < 8:
            return False, "Password must contain more than 8 characters"

        contains_uppercase_char = False
        for char in self.password:
            if char.isupper():
                contains_uppercase_char = True
                break
        if not contains_uppercase_char:
            return False, "Password must contain at least one upper case character"

        if not re.search(r'[!@#$%^&*]', self.password):
            return False, "Password must contain a special character (!@#$%^&*)"
        return True, "Password is valid"

    def Check_Phone_Number_Contents(self):
        if not self.phone_number:
            return True, "No phone number entered"

        clean_phone_number = self.phone_number.replace("-", "").replace("(", "").replace(")", "")

        country_codes = {
            "United Kingdom": "+44",
            "United States": "+1",
            "Germany": "+49",
            "France": "+33"
        }

        expected_code = country_codes.get(self.country)

        if not clean_phone_number.startswith(expected_code):
            return False, "Phone number does not match selected country"
        return True, "Phone number is valid"

    def Check_Country_Valid(self):
        if not self.country:
            return False, "Select a valid country"
        return True, "Country is valid"

#
# CHCECK IF ACCOUNTS EXISTS VIA EMAIL, USERNAME, PHONE NUMBER INDIVIDUALLY
#

class Account_Exists_Validator:
    def __init__(self, email, username, phone_number):
        self.email = email
        self.username = username
        self.phone_number = phone_number

    def Email_Found(self):
        Email_Found = Accounts.query.filter_by(email=self.email).first()
        if bool(Email_Found) == 1: print("email exists")
        return bool(Email_Found)

    def Username_Found(self):
        Username_Found = Accounts.query.filter_by(username=self.username).first()
        if bool(Username_Found) == 1: print("username exists")
        return bool(Username_Found)

    def Phone_number_found(self):
        if not self.phone_number:
            return False

        Phone_number_found = Accounts.query.filter_by(phone_number=self.phone_number).first()
        if bool(Phone_number_found) == 1: print("Phone number in use")
        return bool(Phone_number_found)

def AuthCode_check(auth_code):
    if not auth_code:
        return False, "auth code cannot hold an empty value"
    
    if not auth_code.isdigit():
        return False, "auth code must be a whole 7 digit number"

    if not len(auth_code) == 7:
        return False, "auth code must be 7 digits long"

    return True, "Valid code"

# create auth
def Create_Auth_Code(user_account):
    # 1. Update existing auth row (or create if it doesn't exist)
    if not user_account.authentication_data:
        auth_row = Authentication(user_id=user_account.user_id)
        db.session.add(auth_row)
        db.session.commit()
    else:
        auth_row = user_account.authentication_data

    # 2. Generate code and save to DB
    auth_code_ = str(random.randint(1000000, 9999999))
    auth_row.auth_code = generate_password_hash(auth_code_)
    auth_row.auth_code_expires = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.session.commit()

    # 3. Send email
    try:
        msg = Message(
            subject="Rover Auth Code", 
            sender=current_app.config['MAIL_USERNAME'], # Best practice to use config
            recipients=[user_account.email]
        )
        msg.body = f"Welcome to Rover {user_account.username}!\n\nYour auth code is: {auth_code_}\n\nThis code expires in 10 minutes"
        mail.send(msg)
        return True, "Auth code sent to your email."
    except Exception as e:
        print(f"Email failed to send: {e}")
        return False, "Failed to send email."