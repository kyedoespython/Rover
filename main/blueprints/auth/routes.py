import sqlite3
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from math import isfinite

from flask import (
    current_app,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import case, func, update
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from main.extensions import db, limiter
from main.models.user import (
    Accounts,
    Authentication,
    Notes,
    UserApiKey,
    UserSchemaDatabase,
    UserSchema,
)

from main.services.auth_service import (
    AUTH_CODE_MAX_ATTEMPTS,
    AuthCode_check,
    Consume_Password_Reset_Token,
    Create_Auth_Code,
    Create_Password_Reset_Token,
    Is_Password_Reset_Token_Valid,
    SendPasswordResetEmail,
    SendVerificationConfirmationEmail,
    SignupAttemptMail,
)

from main.services.notes_service import (
    create_note,
    delete_note,
    ensure_default_note,
    read_note_content,
    update_note,
)

from main.services.ollama_service import encrypt_api_key
from main.services.user_service import Account_Exists_Validator, Contents_Checker

from . import auth_bp

# This is the route for the signup page
@auth_bp.route("/Rover/Sign Up")
def Signup():
    return render_template("Signup/Signup.html")

# This is the route for handling the signup request, request must be a post request to perform the signup action,
# Inside the signup page i use my limiter class to set a rate limit on login attempts to 5 per minute and a max of 50 per day,
@auth_bp.route("/Handle_signup", methods=["POST", "GET"])
@limiter.limit("5/minute; 50 per day")
def Handle_Signup():
    if request.method == "POST":

        # get the form data from the web page inputs, strip whitespace for solving accidental user typing errors,
        # the password feild isnt stripped of whitespace as the user may want to include that inside their password
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password")
        phone_number = request.form.get("telephone", "").strip()
        country = request.form.get("country", "").strip()

        # run the contents checker function 
        contents_checker = Contents_Checker(
            email, username, password, phone_number, country
        )

        is_valid, message = contents_checker.Check_Email_Contents()
        if not is_valid:
            flash(message, "error")
            return redirect(url_for("auth.Signup"))

        is_valid, message = contents_checker.Check_Username_Contents()
        if not is_valid:
            flash(message, "error")
            return redirect(url_for("auth.Signup"))

        is_valid, message = contents_checker.Check_Password_Contents()
        if not is_valid:
            flash(message, "error")
            return redirect(url_for("auth.Signup"))

        is_valid, message = contents_checker.Check_Phone_Number_Contents()
        if not is_valid:
            flash(message, "error")
            return redirect(url_for("auth.Signup"))

        is_valid, message = contents_checker.Check_Country_Valid()
        if not is_valid:
            flash(message, "error")
            return redirect(url_for("auth.Signup"))

        account_checker = Account_Exists_Validator(email, username, phone_number)

        # Return the same response for every duplicate field to prevent enumeration.
        if (
            account_checker.Email_Found()
            or account_checker.Username_Found()
            or account_checker.Phone_number_Found()
        ):
            SignupAttemptMail(email)

            flash("Check your email inbox", "info")
            session.pop("pending_auth_email", None)
            return redirect(url_for("auth.Authenticate_User"))

        # Store an omitted phone number as NULL rather than an empty unique value.
        clean_empty_phone_number = phone_number if phone_number else None

        AccountBlock = Accounts(
            email=email,
            username=username,
            password=generate_password_hash(password),
            phone_number=clean_empty_phone_number,
            country_of_origin=country,
        )

        db.session.add(AccountBlock)
        db.session.flush()

        success, message = Create_Auth_Code(AccountBlock)

        if success:
            flash(
                "Account created successfully, Check your email inbox for your auth code",
                "success",
            )
        else:
            flash(message, "error")

        db.session.commit()

        session["pending_auth_email"] = email
        return redirect(url_for("auth.Authenticate_User"))


@auth_bp.route("/Rover/Auth")
def Authenticate_User():
    return render_template("Auth/Auth.html")


@auth_bp.route("/HandleAuth", methods=["POST", "GET"])
@limiter.limit("10/minute; 100 per day")
def Handle_Auth():
    if request.method == "POST":
        auth_code = request.form.get("authCode", "").strip()

        is_valid, message = AuthCode_check(auth_code)
        if not is_valid:
            flash(message, "error")
            return redirect(url_for("auth.Authenticate_User"))

        pending_email = session.get("pending_auth_email")

        if not pending_email:
            flash("No authentication session found.", "error")
            return redirect(url_for("auth.Login"))

        user = Accounts.query.filter_by(email=pending_email).first()

        if not user:
            flash("Error finding account.", "error")
            return redirect(url_for("auth.Login"))

        authentication = (
            Authentication.query.filter_by(user_id=user.user_id)
            .with_for_update()
            .one_or_none()
        )
        if not authentication:
            flash("Error finding account.", "error")
            return redirect(url_for("auth.Authenticate_User"))

        if (
            authentication.authenticated
            or not authentication.auth_code
            or not authentication.auth_code_expires
            or authentication.failed_attempts >= AUTH_CODE_MAX_ATTEMPTS
        ):
            flash("This code is no longer valid. Request a new code.", "error")
            return redirect(url_for("auth.Authenticate_User"))

        expiry = authentication.auth_code_expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expiry:
            flash("Your auth code has expired", "error")
            return redirect(url_for("auth.Authenticate_User"))

        if check_password_hash(authentication.auth_code, auth_code):
            authentication.authenticated = True
            authentication.auth_code = None
            authentication.auth_code_expires = None
            authentication.failed_attempts = 0
            db.session.commit()
            session.pop("pending_auth_email", None)

            sent, message = SendVerificationConfirmationEmail(user)
            flash(
                f"{message} Please log in.",
                "success" if sent else "info",
            )
            return redirect(url_for("auth.Login"))

        attempts_exhausted = (
            Authentication.failed_attempts + 1 >= AUTH_CODE_MAX_ATTEMPTS
        )
        result = db.session.execute(
            update(Authentication)
            .where(
                Authentication.user_id == user.user_id,
                Authentication.authenticated.is_(False),
                Authentication.auth_code == authentication.auth_code,
                Authentication.auth_code_expires == authentication.auth_code_expires,
                Authentication.failed_attempts < AUTH_CODE_MAX_ATTEMPTS,
            )
            .values(
                failed_attempts=Authentication.failed_attempts + 1,
                auth_code=case(
                    (attempts_exhausted, None),
                    else_=Authentication.auth_code,
                ),
                auth_code_expires=case(
                    (attempts_exhausted, None),
                    else_=Authentication.auth_code_expires,
                ),
            )
            .execution_options(synchronize_session=False)
        )
        db.session.commit()

        if result.rowcount != 1:
            flash("This code is no longer valid. Request a new code.", "error")
        else:
            db.session.expire(authentication)
            if authentication.failed_attempts >= AUTH_CODE_MAX_ATTEMPTS:
                flash(
                    "Too many invalid auth code attempts. Request a new code.", "error"
                )
            else:
                flash("Invalid auth code", "error")
        return redirect(url_for("auth.Authenticate_User"))


@auth_bp.route("/Resend_Auth", methods=["POST"])
@limiter.limit("10/minute; 100 per day")
def ResendAuth():
    pending_email = session.get("pending_auth_email")

    if not pending_email:
        flash("No authentication session found. Please log in again.", "error")
        return redirect(url_for("auth.Login"))

    user = Accounts.query.filter_by(email=pending_email).first()

    if not user:
        flash("Error finding account.", "error")
        return redirect(url_for("auth.Login"))

    # Enforce the cooldown so repeated requests cannot spam verification emails.
    if user.authentication_data.last_code_sent_at:
        last_sent = user.authentication_data.last_code_sent_at.replace(
            tzinfo=timezone.utc
        )
        time_passed = datetime.now(timezone.utc) - last_sent

        if time_passed < timedelta(minutes=10):
            minutes_left = 10 - int(time_passed.total_seconds() // 60)
            flash(
                f"You must wait {minutes_left} before you can request a new auth code",
                "error",
            )
            return redirect(url_for("auth.Authenticate_User"))

    success, message = Create_Auth_Code(user)

    if success:
        flash("A new auth code has been sent to your email.", "success")
    else:
        flash(message, "error")

    return redirect(url_for("auth.Authenticate_User"))


@auth_bp.route("/Rover/Login")
def Login():
    return render_template("Login/Login.html")


def _password_reset_email_limit_key():
    email = request.form.get("email", "").strip().casefold()
    return sha256(email.encode("utf-8")).hexdigest()


def _password_reset_url(token):
    reset_path = url_for("auth.Reset_Password", token=token)
    public_base_url = current_app.config.get("PUBLIC_BASE_URL")
    if public_base_url:
        return f"{public_base_url.rstrip('/')}{reset_path}"
    if current_app.debug:
        return f"{request.url_root.rstrip('/')}{reset_path}"
    raise RuntimeError("PUBLIC_BASE_URL is required to send password reset links")


def _password_reset_redirect(endpoint, **values):
    response = make_response(redirect(url_for(endpoint, **values)))
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@auth_bp.route("/Rover/Forgot-Password")
def Forgot_Password():
    return render_template("Auth/ForgotPassword.html")


@auth_bp.route("/Handle_Forgot_Password", methods=["POST"])
@limiter.limit("10 per hour")
@limiter.limit("3 per hour", key_func=_password_reset_email_limit_key)
def Handle_Forgot_Password():
    email = request.form.get("email", "").strip()
    if email and len(email) <= 254:
        user_account = Accounts.query.filter(
            func.lower(Accounts.email) == email.casefold()
        ).first()
        if user_account is not None:
            token = Create_Password_Reset_Token(user_account)
            SendPasswordResetEmail(user_account, _password_reset_url(token))

    flash(
        "If an account exists for that email, password reset instructions will be sent.",
        "info",
    )
    return redirect(url_for("auth.Forgot_Password"))


@auth_bp.route("/Rover/Reset-Password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def Reset_Password():
    if request.method == "GET":
        token = request.args.get("token", "")
        if not Is_Password_Reset_Token_Valid(token):
            flash(
                "That password reset link is invalid or expired. Request a new one.",
                "error",
            )
            return _password_reset_redirect("auth.Forgot_Password")

        response = make_response(
            render_template("Auth/ResetPassword.html", token=token)
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response

    token = request.form.get("token", "")
    if not Is_Password_Reset_Token_Valid(token):
        flash(
            "That password reset link is invalid or expired. Request a new one.",
            "error",
        )
        return _password_reset_redirect("auth.Forgot_Password")

    password = request.form.get("password", "")
    confirmation = request.form.get("confirm_password", "")
    if password != confirmation:
        flash("The passwords do not match.", "error")
        return _password_reset_redirect("auth.Reset_Password", token=token)
    if len(password) > 128:
        flash("Password must be 128 characters or fewer.", "error")
        return _password_reset_redirect("auth.Reset_Password", token=token)

    password_checker = Contents_Checker("", "", password, "", "")
    is_valid, message = password_checker.Check_Password_Contents()
    if not is_valid:
        flash(message, "error")
        return _password_reset_redirect("auth.Reset_Password", token=token)

    if not Consume_Password_Reset_Token(token, password):
        flash(
            "That password reset link is invalid or expired. Request a new one.",
            "error",
        )
        return _password_reset_redirect("auth.Forgot_Password")

    logout_user()
    flash("Your password has been reset. Please log in.", "success")
    return redirect(url_for("auth.Login"))


@auth_bp.route("/Handle_Login", methods=["POST", "GET"])
@limiter.limit("5 per minute")
def Handle_Login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = Accounts.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password, password):
            flash("Invalid username or password.", "error")
            return redirect(url_for("auth.Login"))

        if not user.authentication_data.authenticated:
            if user.authentication_data.auth_code_expires:
                expiry = user.authentication_data.auth_code_expires.replace(
                    tzinfo=timezone.utc
                )
                if datetime.now(timezone.utc) > expiry:
                    flash("Your auth code expired. Please request a new one.", "error")
                    return redirect(url_for("auth.Login"))

            flash("Please verify your email before logging in.", "error")

            session["pending_auth_email"] = user.email
            return redirect(url_for("auth.Authenticate_User"))

        # Temporarily lock accounts after repeated failed logins.
        if user.failed_login_attempts >= 5 and user.last_login_attempt:
            last_attempt = user.last_login_attempt.replace(tzinfo=timezone.utc)
            time_passed = datetime.now(timezone.utc) - last_attempt

            if time_passed < timedelta(minutes=15):
                minutes_left = 15 - int(time_passed.total_seconds() // 60)
                flash(
                    f"Too many failed attempts to login, you can try again in {minutes_left} minutes",
                    "error",
                )
                return redirect(url_for("auth.Login"))
            else:
                user.failed_login_attemps = (
                    0  # if 15 minutes has passed reset the failed login attempts to 0
                )
                user.last_login_attempt = datetime.now(timezone.utc)
                db.session.commit()  # commit change

        login_user(user)

        flash(f"Welcome back {user.username}!", "success")

        return redirect(url_for("auth.DesignDash"))


@auth_bp.route("/DesignDashboard")
@login_required  # only logged in users can access the design dashboard
def DesignDash():
    return render_template("Design/DesignDash.html")


@auth_bp.route("/DesignDashboard/Agents")
@login_required
def AgentsDash():
    return render_template("Design/Agents.html")


def _require_verified_account():
    authentication = current_user.authentication_data
    if authentication is None or not authentication.authenticated:
        flash("Please verify your email before accessing this page.", "error")
        logout_user()
        return redirect(url_for("auth.Login"))
    return None


@auth_bp.route("/Rover/Design/API-Keys", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def Save_User_Api_Key():
    authentication = current_user.authentication_data
    if authentication is None or not authentication.authenticated:
        return jsonify(error="Verify your account before saving an API key."), 403

    if not request.is_json:
        return jsonify(error="A JSON request is required."), 415

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="The request body must be valid JSON."), 400

    key_name = payload.get("name")
    key_type = payload.get("type")
    api_key = payload.get("api_key")
    if not all(isinstance(value, str) for value in (key_name, key_type, api_key)):
        return jsonify(error="Name, type, and API key are required."), 400

    key_name = key_name.strip()
    api_key = api_key.strip()
    if not key_name or len(key_name) > 128:
        return jsonify(error="Name must be between 1 and 128 characters."), 400
    if key_type != "ollama":
        return jsonify(error="Select a supported API key type."), 400
    if not api_key or len(api_key) > 4096:
        return jsonify(error="API key must be between 1 and 4096 characters."), 400

    now = datetime.now(timezone.utc)
    saved_key = UserApiKey.query.filter_by(
        user_id=current_user.user_id,
        key_name=key_name,
    ).first()
    if saved_key is not None and saved_key.key_ciphertext is not None:
        return jsonify(error="You already have an API key with that name."), 409

    if saved_key is None:
        saved_key = UserApiKey(
            user_id=current_user.user_id,
            key_name=key_name,
            key_type=key_type,
            key_hash=generate_password_hash(api_key),
            created_at=now,
            updated_at=now,
        )
        db.session.add(saved_key)
    else:
        saved_key.key_type = key_type
        saved_key.key_hash = generate_password_hash(api_key)
        saved_key.updated_at = now

    try:
        db.session.flush()
        saved_key.key_ciphertext = encrypt_api_key(
            api_key,
            saved_key.user_id,
            saved_key.api_key_id,
        )
        current_user.active_ollama_api_key_id = saved_key.api_key_id
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="You already have an API key with that name."), 409
    except RuntimeError as error:
        db.session.rollback()
        current_app.logger.exception("Unable to encrypt the submitted Ollama API key")
        return jsonify(error=str(error)), 500

    return jsonify(
        api_key={
            "id": saved_key.api_key_id,
            "name": saved_key.key_name,
            "type": saved_key.key_type,
            "created_at": saved_key.created_at.isoformat(),
        }
    ), 201


@auth_bp.route("/Rover/Settings")
@login_required
def Settings():
    access_denied = _require_verified_account()
    if access_denied:
        return access_denied
    api_keys = (
        UserApiKey.query.filter_by(user_id=current_user.user_id)
        .order_by(UserApiKey.created_at.desc())
        .all()
    )
    return render_template(
        "Settings/Settings.html",
        api_keys=api_keys,
        active_api_key_id=current_user.active_ollama_api_key_id,
    )


@auth_bp.route("/Rover/Notes", methods=["GET", "POST"])
@login_required
def Notes_Page():
    access_denied = _require_verified_account()
    if access_denied:
        return access_denied

    if request.method == "POST":
        name = request.form.get("note_name", "").strip()
        description = request.form.get("note_description", "").strip()
        content = request.form.get("note_content", "")

        if not name:
            flash("A note name is required.", "error")
            return redirect(url_for("auth.Notes_Page"))
        if len(name) > 128 or len(description) > 512 or len(content) > 4096:
            flash("The note exceeds the allowed length.", "error")
            return redirect(url_for("auth.Notes_Page"))

        try:
            create_note(current_user.user_id, name, description, content)
        except IntegrityError:
            db.session.rollback()
            flash("A note with that name already exists.", "error")
            return redirect(url_for("auth.Notes_Page"))
        except OSError:
            current_app.logger.exception("Unable to save a Markdown note")
            flash("The note could not be saved. Please try again.", "error")
            return redirect(url_for("auth.Notes_Page"))

        flash("Note created. Select it from Your notes to open it.", "success")
        return redirect(url_for("auth.Notes_Page"))

    try:
        ensure_default_note(current_user.user_id)
    except OSError:
        current_app.logger.exception("Unable to create the default Markdown note")
        flash("Your default note could not be created. Please try again.", "error")

    selected_note = None
    selected_content = ""
    load_id = request.args.get("load_id", type=int)
    if load_id is not None:
        selected_note = Notes.query.filter_by(
            note_id=load_id,
            user_id=current_user.user_id,
        ).first_or_404()
        try:
            selected_content = read_note_content(selected_note)
        except OSError:
            current_app.logger.exception(
                "Unable to load Markdown file for note %s", selected_note.note_id
            )
            flash("This note file could not be loaded.", "error")
            selected_note = None

    pagination = (
        Notes.query.filter_by(user_id=current_user.user_id)
        .order_by(Notes.note_last_modified_at.desc())
        .paginate(
            page=request.args.get("page", 1, type=int),
            per_page=50,
            max_per_page=100,
            error_out=False,
        )
    )
    return render_template(
        "Notes/Notes.html",
        notes=pagination.items,
        pagination=pagination,
        selected_note=selected_note,
        selected_content=selected_content,
    )


@auth_bp.route("/Rover/Notes/<int:note_id>/update", methods=["POST"])
@login_required
def Update_Note(note_id):
    access_denied = _require_verified_account()
    if access_denied:
        return access_denied

    note = Notes.query.filter_by(
        note_id=note_id,
        user_id=current_user.user_id,
    ).first_or_404()
    name = request.form.get("note_name", note.note_name).strip()
    description = request.form.get("note_description", note.note_description).strip()
    content = request.form.get("note_content", "")

    if not name:
        flash("A note name is required.", "error")
        return redirect(url_for("auth.Notes_Page"))
    if len(name) > 128 or len(description) > 512 or len(content) > 4096:
        flash("The note exceeds the allowed length.", "error")
        return redirect(url_for("auth.Notes_Page"))

    try:
        update_note(note, name, description, content)
    except IntegrityError:
        db.session.rollback()
        flash("A note with that name already exists.", "error")
        return redirect(url_for("auth.Notes_Page"))
    except OSError:
        current_app.logger.exception(
            "Unable to update Markdown file for note %s", note_id
        )
        flash("The note could not be updated. Please try again.", "error")
        return redirect(url_for("auth.Notes_Page", load_id=note_id))

    flash("Note updated.", "success")
    return redirect(url_for("auth.Notes_Page", load_id=note_id))


@auth_bp.route("/Rover/Notes/<int:note_id>/description", methods=["POST"])
@login_required
def Update_Note_Description(note_id):
    access_denied = _require_verified_account()
    if access_denied:
        return access_denied

    note = Notes.query.filter_by(
        note_id=note_id,
        user_id=current_user.user_id,
    ).first_or_404()
    description = request.form.get("note_description", "").strip()

    if len(description) > 512:
        flash("The note description exceeds the allowed length.", "error")
        return redirect(url_for("auth.Notes_Page"))

    note.note_description = description
    note.note_last_modified_at = datetime.now(timezone.utc)
    db.session.commit()
    flash("Note description updated.", "success")
    return redirect(url_for("auth.Notes_Page", load_id=note_id))


@auth_bp.route("/Rover/Notes/<int:note_id>/delete", methods=["POST"])
@login_required
def Delete_Note(note_id):
    access_denied = _require_verified_account()
    if access_denied:
        return access_denied

    note = Notes.query.filter_by(
        note_id=note_id,
        user_id=current_user.user_id,
    ).first_or_404()
    delete_note(note)
    flash("Note deleted.", "success")
    return redirect(url_for("auth.Notes_Page"))


SCHEMA_DATA_TYPES = {
    "AutoNumber",
    "Short Text",
    "Long Text",
    "Number",
    "Decimal",
    "Date/Time",
    "Yes/No",
    "Currency",
    "Attachment",
}
SCHEMA_LINE_COLORS = {
    "#2878b5",
    "#d64545",
    "#2b8a3e",
    "#9c36b5",
    "#e67700",
    "#00838f",
    "#343a40",
}
SCHEMA_FILE_EXTENSIONS = {"db", "sqlite", "sqlite3"}
MAX_SCHEMA_FILE_BYTES = 25 * 1024 * 1024
MAX_SCHEMA_QUERY_LENGTH = 10_000
MAX_SCHEMA_QUERY_ROWS = 200
MAX_SCHEMA_QUERY_STEPS = 250_000
MAX_SCHEMA_QUERY_RESULT_BYTES = 256 * 1024
SCHEMA_SQLITE_TYPES = {
    "AutoNumber": "INTEGER",
    "Short Text": "TEXT",
    "Long Text": "TEXT",
    "Number": "INTEGER",
    "Decimal": "REAL",
    "Date/Time": "TEXT",
    "Yes/No": "INTEGER",
    "Currency": "NUMERIC",
    "Attachment": "BLOB",
}


def _validate_user_schema(schema_data):
    if not isinstance(schema_data, dict):
        return None, "Schema data must be an object."
    tables = schema_data.get("tables")
    relationships = schema_data.get("relationships")
    if (
        not isinstance(tables, list)
        or len(tables) > 200
        or not isinstance(relationships, list)
        or len(relationships) > 1000
    ):
        return None, "Schema must contain at most 200 tables and 1000 relationships."

    clean_tables = []
    table_ids = set()
    table_names = set()
    column_ids = {}
    for table in tables:
        if not isinstance(table, dict):
            return None, "Each table must be an object."
        table_id = table.get("id")
        name = table.get("name")
        columns = table.get("columns")
        x = table.get("x")
        y = table.get("y")
        if (
            not isinstance(table_id, str)
            or not table_id
            or len(table_id) > 64
            or table_id in table_ids
            or not isinstance(name, str)
            or not name.strip()
            or len(name.strip()) > 64
            or "\x00" in name
            or name.strip().casefold().startswith("sqlite_")
            or name.strip().casefold() in table_names
            or not isinstance(columns, list)
            or not 1 <= len(columns) <= 100
            or isinstance(x, bool)
            or not isinstance(x, (int, float))
            or not isfinite(x)
            or isinstance(y, bool)
            or not isinstance(y, (int, float))
            or not isfinite(y)
            or not 0 <= x <= 10000
            or not 0 <= y <= 10000
        ):
            return None, "A table has invalid, duplicate, or incomplete fields."

        table_ids.add(table_id)
        table_names.add(name.strip().casefold())
        clean_columns = []
        seen_column_ids = set()
        seen_column_names = set()
        for column in columns:
            if not isinstance(column, dict):
                return None, "Each field must be an object."
            column_id = column.get("id")
            column_name = column.get("name")
            data_type = column.get("type")
            primary_key = column.get("primaryKey")
            if (
                not isinstance(column_id, str)
                or not column_id
                or len(column_id) > 64
                or column_id in seen_column_ids
                or not isinstance(column_name, str)
                or not column_name.strip()
                or len(column_name.strip()) > 64
                or "\x00" in column_name
                or column_name.strip().casefold() in seen_column_names
                or not isinstance(data_type, str)
                or data_type not in SCHEMA_DATA_TYPES
                or not isinstance(primary_key, bool)
            ):
                return None, "A table field has invalid or incomplete values."
            seen_column_ids.add(column_id)
            seen_column_names.add(column_name.strip().casefold())
            clean_columns.append(
                {
                    "id": column_id,
                    "name": column_name.strip(),
                    "type": data_type,
                    "primaryKey": primary_key,
                }
            )
        column_ids[table_id] = seen_column_ids
        clean_tables.append(
            {
                "id": table_id,
                "name": name.strip(),
                "x": int(x),
                "y": int(y),
                "columns": clean_columns,
            }
        )

    clean_relationships = []
    relationship_ids = set()
    for relationship in relationships:
        if not isinstance(relationship, dict):
            return None, "Each relationship must be an object."
        relationship_id = relationship.get("id")
        source_table_id = relationship.get("sourceTableId")
        target_table_id = relationship.get("targetTableId")
        source_column_id = relationship.get("sourceColumnId")
        target_column_id = relationship.get("targetColumnId")
        color = relationship.get("color")
        if (
            not isinstance(relationship_id, str)
            or not relationship_id
            or len(relationship_id) > 64
            or relationship_id in relationship_ids
            or not isinstance(source_table_id, str)
            or not isinstance(target_table_id, str)
            or not isinstance(source_column_id, str)
            or not isinstance(target_column_id, str)
            or source_table_id not in table_ids
            or target_table_id not in table_ids
            or source_table_id == target_table_id
            or source_column_id not in column_ids.get(source_table_id, set())
            or target_column_id not in column_ids.get(target_table_id, set())
            or not isinstance(color, str)
            or color not in SCHEMA_LINE_COLORS
        ):
            return (
                None,
                "A relationship references an invalid table, field, or line color.",
            )
        relationship_ids.add(relationship_id)
        clean_relationships.append(
            {
                "id": relationship_id,
                "sourceTableId": source_table_id,
                "targetTableId": target_table_id,
                "sourceColumnId": source_column_id,
                "targetColumnId": target_column_id,
                "color": color,
            }
        )

    return {"tables": clean_tables, "relationships": clean_relationships}, None


def _quote_sqlite_identifier(value):
    return '"' + value.replace('"', '""') + '"'


def _create_schema_database(schema_data, source_database=None):
    target = sqlite3.connect(":memory:")
    source = None
    try:
        if source_database is not None:
            source = sqlite3.connect(":memory:")
            source.deserialize(source_database)

        for table in schema_data["tables"]:
            primary_keys = [
                column for column in table["columns"] if column["primaryKey"]
            ]
            definitions = []
            for column in table["columns"]:
                name = _quote_sqlite_identifier(column["name"])
                column_type = SCHEMA_SQLITE_TYPES[column["type"]]
                if len(primary_keys) == 1 and column is primary_keys[0]:
                    if column["type"] == "AutoNumber":
                        column_type += " PRIMARY KEY AUTOINCREMENT"
                    else:
                        column_type += " PRIMARY KEY"
                definitions.append(f"{name} {column_type}")
            if len(primary_keys) > 1:
                key_names = ", ".join(
                    _quote_sqlite_identifier(column["name"])
                    for column in primary_keys
                )
                definitions.append(f"PRIMARY KEY ({key_names})")
            target.execute(
                f"CREATE TABLE {_quote_sqlite_identifier(table['name'])} "
                f"({', '.join(definitions)})"
            )

        if source is not None:
            source_tables = {
                row[0].casefold(): row[0]
                for row in source.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            for table in schema_data["tables"]:
                source_table_name = source_tables.get(table["name"].casefold())
                if source_table_name is None:
                    continue
                source_columns = {
                    row[1].casefold(): row[1]
                    for row in source.execute(
                        f"PRAGMA table_info({_quote_sqlite_identifier(source_table_name)})"
                    )
                }
                common_columns = [
                    column["name"]
                    for column in table["columns"]
                    if column["name"].casefold() in source_columns
                ]
                if not common_columns:
                    continue
                target_names = ", ".join(
                    _quote_sqlite_identifier(name) for name in common_columns
                )
                source_names = ", ".join(
                    _quote_sqlite_identifier(source_columns[name.casefold()])
                    for name in common_columns
                )
                select_cursor = source.execute(
                    f"SELECT {source_names} "
                    f"FROM {_quote_sqlite_identifier(source_table_name)}"
                )
                placeholders = ", ".join("?" for _ in common_columns)
                insert_sql = (
                    f"INSERT INTO {_quote_sqlite_identifier(table['name'])} "
                    f"({target_names}) VALUES ({placeholders})"
                )
                while rows := select_cursor.fetchmany(500):
                    target.executemany(insert_sql, rows)

        target.commit()
        return target.serialize()
    finally:
        if source is not None:
            source.close()
        target.close()


def _schema_from_sqlite(database_data):
    connection = sqlite3.connect(":memory:")
    try:
        connection.deserialize(database_data)
        integrity = connection.execute("PRAGMA quick_check(1)").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise ValueError("The SQLite database did not pass its integrity check.")

        raw_tables = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        if len(raw_tables) > 200:
            raise ValueError("The SQLite file contains more than 200 tables.")

        tables = []
        table_ids = {}
        column_ids = {}
        next_id = 1
        for table_index, (table_name,) in enumerate(raw_tables):
            column_rows = connection.execute(
                f"PRAGMA table_info({_quote_sqlite_identifier(table_name)})"
            ).fetchall()
            if not 1 <= len(column_rows) <= 100:
                raise ValueError(
                    f"Table '{table_name}' must have between 1 and 100 fields."
                )
            table_id = str(next_id)
            next_id += 1
            table_ids[table_name.casefold()] = table_id
            columns = []
            table_column_ids = {}
            for _, column_name, declared_type, _, _, primary_key in column_rows:
                column_id = str(next_id)
                next_id += 1
                table_column_ids[column_name.casefold()] = column_id
                type_name = (declared_type or "").upper()
                if "INT" in type_name:
                    data_type = "AutoNumber" if primary_key else "Number"
                elif "BOOL" in type_name:
                    data_type = "Yes/No"
                elif "DATE" in type_name or "TIME" in type_name:
                    data_type = "Date/Time"
                elif any(token in type_name for token in ("REAL", "FLOA", "DOUB", "DEC", "NUM")):
                    data_type = "Decimal"
                elif "BLOB" in type_name:
                    data_type = "Attachment"
                else:
                    data_type = "Short Text"
                columns.append(
                    {
                        "id": column_id,
                        "name": column_name,
                        "type": data_type,
                        "primaryKey": bool(primary_key),
                    }
                )
            column_ids[table_name.casefold()] = table_column_ids
            tables.append(
                {
                    "id": table_id,
                    "name": table_name,
                    "x": 24 + (table_index % 3) * 340,
                    "y": 24 + (table_index // 3) * 280,
                    "columns": columns,
                }
            )

        relationships = []
        for table_name, in raw_tables:
            for foreign_key in connection.execute(
                f"PRAGMA foreign_key_list({_quote_sqlite_identifier(table_name)})"
            ):
                target_table = foreign_key[2]
                source_column = foreign_key[3]
                target_column = foreign_key[4]
                source_table_id = table_ids.get(table_name.casefold())
                target_table_id = table_ids.get(target_table.casefold())
                source_column_id = column_ids.get(table_name.casefold(), {}).get(
                    source_column.casefold()
                )
                target_column_id = column_ids.get(target_table.casefold(), {}).get(
                    target_column.casefold()
                )
                if (
                    source_table_id
                    and target_table_id
                    and source_column_id
                    and target_column_id
                ):
                    relationships.append(
                        {
                            "id": str(next_id),
                            "sourceTableId": source_table_id,
                            "targetTableId": target_table_id,
                            "sourceColumnId": source_column_id,
                            "targetColumnId": target_column_id,
                            "color": "#2878b5",
                        }
                    )
                    next_id += 1
                    if len(relationships) > 1000:
                        raise ValueError(
                            "The SQLite file contains more than 1000 relationships."
                        )

        schema, error = _validate_user_schema(
            {"tables": tables, "relationships": relationships}
        )
        if error:
            raise ValueError(error)
        return schema
    finally:
        connection.close()


def _schema_database_summary(database):
    tables = database.schema_data["tables"]
    return {
        "id": database.schema_database_id,
        "name": database.schema_name,
        "file_name": database.file_name,
        "table_count": len(tables),
        "column_count": sum(len(table["columns"]) for table in tables),
        "relationship_count": len(database.schema_data["relationships"]),
        "updated_at": database.updated_at.isoformat(),
    }


def _schema_file_name(name):
    slug = secure_filename(name.replace(" ", "-")) or "schema"
    return f"{slug[:245]}.sqlite3"


def _schema_name_error(name):
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 128:
        return "Database name must be between 1 and 128 characters."
    return None


def _migrate_legacy_schema(user_id):
    legacy_schema = UserSchema.query.filter_by(user_id=user_id).first()
    if legacy_schema is None:
        return
    clean_schema, error = _validate_user_schema(legacy_schema.schema_data)
    if error:
        raise ValueError(f"Unable to migrate the saved schema: {error}")
    name = "My Database"
    suffix = 2
    while UserSchemaDatabase.query.filter_by(
        user_id=user_id,
        schema_name=name,
    ).first():
        name = f"My Database (legacy {suffix})"
        suffix += 1
    database = UserSchemaDatabase(
        user_id=user_id,
        schema_name=name,
        file_name=_schema_file_name(name),
        database_data=_create_schema_database(clean_schema),
        schema_data=clean_schema,
    )
    db.session.add(database)
    db.session.delete(legacy_schema)
    db.session.commit()


def _open_readonly_schema(database_data):
    connection = sqlite3.connect(":memory:")
    connection.deserialize(database_data)
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA trusted_schema = OFF")
    connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_SCHEMA_QUERY_RESULT_BYTES)
    connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, MAX_SCHEMA_QUERY_LENGTH)
    connection.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, 100)
    connection.set_progress_handler(lambda: 1, MAX_SCHEMA_QUERY_STEPS)
    denied_actions = {
        sqlite3.SQLITE_INSERT,
        sqlite3.SQLITE_UPDATE,
        sqlite3.SQLITE_DELETE,
        sqlite3.SQLITE_CREATE_INDEX,
        sqlite3.SQLITE_CREATE_TABLE,
        sqlite3.SQLITE_CREATE_TEMP_INDEX,
        sqlite3.SQLITE_CREATE_TEMP_TABLE,
        sqlite3.SQLITE_CREATE_TEMP_TRIGGER,
        sqlite3.SQLITE_CREATE_TEMP_VIEW,
        sqlite3.SQLITE_CREATE_TRIGGER,
        sqlite3.SQLITE_CREATE_VIEW,
        sqlite3.SQLITE_CREATE_VTABLE,
        sqlite3.SQLITE_DROP_INDEX,
        sqlite3.SQLITE_DROP_TABLE,
        sqlite3.SQLITE_DROP_TEMP_INDEX,
        sqlite3.SQLITE_DROP_TEMP_TABLE,
        sqlite3.SQLITE_DROP_TEMP_TRIGGER,
        sqlite3.SQLITE_DROP_TEMP_VIEW,
        sqlite3.SQLITE_DROP_TRIGGER,
        sqlite3.SQLITE_DROP_VIEW,
        sqlite3.SQLITE_DROP_VTABLE,
        sqlite3.SQLITE_ALTER_TABLE,
        sqlite3.SQLITE_ATTACH,
        sqlite3.SQLITE_DETACH,
        sqlite3.SQLITE_PRAGMA,
        sqlite3.SQLITE_TRANSACTION,
        sqlite3.SQLITE_SAVEPOINT,
        sqlite3.SQLITE_ANALYZE,
        sqlite3.SQLITE_REINDEX,
    }

    def authorize(action, first_argument, second_argument, _, __):
        if action in denied_actions:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_FUNCTION:
            function_name = (second_argument or first_argument or "").casefold()
            if function_name in {"load_extension", "readfile", "writefile"}:
                return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    connection.set_authorizer(authorize)
    return connection


@auth_bp.route("/api/schema", methods=["GET", "POST"])
@login_required
@limiter.limit("30 per minute")
def User_Schema():
    if request.method == "GET":
        try:
            _migrate_legacy_schema(current_user.user_id)
        except ValueError as error:
            return jsonify(error=str(error)), 409
        databases = (
            UserSchemaDatabase.query.filter_by(user_id=current_user.user_id)
            .order_by(UserSchemaDatabase.updated_at.desc())
            .all()
        )
        return jsonify(databases=[_schema_database_summary(item) for item in databases])

    if not request.is_json:
        return jsonify(error="A JSON request is required."), 415
    if len(request.get_data(cache=True)) > 1_000_000:
        return jsonify(error="Schema data must be smaller than 1 MB."), 413
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="The request body must be valid JSON."), 400
    name = payload.get("name")
    name_error = _schema_name_error(name)
    if name_error:
        return jsonify(error=name_error), 400
    clean_schema, error = _validate_user_schema(payload.get("schema"))
    if error:
        return jsonify(error=error), 400
    if UserSchemaDatabase.query.filter(
        UserSchemaDatabase.user_id == current_user.user_id,
        func.lower(UserSchemaDatabase.schema_name) == name.strip().lower(),
    ).first():
        return jsonify(error="A database with that name already exists."), 409
    try:
        database_data = _create_schema_database(clean_schema)
    except sqlite3.DatabaseError as error:
        return jsonify(error=f"Could not create the SQLite database: {error}"), 400
    now = datetime.now(timezone.utc)
    database = UserSchemaDatabase(
        user_id=current_user.user_id,
        schema_name=name.strip(),
        file_name=_schema_file_name(name.strip()),
        database_data=database_data,
        schema_data=clean_schema,
        created_at=now,
        updated_at=now,
    )
    db.session.add(database)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="A database with that name already exists."), 409
    return jsonify(database=_schema_database_summary(database)), 201


@auth_bp.route("/api/schema/import", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def Import_Schema_Database():
    if (
        request.content_length is not None
        and request.content_length > MAX_SCHEMA_FILE_BYTES + 1024 * 1024
    ):
        return jsonify(error="Database files must be 25 MB or smaller."), 413
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify(error="Choose a SQLite database file to load."), 400

    file_name = secure_filename(upload.filename)
    if len(file_name) > 255:
        return jsonify(error="The database filename is too long."), 400
    extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if extension not in SCHEMA_FILE_EXTENSIONS:
        return jsonify(error="Only .sqlite3, .sqlite, and .db files are accepted."), 415

    database_data = upload.stream.read(MAX_SCHEMA_FILE_BYTES + 1)
    if not database_data:
        return jsonify(error="The selected database file is empty."), 400
    if len(database_data) > MAX_SCHEMA_FILE_BYTES:
        return jsonify(error="Database files must be 25 MB or smaller."), 413
    if not database_data.startswith(b"SQLite format 3\x00"):
        return jsonify(error="The selected file is not a SQLite database."), 400

    try:
        schema_data = _schema_from_sqlite(database_data)
    except (sqlite3.DatabaseError, ValueError) as error:
        return jsonify(error=str(error)), 400

    default_name = file_name.rsplit(".", 1)[0].replace("-", " ").replace("_", " ")
    name = request.form.get("name", "").strip() or default_name
    name_error = _schema_name_error(name)
    if name_error:
        return jsonify(error=name_error), 400
    if UserSchemaDatabase.query.filter(
        UserSchemaDatabase.user_id == current_user.user_id,
        func.lower(UserSchemaDatabase.schema_name) == name.lower(),
    ).first():
        return jsonify(error="A database with that name already exists."), 409

    database = UserSchemaDatabase(
        user_id=current_user.user_id,
        schema_name=name,
        file_name=file_name,
        database_data=database_data,
        schema_data=schema_data,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.session.add(database)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="A database with that name already exists."), 409
    return jsonify(database=_schema_database_summary(database)), 201


@auth_bp.route("/api/schema/<int:schema_id>", methods=["GET", "PUT", "DELETE"])
@login_required
@limiter.limit("30 per minute")
def User_Schema_Database(schema_id):
    database = UserSchemaDatabase.query.filter_by(
        schema_database_id=schema_id,
        user_id=current_user.user_id,
    ).first_or_404()

    if request.method == "GET":
        return jsonify(
            database=_schema_database_summary(database),
            schema=database.schema_data,
        )
    if request.method == "DELETE":
        db.session.delete(database)
        db.session.commit()
        return jsonify(deleted=True)

    if not request.is_json:
        return jsonify(error="A JSON request is required."), 415
    if len(request.get_data(cache=True)) > 1_000_000:
        return jsonify(error="Schema data must be smaller than 1 MB."), 413
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="The request body must be valid JSON."), 400
    name = payload.get("name", database.schema_name)
    name_error = _schema_name_error(name)
    if name_error:
        return jsonify(error=name_error), 400
    clean_schema, error = _validate_user_schema(payload.get("schema"))
    if error:
        return jsonify(error=error), 400
    if UserSchemaDatabase.query.filter(
        UserSchemaDatabase.user_id == current_user.user_id,
        UserSchemaDatabase.schema_database_id != schema_id,
        func.lower(UserSchemaDatabase.schema_name) == name.strip().lower(),
    ).first():
        return jsonify(error="A database with that name already exists."), 409

    try:
        updated_data = _create_schema_database(
            clean_schema,
            source_database=database.database_data,
        )
    except sqlite3.DatabaseError:
        return jsonify(error="Schema edits could not preserve the existing database."), 400

    database.schema_name = name.strip()
    database.file_name = _schema_file_name(name.strip())
    database.database_data = updated_data
    database.schema_data = clean_schema
    database.updated_at = datetime.now(timezone.utc)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="A database with that name already exists."), 409
    return jsonify(
        saved=True,
        database=_schema_database_summary(database),
        metadata={
            "table_count": len(clean_schema["tables"]),
            "column_count": sum(
                len(table["columns"]) for table in clean_schema["tables"]
            ),
            "relationship_count": len(clean_schema["relationships"]),
        },
    )


@auth_bp.route("/api/schema/<int:schema_id>/query", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def Query_Schema_Database(schema_id):
    database = UserSchemaDatabase.query.filter_by(
        schema_database_id=schema_id,
        user_id=current_user.user_id,
    ).first_or_404()
    if not request.is_json:
        return jsonify(error="A JSON request is required."), 415
    if (
        request.content_length is not None
        and request.content_length > MAX_SCHEMA_QUERY_LENGTH + 2048
    ):
        return jsonify(error="Queries must be 10,000 characters or fewer."), 413
    payload = request.get_json(silent=True)
    query = payload.get("query") if isinstance(payload, dict) else None
    if not isinstance(query, str) or not query.strip():
        return jsonify(error="Enter a read-only SQL query."), 400
    if len(query) > MAX_SCHEMA_QUERY_LENGTH:
        return jsonify(error="Queries must be 10,000 characters or fewer."), 413

    connection = None
    try:
        connection = _open_readonly_schema(database.database_data)
        cursor = connection.execute(query)
        if cursor.description is None:
            return jsonify(error="Only read-only queries that return rows are allowed."), 400
        rows = cursor.fetchmany(MAX_SCHEMA_QUERY_ROWS + 1)
        truncated = len(rows) > MAX_SCHEMA_QUERY_ROWS
        rows = rows[:MAX_SCHEMA_QUERY_ROWS]
        result_rows = []
        for row in rows:
            result = []
            for value in row:
                if isinstance(value, bytes):
                    result.append(
                        {
                            "blob_hex": value[:128].hex(),
                            "truncated": len(value) > 128,
                        }
                    )
                elif isinstance(value, str) and len(value) > 1024:
                    result.append(value[:1024] + "...")
                else:
                    result.append(value)
            result_rows.append(result)
        return jsonify(
            columns=[column[0] for column in cursor.description],
            rows=result_rows,
            truncated=truncated,
        )
    except sqlite3.OperationalError as error:
        if "interrupted" in str(error).casefold():
            return jsonify(error="The query exceeded the execution limit."), 422
        return jsonify(error=str(error)), 400
    except sqlite3.DatabaseError as error:
        return jsonify(error=str(error)), 400
    finally:
        if connection is not None:
            connection.close()
