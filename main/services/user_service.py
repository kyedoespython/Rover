from main.extensions import db # import database instance
from main.models.user import Accounts # import class table to use

def Check_if_exists(email, username, password_hash, phone_number, country):
    if Accounts.query.filter_by(email=email).first(): return "An account with this email exists"

    if Accounts.query.filter_by(username=username).first(): return "This username is taken"

    if Accounts.query.filter_by(phone_number=phone_number).first(): return "This phone number is in use already"

    else: Create_User(email, username, password_hash, phone_number, country)

def Create_User(email, username, password_hash, phone_number, country):
    user_account = Accounts(
                            email=email,
                            username=username,
                            password=password_hash,
                            phone_number=phone_number,
                            country=country
                            )
    
    db.session.add(user_account)
    db.session.commit()

    return None