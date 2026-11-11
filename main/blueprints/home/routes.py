from flask import render_template, request
from flask_login import login_required

from . import home_bp


@home_bp.route("/")
def Rover_Home_Page():
    return render_template("Home/Home.html")


@home_bp.route("/Rover/Support")
def Contact():
    return render_template("Contact/Contact.html")


@home_bp.route("/Tickets/Rover", methods=["POST", "GET"])
@login_required
def Tickets():
    ticketName = request.form.get("ticketName").strip()
    ticket_content = request.form.get("TicketContent")
