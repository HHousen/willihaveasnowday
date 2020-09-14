from flask import (Blueprint, render_template, redirect, url_for,
                   abort, flash, request, current_app)
from flask_login import login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer
import json
import uuid
from app import models, app
from app.extensions import db, login_manager, limiter
from app.forms import user as user_forms
from app.toolbox import email
from app.decorators import already_signed_in

from sendgrid.helpers.mail import From

# Setup Stripe integration
import stripe
import json
from json import dumps

stripe_keys = {
	'secret_key': "secret_key",
	'publishable_key': "publishable_key"
}

stripe.api_key = stripe_keys['secret_key']

@login_manager.user_loader
def load_user(user_id):
    return models.User.query.filter(models.User.alt_id == user_id).first()

# Create a user blueprint
userbp = Blueprint('userbp', __name__, url_prefix='/user')

@userbp.route('/signup', methods=['GET', 'POST'])
@already_signed_in
def signup():
    # Serializer for generating random tokens
    ts = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    form = user_forms.SignUp()
    if form.validate_on_submit():
        user = models.User(
            username=form.username.data,
            email=form.email.data,
            confirmation=current_app.config['AUTO_CONFIRM'],
            password=form.password.data
        )
        # Insert the user in the database
        db.session.add(user)
        db.session.commit()
        # Subject of the confirmation email
        subject = 'Please confirm your email address.'
        # Generate a random token
        token = ts.dumps(user.email, salt=current_app.config['EMAIL_CONFIRM_SALT'])
        # Build a confirm link with token
        confirmUrl = url_for('userbp.confirm', token=token, _external=True)
        # Render an HTML template to send by email
        html = render_template('email/confirm.html', confirm_url=confirmUrl)
        # Send the email to user
        email.send(user.email, subject, html, from_email=From(email=current_app.config['REGISTER_FROM_EMAIL'], name="Accounts @ WilliHaveASnowDay.com"))
        # Send back to the home page
        flash('Check your email to confirm your email address', 'positive')
        return redirect(url_for('mainbp.index'))
    return render_template('user/signup.html', form=form, title='Sign up')


@userbp.route('/confirm/<token>', methods=['GET', 'POST'])
def confirm(token):
    # Serializer for generating random tokens
    ts = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = ts.loads(token, salt=current_app.config['EMAIL_CONFIRM_SALT'], max_age=86400)
    # The token can either expire or be invalid
    except:
        abort(404)
    # Get the user from the database
    user = models.User.query.filter_by(email=email).first()
    # The user has confirmed his or her email address
    user.confirmation = True
    # Update the database with the user
    db.session.commit()
    # Send to the signin page
    flash('Your email address has been confirmed, you can sign in', 'positive')
    return redirect(url_for('userbp.signin'))


@userbp.route('/signin', methods=['GET', 'POST'])
@already_signed_in
def signin():
    form = user_forms.Login()
    if form.validate_on_submit():
        user = models.User.query.filter_by(email=form.email.data).first()
        # Check the user exists
        if user is not None:
            # Check the password is correct
            if user.check_password(form.password.data):
                login_user(user, remember=form.remember.data)
                # Send back to the home page
                flash('Succesfully signed in', 'positive')
                return redirect(url_for('mainbp.index'))
            else:
                flash('The password you have entered is wrong', 'negative')
                return redirect(url_for('userbp.signin'))
        else:
            flash('Unknown email address', 'negative')
            return redirect(url_for('userbp.signin'))
    return render_template('user/signin.html', form=form, title='Sign in')


@userbp.route('/signout')
def signout():
    logout_user()
    flash('Succesfully signed out', 'positive')
    return redirect(url_for('mainbp.index'))


@userbp.route('/account')
@login_required
def account():
    change_password_form = user_forms.ChangePassword()
    change_username_form = user_forms.ChangeUsername()
    return render_template('user/account.html', receive_improve_emails=current_user.receive_improve_emails, change_password_form=change_password_form, change_username_form=change_username_form, title='Account')


@userbp.route('/change-password', methods=['POST'])
@login_required
@limiter.limit("1 per minute")
def change_password():
    form = user_forms.ChangePassword()
    
    if form.validate_on_submit():
        if current_user.check_password(form.current_password.data):
            current_user.password = form.new_password.data
            current_user.alt_id = str(uuid.uuid4())
            db.session.commit()
            logout_user()

            return json.dumps('Your password has been changed, you can sign in'), 200
        else:
            return json.dumps('The current password you have entered is wrong'), 401

    return json.dumps(form.errors), 400


@userbp.route('/change-username', methods=['POST'])
@login_required
@limiter.limit("1 per hour")
def change_username():
    form = user_forms.ChangeUsername()
    
    if form.validate_on_submit():
        current_user.username = form.new_username.data
        db.session.commit()
        return json.dumps('Your username has been changed'), 200

    return json.dumps(form.errors), 400

@userbp.route('/improve-emails-toggle', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def toggle_improve_emails():
    if request.json is not None:
        switch_state = request.json["state"]
        if switch_state == 1:
            current_user.receive_improve_emails = True
            db.session.commit()
            return json.dumps(1)
        elif switch_state == 0:
            current_user.receive_improve_emails = False
            db.session.commit()
            return json.dumps(0)
        else:
            return json.dumps("Invalid checkbox state"), 400
    else:
        return json.dumps("Invalid data submitted"), 400


@userbp.route('/forgot', methods=['GET', 'POST'])
def forgot():
    # Serializer for generating random tokens
    ts = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    form = user_forms.Forgot()
    if form.validate_on_submit():
        user = models.User.query.filter_by(email=form.email.data).first()
        # Check the user exists
        if user is not None:
            # Subject of the confirmation email
            subject = 'Reset your password.'
            # Generate a random token
            token = ts.dumps(user.email, salt=current_app.config['PASSWORD_RESET_SALT'])
            # Build a reset link with token
            resetUrl = url_for('userbp.reset', token=token, _external=True)
            # Render an HTML template to send by email
            html = render_template('email/reset.html', reset_url=resetUrl)
            # Send the email to user
            email.send(user.email, subject, html, from_email=From(email=current_app.config['REGISTER_FROM_EMAIL'], name="Accounts @ WilliHaveASnowDay.com"))
            # Send back to the home page
            flash('Check your emails to reset your password', 'positive')
            return redirect(url_for('mainbp.index'))
        else:
            flash('Unknown email address', 'negative')
            return redirect(url_for('userbp.forgot'))
    return render_template('user/forgot.html', form=form)


@userbp.route('/reset/<token>', methods=['GET', 'POST'])
def reset(token):
    # Serializer for generating random tokens
    ts = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = ts.loads(token, salt=current_app.config['PASSWORD_RESET_SALT'], max_age=86400)
    # The token can either expire or be invalid
    except:
        abort(404)
    form = user_forms.Reset()
    if form.validate_on_submit():
        user = models.User.query.filter_by(email=email).first()
        # Check the user exists
        if user is not None:
            user.password = form.password.data
            # Update the database with the user
            db.session.commit()
            # Send to the signin page
            flash('Your password has been reset, you can sign in', 'positive')
            return redirect(url_for('userbp.signin'))
        else:
            flash('Unknown email address', 'negative')
            return redirect(url_for('userbp.forgot'))
    return render_template('user/reset.html', form=form, token=token)
