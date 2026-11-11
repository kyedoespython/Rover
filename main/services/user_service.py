import re

import phonenumbers

from main.models.user import Accounts

# These regions are the only countries accepted by the signup form.
country_regions = {
    "United Kingdom": "GB",
    "United States": "US",
    "Germany": "DE",
    "France": "FR",
}


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
        if "@" not in self.email:
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

        if not re.search(r"[!@#$%^&*]", self.password):
            return False, "Password must contain a special character (!@#$%^&*)"
        return True, "Password is valid"

    def Check_Phone_Number_Contents(self):
        if not self.phone_number:
            return True, "No phone number entered"

        region = country_regions.get(self.country)
        if region is None:
            return False, "Select a valid country"

        try:
            phone_number = phonenumbers.parse(
                self.phone_number,
                None if self.phone_number.lstrip().startswith("+") else region,
            )
        except phonenumbers.NumberParseException:
            return False, "Enter a valid phone number"

        if not phonenumbers.is_valid_number(phone_number):
            return False, "Enter a valid phone number"

        if phonenumbers.region_code_for_number(phone_number) != region:
            return False, "phone number and country doesnt match"

        return True, "Phone number is valid"

    def Check_Country_Valid(self):
        if self.country not in country_regions:
            return False, "Select a valid country"
        return True, "Country is valid"


class Account_Exists_Validator:
    def __init__(self, email, username, phone_number=None):
        self.email = email
        self.username = username
        self.phone_number = phone_number

    def Email_Found(self):
        user = Accounts.query.filter_by(email=self.email).first()
        return user is not None

    def Username_Found(self):
        user = Accounts.query.filter_by(username=self.username).first()
        return user is not None

    def Phone_number_Found(self):
        if not self.phone_number:
            return False
        user = Accounts.query.filter_by(phone_number=self.phone_number).first()
        return user is not None
