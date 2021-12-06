from flask import render_template
from views import app

@app.errorhandler(400)
def handle_404(error):
    return render_template('404.html'), 400

@app.errorhandler(404)
def handle_404(error):
    return render_template('404.html'), 404

@app.errorhandler(403)
def handle_403(error):
    return render_template('500.html'), 403

@app.errorhandler(500)
def handle_500(error):
    return render_template('500.html'), 500