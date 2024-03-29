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
from app.extensions import db, limiter, sitemap
from app.decorators import *

from sqlalchemy.orm import aliased
from sqlalchemy import func

from sendgrid.helpers.mail import To, Substitution, Personalization, From

from app.views import noaa_api
from app.prediction_utils import used_features_list, pred_min, max_minus_min

import pandas as pd

from uszipcode import SearchEngine
from noaa_sdk.errors import InvalidZipCodeError, RetryTimeoutError, ServiceUnavilableError

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

today = dt.datetime.now()
is_summer = today.month in (7, 8)

def create_follow_up_email_mul_zip(prediction_ids, zip_codes, user, first_prediction_date, ts, extra):
    if extra == "un":
        extra_message = 'If you would like to keep track of your contributions and see your rank on the <a href="https://willihaveasnowday.com/leaderboard">leaderboard</a> then <a href="https://willihaveasnowday.com/user/signup">sign up for an account</a>.'
    else:
        extra_message = ""

    p = Personalization()
    substitutions = [
        Substitution('((date))', first_prediction_date.strftime('%Y-%m-%d'), p),
        Substitution('((extra_message))', extra_message, p),
    ]

    for idx, (prediction_id, zip_code) in enumerate(zip(prediction_ids, zip_codes)):
        start_token = str(extra) + "-" + str(prediction_id) + "-" + str(user.id)
        yes_token = ts.dumps(start_token + "-1", salt=current_app.config['SNOWDAY_STATUS_SALT'])
        yes_url = url_for('mainbp.snowday_status', token=yes_token, _external=True)
        no_token = ts.dumps(start_token + "-0", salt=current_app.config['SNOWDAY_STATUS_SALT'])
        no_url = url_for('mainbp.snowday_status', token=no_token, _external=True)

        substitutions.append(Substitution('((yes_url_' + str(idx) + '))', yes_url, p))
        substitutions.append(Substitution('((no_url_' + str(idx) + '))', no_url, p))
        substitutions.append(Substitution('((zip_code_' + str(idx) + '))', zip_code, p))
    
    p = Personalization()
    assert user.email is not None
    to_object = To(email=user.email, substitutions=substitutions)
    p.add_to(to_object)

    return p


def send_follow_up_emails():
    with app.main_app.app_context():
        app.main_app.logger.info("Sending follow up emails")
        if is_summer:
            return
        ts = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        
        current_date = dt.date.today()
        # today = dt.datetime.today().replace(hour=12, minute=0, second=0).strftime('%Y-%m-%d %H:%M:%S')
        # yesterday = (dt.datetime.now() - dt.timedelta(1)).replace(hour=12, minute=0, second=0).strftime('%Y-%m-%d %H:%M:%S')
        
        to_emails = []
        distinct_zip_codes = PreditionReport.query.filter(PreditionReport.first_prediction_date == current_date).with_entities(PreditionReport.zip_code).distinct().all()
        distinct_zip_codes = [x[0] for x in distinct_zip_codes]
        app.main_app.logger.info(f"Sending emails: Number of distinct zip codes: {len(distinct_zip_codes)}")

        user_emails_dict = {}

        for zip_idx, zip_code in enumerate(distinct_zip_codes):
            if zip_idx % 100 == 0:
                app.main_app.logger.info(f"On zip code idx {zip_idx} of {len(distinct_zip_codes)}")
            predictions = PreditionReport.query.filter(PreditionReport.first_prediction_date == current_date, PreditionReport.emailed.is_(False), PreditionReport.zip_code == zip_code).all()
            if len(predictions) > 0:
                app.main_app.logger.info(f"{len(predictions)} predictions matched for zip code {zip_code}")
            # predictions = PreditionReport.query.filter(PreditionReport.created_at.between(yesterday, today), PreditionReport.emailed == False, PreditionReport.zip_code == zip_code).all()

            # current_date = predictions[0].first_prediction_date

            users = set([assoc.user_rel for prediction in predictions for assoc in prediction.users_ids])
            unauth_users = set([assoc.unauth_user_rel for prediction in predictions for assoc in prediction.unauth_users_ids])

            predictions_ids = [str(prediction.id) for prediction in predictions]
            predictions_ids_tokenized = ",".join(predictions_ids)

            for user in users:
                if user.email is None:
                    continue
                if user.receive_improve_emails:
                    user_email_info = {"predictions_ids_tokenized": predictions_ids_tokenized, "zip_code": zip_code, "extra": "full"}
                    try:
                        user_emails_dict[user].append(user_email_info)
                    except:
                        user_emails_dict[user] = [user_email_info]
                
                # p = create_follow_up_email(predictions_ids_tokenized, zip_code, user, current_date, ts, extra="full")
                # to_emails.append(p)
            for unauth_user in unauth_users:
                if unauth_user.email is None:
                    continue
                user_email_info = {"predictions_ids_tokenized": predictions_ids_tokenized, "zip_code": zip_code, "extra": "un"}
                try:
                    user_emails_dict[unauth_user].append(user_email_info)
                except:
                    user_emails_dict[unauth_user] = [user_email_info]
                # p = create_follow_up_email(predictions_ids_tokenized, zip_code, unauth_user, current_date, ts, extra="un")
                # to_emails.append(p)
            
            for prediction in predictions:
                prediction.emailed = True
                db.session.commit()
        
        app.main_app.logger.info(f"Sending emails: Number of distinct users: {len(user_emails_dict)}")
        
        emails_by_num_zip_codes = {}
        for user, emails in user_emails_dict.items():
            num_emails = len(emails)
            if num_emails > 1:
                # Next line based on: https://stackoverflow.com/a/33046935
                emails = {k: [dic[k] for dic in emails] for k in emails[0]}
                p = create_follow_up_email_mul_zip(emails["predictions_ids_tokenized"], emails["zip_code"], user, current_date, ts, extra=emails["extra"][0])
            else:
                num_emails = 1
                emails = emails[0]
                p = create_follow_up_email_mul_zip([emails["predictions_ids_tokenized"]], [emails["zip_code"]], user, current_date, ts, extra=emails["extra"])
            
            try:
                emails_by_num_zip_codes[num_emails].append(p)
            except KeyError:
                emails_by_num_zip_codes[num_emails] = [p]

        for num_zip_codes, to_emails in emails_by_num_zip_codes.items():
            if num_zip_codes > 1:
                html = render_template('email/improve_multiple.html', num_zip_codes=num_zip_codes)
            else:
                html = render_template('email/improve.html')
            app.main_app.logger.info(f"Sending num_zip_codes={num_zip_codes}, len(to_emails)={len(to_emails)}")
            email.send(
                recipient=None,
                personalizations=to_emails,
                subject="Was our prediction right? - WillIHaveASnowDay.com",
                body=html,
                from_email=From(email=current_app.config['IMPROVE_FROM_EMAIL'], name="Help Improve @ WilliHaveASnowDay.com"),
                sendgrid_only=True
            )

def update_rankings():
    with app.main_app.app_context():
        u1 = aliased(User)
        subq = db.session.query(func.count(u1.id)).filter(u1.points > User.points).as_scalar()
        User.query.update({"rank": subq + 1}, synchronize_session=False)
        db.session.commit()

scheduler = BackgroundScheduler(job_defaults={'misfire_grace_time': 15*60})
scheduler.add_job(func=send_follow_up_emails, trigger="cron", hour=8, minute=35, day_of_week="1-5", jitter=120)
scheduler.add_job(func=update_rankings, trigger="cron", hour="*/3", day_of_week="1-5", jitter=120)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

mainbp = Blueprint('mainbp', __name__)


def set_session_id():
    if not current_user.is_authenticated:
        if 'id' not in session:
            session['id'] = str(uuid.uuid4())

@mainbp.route('/')
@mainbp.route('/index', methods=['GET', 'POST'])
def index():
    set_session_id()
    predict_form = predict_forms.Predict()
    help_form = help_forms.Help()
    background = "data:image/jpeg;base64,"
    background += random.choice(index_backgrounds_base64)

    return render_template('index.html', disable_help_improve=is_summer, predict_form=predict_form, help_form=help_form, signed_in=current_user.is_authenticated, background=background)

@mainbp.route('/about')
def about():
    return render_template('about.html', title="About")

@mainbp.route('/reverse-geocode', methods=['POST'])
@limiter.limit("4 per minute")
def reverse_geocode():
    if request.content_type == "application/json":
        latitude = request.json["latitude"]
        longitude = request.json["longitude"]
        
        search = SearchEngine(simple_zipcode=True, db_file_dir="app/uszipcode/")
        result_obj = search.by_coordinates(lat=latitude, lng=longitude, radius=10, returns=1)[0]
        return result_obj.zipcode
    
    return json.dumps("Incorrect data type submitted"), 400

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

def prediction_error_json(func):
    def wrapper():
        try:
            return func()
        except PredictionError:
            raise
        except Exception as e:
            raise PredictionError("Code 245 Unknown Error") from e
    return wrapper

@mainbp.route('/predict', methods=['POST'])
@prediction_error_json
@limiter.limit("4 per minute")
def predict():
    if current_user.is_authenticated:
        unauth_user = None
    else:
        set_session_id()
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
            raise PredictionError("Code 878 Recent Prediction Timeout")
        
        if is_summer:
            return json.dumps({"percentages": [0, 0, 0], "weather_text": "summer"})

        recent_prediction = check_for_recent_prediction(form.zip_code.data, unauth_user)
        if recent_prediction:
            return recent_prediction

        # Large try...finally block to always remove the currently running zip code from
        # `currently_running_zip_codes` no matter if the code completes or crashes.
        try:
            currently_running_zip_codes.append(form.zip_code.data)

            try:
                weather_data, text_weather, result_object = noaa_api.get_weather(form.zip_code.data, return_result_object=True, db_file_dir="app/uszipcode/")
            except InvalidZipCodeError as e:
                return json.dumps({"zip_code": ["Invalid zip code"]}), 400
            except RetryTimeoutError as e:
                raise PredictionError("Code 904 NOAA Weather.gov Timeout") from e
            except ServiceUnavilableError as e:
                raise PredictionError("Code 775 NOAA Weather.gov Unavilable") from e
            except Exception as e:
                raise PredictionError("Code 141 NOAA Weather.gov Processing Error") from e

            # Prepare model inputs
            extra_info = {"Latitude": result_object.lat, "Longitude": result_object.lng, "State": result_object.state}
            model_inputs = noaa_api.prepapre_model_inputs(weather_data, extra_info, used_features_list=used_features_list)

            dates, offsets = noaa_api.create_weekdates(return_weekday_names=False, return_offsets=True)
            first_prediction_date = dates[0]

            model_inputs["Number of Snowdays in Year"] = [form.num_snowdays.data] * len(model_inputs[used_features_list[10]])
            # Convert to DataFrame and reorder the columns according to used_features_list
            model_inputs = pd.DataFrame(model_inputs)[used_features_list]
            
            # Make prediction
            try:
                prediction_probs = app.model.predict_proba(model_inputs)
                prediction_probs = prediction_probs[:, 0]
                prediction_probs = noaa_api.scale_model_predictions(prediction_probs, pred_min, max_minus_min, apply_shift=True)
            except Exception as e:
                raise PredictionError("Code 436 AI Model Failure") from e

            prediction = {"percentages": []}

            for idx, offset in enumerate(offsets):
                try:
                    prediction["percentages"].append(int(prediction_probs[offset]*100))
                except IndexError:
                    prediction["percentages"].append(-3)  # -3 is code for "no prediction returned"

            period_text_descriptions = noaa_api.generate_text_descriptions(text_weather)
            period_text_descriptions = noaa_api.process_text_descriptions(period_text_descriptions)

            report = PreditionReport(
                zip_code=form.zip_code.data,
                num_snowdays=form.num_snowdays.data,
                model_inputs=model_inputs.round(1).to_json(orient="values"),
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

            return json.dumps({**prediction, "weather_text": period_text_descriptions})
        finally:
            currently_running_zip_codes.remove(form.zip_code.data)
    
    return json.dumps(form.errors), 400

@mainbp.route('/help-improve', methods=['POST'])
def help_improve():
    if is_summer:
        return "summer", 501
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
        not_none_association = None
        for prediction_id in prediction_ids:
            association = UserPredictions.query.filter_by(prediction_id=int(prediction_id), user_id=user_id).first()
            if association is not None:
                statuses.append(association.snowday_status)
                association.snowday_status = response
                not_none_association = association
        
        all_statuses_are_none = all([x is None for x in statuses])
        if all_statuses_are_none:
            flash("Response recorded successfully and points awarded.")
            not_none_association.user_rel.points += 1
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
@limiter.limit("20 per hour")
def contact():
    # form = contact_forms.Contact()
    # if form.validate_on_submit():
    #     status, response = email.send(current_app.config['CONTACT_EMAIL'], "[WIHASD Support] " + str(form.subject.data), form.message.data, from_email=form.email.data)
    #     if status == "success":
    #         flash('Your message has been sent', 'positive')
    #     elif status == "fail":
    #         flash('Your message failed to send', 'negative')
    #     return redirect(url_for('mainbp.index'))
    
    return render_template('contact.html', title="Contact")

@mainbp.route('/leaderboard')
def leaderboard():
    users = User.query.order_by(-User.points).limit(50).all()
    users = [(user.username, user.points, user.avatar(50)) for user in users]
    return render_template('leaderboard.html', users=users, title="Leaderboard")

@mainbp.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy-policy.html', title="Privacy Policy")

@sitemap.register_generator
def index():
    for x in ['mainbp.index', 'mainbp.about', 'mainbp.contact', 'mainbp.leaderboard', 'mainbp.privacy_policy', 'userbp.signup', 'userbp.signin', 'userbp.forgot']:
        yield x, {}
