from main.models.user import Accounts, Authentication
from werkzeug.security import check_password_hash
import re

# country codes (useful as global dictionary)
country_codes = {

            "United Kingdom": "+44",
            "United States": "+1",
            "Germany": "+49",
            "France": "+33"
        }

# match up the value of the country code dict to first 2 digits phone numbers
phoneNumber_digit_match = {

    "+44 First Two Digits": ["01", "02", "07", "03", "05", "08", "09"], # UK
    
    "+1 First Digit" : ["2", "3", "4", "5", "6", "7", "8", "9"], # USA
    "+1 Second Digit": ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"],
    
    "+49 First Two Digits": ["15", "16", "17"], # Germany
    
    "+33 First Two Digits": ["06", "07"], # French
}

# check all account fields before insertion to validate via rules
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

    # check if a phone number has been given
    def Check_Phone_Number_Contents(self):
        if not self.phone_number:
            return True, "No phone number entered"

        clean_phone_number = self.phone_number.replace("-", "").replace("(", "").replace(")", "")

        expected_code = country_codes.get(self.country)

        if not clean_phone_number.startswith(expected_code):
            return False, "Phone number does not match selected country"
        return True, "Phone number is valid"

    def Check_Country_Valid(self):
        if not self.country:
            return False, "Select a valid country"
        return True, "Country is valid"

# check if account exists via email, username
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