import json
import uuid
from flask import render_template, session, jsonify, Blueprint, flash, abort, current_app
from flask_login import current_user
from itsdangerous import URLSafeTimedSerializer
from app import app
from app.custom_errors import PredictionError
from app.models import PreditionReport, UnauthUser, UnauthUserPredictions, UserPredictions, User
import random
import datetime as dt
from app.forms import predict as predict_forms
from app.forms import improve as help_forms
from app.forms import contact as contact_forms
from app.toolbox import email
from app.extensions import db, limiter
from app.decorators import *

from sqlalchemy.orm import aliased
from sqlalchemy import func

from sendgrid.helpers.mail import To, Substitution, Personalization, From

from app.views import noaa_api
from app.prediction_utils import used_features_list

import pandas as pd

from uszipcode import SearchEngine

import atexit
import time
from apscheduler.schedulers.background import BackgroundScheduler


# Create the list that holds zip codes that the model is currently processing.
# This is used so that if two people predict for the same zip code at the same time
# the model will not process the weather data twice. Instead, the later prediction
# request will be wait until an entry is added in the database for that zip code
# in the last hour using the `PreditionReport.get_recent_prediction()` function.
currently_running_zip_codes = []

with open("app/index_backgrounds_base64.txt", "r") as file:
    index_backgrounds_base64 = file.readlines()

def create_follow_up_email(prediction_id, zip_code, user, first_prediction_date, ts, extra):
    start_token = str(extra) + "-" + str(prediction_id) + "-" + str(user.id)
    yes_token = ts.dumps(start_token + "-1", salt=current_app.config['SNOWDAY_STATUS_SALT'])
    yes_url = url_for('mainbp.snowday_status', token=yes_token, _external=True)
    no_token = ts.dumps(start_token + "-0", salt=current_app.config['SNOWDAY_STATUS_SALT'])
    no_url = url_for('mainbp.snowday_status', token=no_token, _external=True)

    p = Personalization()
    to_object = To(email=user.email, substitutions=[
        Substitution('((yes_url))', yes_url, p),
        Substitution('((no_url))', no_url, p),
        Substitution('((zip_code))', zip_code),
        Substitution('((date))', first_prediction_date.strftime('%Y-%m-%d'))
    ])
    p.add_to(to_object)

    return p

def send_follow_up_emails():
    ts = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    
    current_date = dt.date.today()
    # today = dt.datetime.today().replace(hour=12, minute=0, second=0).strftime('%Y-%m-%d %H:%M:%S')
    # yesterday = (dt.datetime.now() - dt.timedelta(1)).replace(hour=12, minute=0, second=0).strftime('%Y-%m-%d %H:%M:%S')
    
    to_emails = []
    distinct_zip_codes = PreditionReport.query.with_entities(PreditionReport.zip_code).distinct().all()
    distinct_zip_codes = [x[0] for x in distinct_zip_codes]

    for zip_code in distinct_zip_codes:
        predictions = PreditionReport.query.filter(PreditionReport.first_prediction_date == current_date, PreditionReport.emailed == False, PreditionReport.zip_code == zip_code).all()
        # predictions = PreditionReport.query.filter(PreditionReport.created_at.between(yesterday, today), PreditionReport.emailed == False, PreditionReport.zip_code == zip_code).all()

        # current_date = predictions[0].first_prediction_date

        users = set([assoc.user_rel for prediction in predictions for assoc in prediction.users_ids])
        unauth_users = set([assoc.unauth_user_rel for prediction in predictions for assoc in prediction.unauth_users_ids])

        predictions_ids = [str(prediction.id) for prediction in predictions]
        predictions_ids_tokenized = ",".join(predictions_ids)

        for user in users:
            p = create_follow_up_email(predictions_ids_tokenized, zip_code, user, current_date, ts, extra="full")
            to_emails.append(p)
        for unauth_user in unauth_users:
            p = create_follow_up_email(predictions_ids_tokenized, zip_code, unauth_user, current_date, ts, extra="un")
            to_emails.append(p)
        
        for prediction in predictions:
            prediction.emailed = True
            db.session.commit()
    
    html = render_template('email/improve.html', signed_in=current_user.is_authenticated)
    email.send(
        recipient=None,
        personalizations=to_emails,
        subject="Was our prediction right? - WillIHaveASnowDay.com",
        body=html,
        from_email=From(email=current_app.config['IMPROVE_FROM_EMAIL'], name="Help Improve @ WilliHaveASnowDay.com"),
        sendgrid_only=True
    )

def update_rankings():
    u1 = aliased(User)
    subq = db.session.query(func.count(u1.id)).filter(u1.points > User.points).as_scalar()
    print(subq)
    User.query.update({"rank": subq + 1}, synchronize_session=False)
    db.session.commit()

scheduler = BackgroundScheduler()
scheduler.add_job(func=send_follow_up_emails, trigger="cron", hour=15, minute=57, day_of_week="0-4", jitter=120)
scheduler.add_job(func=update_rankings, trigger="cron", hour="*/3", day_of_week="1-5", jitter=120)
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
    background = "data:image/jpeg;base64,"
    background += random.choice(index_backgrounds_base64)

    return render_template('index.html', predict_form=predict_form, help_form=help_form, signed_in=current_user.is_authenticated, background=background)

@mainbp.route('/about')
def about():
    return render_template('about.html', title="About")

@mainbp.route('/reverse-geocode', methods=['POST'])
@limiter.limit("4 per minute")
def reverse_geocode():
    if request.content_type == "application/json":
        latitude = request.json["latitude"]
        longitude = request.json["longitude"]
        
        search = SearchEngine(simple_zipcode=True)
        result_obj = search.by_coordinates(lat=latitude, lng=longitude, radius=10, returns=1)[0]
        return result_obj.zipcode
    
    return "Incorrect data type submitted", 400

def check_for_recent_prediction(zip_code, unauth_user):
    last_prediction = PreditionReport.get_recent_prediction(zip_code)
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
        return json.dumps({"percentages": model_prediction, "weather_text": weather_text})
    
    return False


@mainbp.route('/predict', methods=['POST'])
@limiter.limit("4 per minute")
def predict():
    if current_user.is_authenticated:
        unauth_user = None
    else:
        unauth_user = UnauthUser.query.filter_by(uuid=session['id']).first()
        if not unauth_user:
            unauth_user = UnauthUser(uuid=session['id'])
    
    form = predict_forms.Predict()
    
    if form.validate_on_submit():
        if form.zip_code.data in currently_running_zip_codes:
            timeout_start = time.time()
            while time.time() < timeout_start + 20:
                time.sleep(0.8)
                recent_prediction = check_for_recent_prediction(form.zip_code.data, unauth_user)
                if recent_prediction:
                    return recent_prediction
            raise PredictionError("Code 878")
        
        today = dt.datetime.now()
        if today.month in (7, 8):
            return json.dumps({"percentages": [0, 0, 0], "weather_text": "summer"})

        recent_prediction = check_for_recent_prediction(form.zip_code.data, unauth_user)
        if recent_prediction:
            return recent_prediction

        currently_running_zip_codes.append(form.zip_code.data)

        try:
            weather_data, text_weather, result_object = noaa_api.get_weather(form.zip_code.data, return_result_object=True)
        except ValueError as e:
            currently_running_zip_codes.remove(form.zip_code.data)
            return json.dumps({"zip_code": ["Invalid zip code"]}), 400

        # Prepare model inputs
        extra_info = {"Latitude": result_object.lat, "Longitude": result_object.lng, "State": result_object.state}
        model_inputs = noaa_api.prepapre_model_inputs(weather_data, extra_info, used_features_list=used_features_list)

        dates, offsets = noaa_api.create_weekdates(return_weekday_names=False, return_offsets=True)
        first_prediction_date = dates[0]

        # Make prediction
        try:
            model_inputs["Number of Snowdays in Year"] = [form.num_snowdays.data] * len(model_inputs[used_features_list[0]])
            # Convert to DataFrame and reorder the columns according to used_features_list
            model_inputs = pd.DataFrame(model_inputs)[used_features_list]
            prediction_probs = app.model.predict_proba(model_inputs)
            prediction_probs = prediction_probs[:, 0]

            prediction = {"percentages": []}

            for idx, offset in enumerate(offsets):
                try:
                    prediction["percentages"].append(int(prediction_probs[offset]*100))
                except IndexError:
                    prediction["percentages"].append(-3)  # -3 is code for "no prediction returned"

        except Exception as e:
            currently_running_zip_codes.remove(form.zip_code.data)
            raise PredictionError("Code 436") from e

        period_text_descriptions = noaa_api.generate_text_descriptions(text_weather)
        period_text_descriptions = noaa_api.process_text_descriptions(period_text_descriptions)

        report = PreditionReport(
            zip_code=form.zip_code.data,
            num_snowdays=form.num_snowdays.data,
            model_inputs=model_inputs.to_json(),
            model_prediction=json.dumps(prediction["percentages"]),
            weather_text=json.dumps(period_text_descriptions),
            first_prediction_date=first_prediction_date,
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

        currently_running_zip_codes.remove(form.zip_code.data)
        return json.dumps({**prediction, "weather_text": period_text_descriptions})
    
    return json.dumps(form.errors), 400

@mainbp.route('/help-improve', methods=['POST'])
def help_improve():
    form = help_forms.Help()
    if form.validate_on_submit():
        unauth_user = UnauthUser.query.filter_by(uuid=session['id']).first()
        if unauth_user is None:
            return "User Not Found", 500
        unauth_user.email = form.email.data
        db.session.commit()

        return "OK", 200
    
    return json.dumps(form.errors), 400

@mainbp.route('/snowday-status/<token>')
@limiter.limit("2 per minute")
def snowday_status(token):
    ts = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        # 86400 seconds is one day
        user_type, prediction_id, user_id, response = str(ts.loads(token, salt=current_app.config['SNOWDAY_STATUS_SALT'], max_age=86400)).split("-")
    # The token can either expire or be invalid
    except:
        flash("That code is no longer valid.")
        abort(404)
    
    prediction_ids = prediction_id.split(",")

    statuses = []
    if user_type == "full":
        for prediction_id in prediction_ids:
            association = UserPredictions.query.filter_by(prediction_id=prediction_id, user_id=user_id).first()
            if association is not None:
                statuses.append(association.snowday_status)
                association.snowday_status = response
        
        all_statuses_are_none = all([x is None for x in statuses])
        if all_statuses_are_none:
            flash("Response recorded successfully and points awarded.")
            association.user_rel.points += 1
        else:
            flash("Response updated. Points already awarded.")
    
    elif user_type == "un":
        for prediction_id in prediction_ids:
            association = UnauthUserPredictions.query.filter_by(prediction_id=prediction_id, unauth_user_id=user_id).first()
            if association is not None:
                statuses.append(association.snowday_status)
                association.snowday_status = response
        
        all_statuses_are_none = all([x is None for x in statuses])
        if all_statuses_are_none:
            flash("Response recorded successfully.")
        else:
            flash("Response updated.")
    
    else:
        flash("Corrupted code submitted.")
        abort(404)        

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
    users = [(user.username, user.points, user.avatar(50)) for user in users]
    return render_template('leaderboard.html', users=users, title="Leaderboard")
