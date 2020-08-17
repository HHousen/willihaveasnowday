from flask import (Blueprint, render_template, redirect, url_for,
                   abort, flash, request, current_app)
from flask_login import login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer
from app import models, app
from app.extensions import db, login_manager
from app.forms import user as user_forms
from app.toolbox import email
from app.decorators import already_signed_in

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
def load_user(email):
    return models.User.query.filter(models.User.email == email).first()

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
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            phone=form.phone.data,
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
        email.send(user.email, subject, html, from_email=current_app.config['REGISTER_FROM_EMAIL'])
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
                login_user(user)
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
    return render_template('user/account.html', title='Account')


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
            email.send(user.email, subject, html, from_email=current_app.config['REGISTER_FROM_EMAIL'])
            # Send back to the home page
            flash('Check your emails to reset your password', 'positive')
            return redirect(url_for('index'))
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

@userbp.route('/pay', methods=['GET', 'POST'])
@login_required
def pay():
    plan_form = user_forms.Plan()
    credits_form = user_forms.Credits()
    if credits_form.validate_on_submit():
        if current_user.customer_id is None:
            try:
                customer = stripe.Customer.create(email=current_user.email, source=request.form['stripeToken'])
                current_user.customer_id = customer.id
            except stripe.error.StripeError:
                return render_template('error.html', message='Something went wrong with the payment.')
        try:
            amount = credits_form.credits.data * 100
            charge = stripe.Charge.create(
                customer=current_user.customer_id,
                amount=amount,
                currency='usd',
                description='Service Plan'
            )
            current_user.credits += credits_form.credits.data
            db.session.commit()
            flash('Success! You bought {} credits.'.format(credits_form.credits.data), 'positive')
            return redirect(url_for('userbp.account'))
        except stripe.error.StripeError:
            return render_template('error.html', message='Something went wrong with the payment.')

    if plan_form.validate_on_submit():
        plan = plan_form.plan.data
        if current_user.customer_id is None:
            try:
                customer = stripe.Customer.create(email=current_user.email, source=request.form['stripeToken'])
                current_user.customer_id = customer.id
            except stripe.error.StripeError:
                return render_template('error.html', message='Something went wrong with the payment.')
        try:
            if plan == "individual":
                amount = 100 * 100
                charge = stripe.Charge.create(
                    customer=current_user.customer_id,
                    amount=amount,
                    currency='usd',
                    description='Service Plan'
                )
                current_user.credits += 100
                db.session.commit()
                flash('Success! You bought the individual plan.', 'positive')
                return redirect(url_for('userbp.account'))
            elif plan == "enterprise":
                amount = 1000 * 100
                charge = stripe.Charge.create(
                    customer=current_user.customer_id,
                    amount=amount,
                    currency='usd',
                    description='Service Plan'
                )
                current_user.credits += 1000
                db.session.commit()
                flash('Success! You bought the enterprise plan.', 'positive')
                return redirect(url_for('userbp.account'))
            else:
                return render_template('error.html', message='Something went wrong with the payment.')
        except stripe.error.StripeError:
            return render_template('error.html', message='Something went wrong with the payment.')
    return render_template('user/buy.html', plan_form=plan_form, credits_form=credits_form, key=stripe_keys['publishable_key'], email=current_user.email)

@userbp.route('/charge', methods=['POST'])
@login_required
def charge():
    form = user_forms.Plan()
    if form.validate_on_submit():
        plan = form.plan.data
        if current_user.customer_id is None:
            try:
                customer = stripe.Customer.create(email=current_user.email, source=request.form['stripeToken'])
                current_user.customer_id = customer.id
            except stripe.error.StripeError:
                return render_template('error.html', message='Something went wrong with the payment.')
        
        if plan == "credits":
            try:
                amount = form.credits.data * 100
                charge = stripe.Charge.create(
                    customer=current_user.customer_id,
                    amount=amount,
                    currency='usd',
                    description='Service Plan'
                )
                current_user.credits += form.credits.data
                db.session.commit()
                flash('Success! You bought {} credits.'.format(form.credits.data), 'positive')
                return redirect(url_for('userbp.account'))
            except stripe.error.StripeError:
                return render_template('error.html', message='Something went wrong with the payment.')
        elif plan == "individual":
            amount = 100 * 100
            charge = stripe.Charge.create(
                customer=current_user.customer_id,
                amount=amount,
                currency='usd',
                description='Service Plan'
            )
            current_user.credits += 100
            db.session.commit()
            flash('Success! You bought the individual plan.', 'positive')
            return redirect(url_for('userbp.account'))
        elif plan == "enterprise":
            amount = 1000 * 100
            charge = stripe.Charge.create(
                customer=current_user.customer_id,
                amount=amount,
                currency='usd',
                description='Service Plan'
            )
            current_user.credits += 1000
            db.session.commit()
            flash('Success! You bought the enterprise plan.', 'positive')
            return redirect(url_for('userbp.account'))
        else:
            return render_template('error.html', message='Something went wrong with the payment.')
    return render_template('error.html', message='Something went wrong with the payment.')


@userbp.route('/api/payFail', methods=['POST', 'GET'])
def payFail():
	content = request.json
	stripe_email = content['data']['object']['email']
	user = models.User.query.filter_by(email=stripe_email).first()
	if user is not None: 
		user.credits -= 5
		db.session.commit()
		# do anything else, like execute shell command to disable user's service on your app
	return "Response: User with associated email " + str(stripe_email) + " updated on our end (payment failure)."

@userbp.route('/api/paySuccess', methods=['POST', 'GET'])
def paySuccess():
	content = request.json
	stripe_email = content['data']['object']['email']
	user = models.User.query.filter_by(email=stripe_email).first()
	#if user is not None: 
		#user.paid = 1
		#db.session.commit()
		# do anything else on payment success, maybe send a thank you email or update more db fields?
	return "Response: User with associated email " + str(stripe_email) + " updated on our end (paid)."