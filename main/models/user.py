from main.extensions import db
from flask_login import UserMixin
from sqlalchemy import func, ForeignKey

class Accounts(db.Model, UserMixin):
    
    __tablename__ = "accounts"

    # primary key to store users id's
    user_id = db.Column(db.Integer, primary_key=True)
    
    # creates a link between the foreign key (auth_id) to (user_id)
    authentication_data = db.relationship('Authentication', backref='user_account', uselist=False)

    # creates a link between the foreign key (note_id) to (user_id)
    user_notes = db.relationship('Notes', backref='author', lazy=True)

    # creates a link between the (ticket_id) and the (user_id)
    user_tickets = db.relationship('Tickets', backref='user', lazy=True)

    email = db.Column(db.String(254), unique=True, nullable=False)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    phone_number = db.Column(db.String(32), unique=True, nullable=True)
    country_of_origin = db.Column(db.String(64), nullable=False)

    # timestamp uses server_default so postgres fills it in automatically and avoids crashes
    account_created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False) # timestamp

    # store the amount of failed login attempts the user has had, defaulted to no failed login attempts
    failed_login_attempts = db.Column(db.Integer, default=0, server_default="0", nullable=False)

    # timestamp to store the last known login attempt of the user
    # starts empty and filled only when the user attempts to login / logs into there account
    last_login_attempt = db.Column(db.DateTime(timezone=True), nullable=True)

    # required for flask_login
    def get_id(self):
        return str(self.user_id)

class Authentication(db.Model):

    __tablename__ = "authentication"

    # main authenctication id
    auth_id = db.Column(db.Integer, primary_key=True)

    # user_id connected to one single auth_id as a one to one relationship (unique=True sets as one row for auth)
    user_id = db.Column(db.Integer, ForeignKey("accounts.user_id"), unique=True, nullable=False)

    # auth_code stores the auth code
    auth_code = db.Column(db.String(256), nullable=True)
    
    # auth_code_expires stores the 10 minute count to expiry, start off empty
    auth_code_expires = db.Column(db.DateTime, nullable=True)

    # user starts un authenticated, then if authenticated gets timestamped
    authenticated = db.Column(db.Boolean, default=False, nullable=False) # show yes or now on a users auth status

    # timestamp for storing the date and time of the authentication of the user account
    authenticated_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # store failed attempts to authenticate, default to no failed attempts, then it adds up per failed attempt
    failed_attempts = db.Column(db.Integer, default=0, server_default="0", nullable=False)

    # store the timestamp of when the last auth code was sent, can be null if there was no auth code sent at all
    last_code_sent_at = db.Column(db.DateTime, nullable=True)

class Tickets(db.Model):

    __tablename__ = "tickets"

    # ticket id to store the id for the whole ticket
    ticket_id = db.Column(db.Integer, primary_key=True)

    # foreign key one user to many tickets (unique is false so tickets can have the same user_id)
    user_id = db.Column(db.Integer, ForeignKey('accounts.user_id'), nullable=False)

    ticket_type = db.Column(db.String(64), nullable=False) # stores what type of the ticket has been created
    ticket_name = db.Column(db.String(64), nullable=False, unique=True) # stores the name of the ticket
    ticket_content = db.Column(db.String(512), nullable=False) # stores the actual ticket content

    # timestamp for when the user created the ticket
    ticket_created_at = db.Column(db.DateTime(timezone=True), nullable=False)

class Notes(db.Model):

    __tablename__ = "notes"

    # id to store the note id for the whole note section
    note_id = db.Column(db.Integer, primary_key=True)

    # foreign key representing the one to many relationship between one user -> many notes
    user_id = db.Column(db.Integer, ForeignKey('accounts.user_id'), nullable=False)

    note_name = db.Column(db.String(128), nullable=False, unique=True) # stores the name of the note given by the user
    note_description = db.Column(db.String(512), nullable=False) # stores the description of the note provides by the user
    note_content = db.Column(db.String(4096), nullable=True) # stores the actual content inside the note 'body'

    note_created_at = db.Column(db.DateTime(timezone=True), nullable=False) # stores a timestamp of when the note was created
    note_last_modified_at = db.Column(db.DateTime(timezone=True), nullable=False) # stores a timestamp of the last time a specific note was modified by the user