from functools import wraps
from flask import g, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse, urljoin

def payment_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.credits < 1:
            flash('You must add more credits to access this page', 'negative')
            return redirect(url_for('userbp.pay', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def already_signed_in(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated:
            return redirect(url_for('userbp.account'))
        return f(*args, **kwargs)
    return decorated_function
