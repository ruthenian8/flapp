from flask import render_template
from views import application


@application.errorhandler(400)
def handle_404(error):
    return render_template("404.html"), 400


@application.errorhandler(404)
def handle_404(error):
    return render_template("404.html"), 404


@application.errorhandler(403)
def handle_403(error):
    return render_template("500.html"), 403


@application.errorhandler(500)
def handle_500(error):
    return render_template("500.html"), 500
