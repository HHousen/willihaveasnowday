import json
import uuid
from flask import render_template, session, jsonify, Blueprint, flash, abort, current_app
from flask_login import current_user
from itsdangerous import URLSafeTimedSerializer
from app import app
from app.models import PreditionReport, UnauthUser, UnauthUserPredictions, UserPredictions, User
import random
import datetime as dt
from app.forms import predict as predict_forms
from app.forms import improve as help_forms
from app.forms import contact as contact_forms
from app.toolbox import email
from app.extensions import db, limiter
from app.decorators import *

from sendgrid.helpers.mail import To, Substitution, Personalization, From

from app.views import noaa_api

from uszipcode import SearchEngine

import atexit
import time
from apscheduler.schedulers.background import BackgroundScheduler

def create_follow_up_email(prediction, user, ts, extra):
    start_token = str(extra) + "-" + str(prediction.id) + "-" + str(user.id)
    yes_token = ts.dumps(start_token + "-1", salt=current_app.config['SNOWDAY_STATUS_SALT'])
    yes_url = url_for('mainbp.snowday_status', token=yes_token, _external=True)
    no_token = ts.dumps(start_token + "-0", salt=current_app.config['SNOWDAY_STATUS_SALT'])
    no_url = url_for('mainbp.snowday_status', token=no_token, _external=True)

    p = Personalization()
    to_object = To(email=user.email, substitutions=[
        Substitution('((yes_url))', yes_url, p),
        Substitution('((no_url))', no_url, p),
        Substitution('((zip_code))', prediction.zip_code)
    ])
    p.add_to(to_object)

    return p

def send_follow_up_emails():
    ts = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    
    today = dt.datetime.today().replace(hour=12, minute=0, second=0).strftime('%Y-%m-%d %H:%M:%S')
    yesterday = (dt.datetime.now() - dt.timedelta(1)).replace(hour=12, minute=0, second=0).strftime('%Y-%m-%d %H:%M:%S')
    
    to_emails = []
    for prediction in PreditionReport.query.filter(PreditionReport.created_at.between(yesterday, today), not PreditionReport.emailed):
        for assoc in prediction.users_ids:
            user = assoc.user_rel
            p = create_follow_up_email(prediction, user, ts, extra="full")
            to_emails.append(p)
        for assoc in prediction.unauth_users_ids:
            user = assoc.unauth_user_rel
            p = create_follow_up_email(prediction, user, ts, extra="un")
            to_emails.append(p)
        
        prediction.emailed = True
        db.session.commit()
    
    html = render_template('email/improve.html')
    email.send(
        recipient=None,
        personalizations=to_emails,
        subject="Was our prediction right? - WillIHaveASnowDay.com",
        body=html,
        from_email=From(email=current_app.config['DEFAULT_FROM_EMAIL'], name="Help Improve @ WilliHaveASnowDay.com"),
        sendgrid_only=True
    )


scheduler = BackgroundScheduler()
scheduler.add_job(func=send_follow_up_emails, trigger="cron", hour=15, minute=58)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

mainbp = Blueprint('mainbp', __name__)

@mainbp.route('/')
@mainbp.route('/index', methods=['GET', 'POST'])
def index():
    if not current_user.is_authenticated:
        if 'id' not in session:
            session['id'] = str(uuid.uuid4())
    predict_form = predict_forms.Predict()
    help_form = help_forms.Help()
    
    return render_template('index.html', predict_form=predict_form, help_form=help_form, signed_in=current_user.is_authenticated)

@mainbp.route('/about')
def about():
    return render_template('about.html', title="About")

@mainbp.route('/reverse-geocode', methods=['POST'])
@limiter.limit("10 per minute")
def reverse_geocode():
    if request.content_type == "application/json":
        latitude = request.json["latitude"]
        longitude = request.json["longitude"]
        
        search = SearchEngine(simple_zipcode=True)
        result_obj = search.by_coordinates(lat=latitude, lng=longitude, radius=10, returns=1)[0]
        return result_obj.zipcode
    
    return "Incorrect data type submitted", 400

@mainbp.route('/predict', methods=['POST'])
@limiter.limit("6 per minute")
def predict():
    if not current_user.is_authenticated:
        unauth_user = UnauthUser.query.filter_by(uuid=session['id']).first()
        if not unauth_user:
            unauth_user = UnauthUser(uuid=session['id'])
    
    form = predict_forms.Predict()
    
    if form.validate_on_submit():
        last_prediction = PreditionReport.get_recent_prediction(form.zip_code.data)
        if last_prediction is not None:
            if current_user.is_authenticated:
                last_prediction_associated_user_ids = [x.user_rel.id for x in last_prediction.users_ids]
                if current_user.id not in last_prediction_associated_user_ids:
                    user_predictions = UserPredictions()
                    user_predictions.user_rel = current_user
                    user_predictions.report = last_prediction
                    last_prediction.users_ids.append(user_predictions)
                    db.session.commit()
            else:
                last_prediction_associated_unauthuser_ids = [x.unauth_user_rel.id for x in last_prediction.unauth_users_ids]
                if unauth_user.id not in last_prediction_associated_unauthuser_ids:
                    user_predictions = UnauthUserPredictions()
                    user_predictions.unauth_user_rel = unauth_user
                    user_predictions.report = last_prediction
                    last_prediction.unauth_users_ids.append(user_predictions)
                    db.session.commit()
            model_prediction = json.loads(last_prediction.model_prediction)
            weather_text = json.loads(last_prediction.weather_text)
            return json.dumps({**model_prediction, "weather_text": weather_text})
        
        try:
            weather_data, text_weather = noaa_api.get_weather(form.zip_code.data)
        except ValueError as e:
            return json.dumps({"zip_code": ["Invalid zip code"]}), 400

        prediction = {"percentages": [random.randint(1,100), random.randint(1,100), random.randint(1,100)]}

        period_text_descriptions = noaa_api.generate_text_descriptions(text_weather)
        period_text_descriptions = noaa_api.process_text_descriptions(period_text_descriptions)

        report = PreditionReport(
            zip_code=form.zip_code.data,
            num_snowdays=form.num_snowdays.data,
            weather_info=0,
            model_prediction=json.dumps(prediction),
            weather_text=json.dumps(period_text_descriptions),
        )
        if current_user.is_authenticated:
            user_predictions = UserPredictions()
            user_predictions.user_rel = current_user
            report.users_ids.append(user_predictions)
        else:
            user_predictions = UnauthUserPredictions()
            user_predictions.unauth_user_rel = unauth_user
            report.unauth_users_ids.append(user_predictions)

        db.session.add(report)
        db.session.commit()

        return json.dumps({**prediction, "weather_text": period_text_descriptions})
    
    return json.dumps(form.errors), 400

@mainbp.route('/help-improve', methods=['POST'])
def help_improve():
    form = help_forms.Help()
    if form.validate_on_submit():
        unauth_user = UnauthUser.query.filter_by(uuid=session['id']).first()
        unauth_user.email = form.email.data
        db.session.commit()

        return "OK", 200
    
    return json.dumps(form.errors), 400

@mainbp.route('/snowday-status/<token>')
def snowday_status(token):
    ts = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        # 86400 seconds is one day
        user_type, prediction_id, user_id, response = str(ts.loads(token, salt=current_app.config['SNOWDAY_STATUS_SALT'], max_age=86400)).split("-")
    # The token can either expire or be invalid
    except:
        flash("That code is no longer valid.")
        abort(404)
    
    if user_type == "full":
        association = UserPredictions.query.filter_by(prediction_id=prediction_id, user_id=user_id).first()
        if association.snowday_status is None:
            association.user_rel.points += 1
    elif user_type == "un":
        association = UnauthUserPredictions.query.filter_by(prediction_id=prediction_id, unauth_user_id=user_id).first()
    else:
        flash("Corrupted code submitted.")
        abort(404)        

    association.snowday_status = response
    db.session.commit()

    return render_template('thanks.html', title='Thanks')


@mainbp.route('/contact', methods=['GET', 'POST'])
def contact():
    form = contact_forms.Contact()
    if form.validate_on_submit():
        status, response = email.send(current_app.config['CONTACT_EMAIL'], "[WIHASD Support] " + str(form.subject.data), form.message.data, from_email=form.email.data)
        if status == "success":
            flash('Your message has been sent', 'positive')
        elif status == "fail":
            flash('Your message failed to send', 'negative')
        return redirect(url_for('mainbp.index'))
    
    return render_template('contact.html', form=form, title="About")

@mainbp.route('/leaderboard')
def leaderboard():
    users = User.query.order_by(-User.points).limit(50).all()
    users = [(user.first_name, user.points, user.avatar(50)) for user in users]
    return render_template('leaderboard.html', users=users, title="Leaderboard")


@mainbp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = dt.datetime.utcnow()
        db.session.commit()