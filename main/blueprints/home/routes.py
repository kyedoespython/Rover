from datetime import datetime, timezone

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from main.extensions import db, limiter
from main.models.user import Tickets as SupportTicket

from . import home_bp


@home_bp.route("/")
def Rover_Home_Page():
    return render_template("Home/Home.html")


@home_bp.route("/Rover/Support")
def Contact():
    return render_template("Contact/Contact.html")


@home_bp.route("/Tickets/Rover", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def Tickets():
    ticket_type = request.form.get("ticketType", "")
    ticket_name = request.form.get("ticketName", "").strip()
    ticket_content = request.form.get("TicketContent", "").strip()
    if ticket_type not in {"bug", "recommendation", "question"}:
        flash("Choose a valid ticket type.", "error")
        return render_template("Contact/Contact.html"), 400
    if not ticket_name or len(ticket_name) > 64 or not ticket_content or len(ticket_content) > 512:
        flash("Enter a ticket name (up to 64 characters) and description (up to 512 characters).", "error")
        return render_template("Contact/Contact.html"), 400

    ticket = SupportTicket(
        user_id=current_user.user_id,
        ticket_type=ticket_type,
        ticket_name=ticket_name,
        ticket_content=ticket_content,
        ticket_created_at=datetime.now(timezone.utc),
    )
    try:
        db.session.add(ticket)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Unable to save support ticket")
        flash("Your ticket could not be saved. Please try again.", "error")
        return render_template("Contact/Contact.html"), 503

    flash(f"Ticket #{ticket.ticket_id} submitted.", "success")
    return redirect(url_for("home.Contact"))
