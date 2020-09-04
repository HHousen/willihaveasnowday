import datetime
from sqlalchemy import ForeignKey, Table
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship
from flask_login import UserMixin

from app.extensions import db, bcrypt
import datetime as dt
from hashlib import md5


class User(db.Model, UserMixin):

    ''' A user who has an account on the website. '''

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, unique=True, nullable=False)
    username = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(80), unique=True, nullable=False)
    confirmation = db.Column(db.Boolean(), nullable=False, default=False)
    created_at = db.Column(db.DateTime(), nullable=True, default=dt.datetime.utcnow)
    credits = db.Column(db.Integer(), nullable=True, default=0)
    points = db.Column(db.Integer(), nullable=True, default=0)
    rank = db.Column(db.Integer(), nullable=True, default=0)
    customer_id = db.Column(db.String(40), nullable=True)
    _password = db.Column(db.Binary(60), nullable=False)

    predictions = relationship("UserPredictions", back_populates="user_rel")

    @hybrid_property
    def password(self):
        return self._password

    @password.setter
    def password(self, plaintext):
        self._password = bcrypt.generate_password_hash(plaintext)

    def check_password(self, plaintext):
        return bcrypt.check_password_hash(self.password, plaintext)

    def get_id(self):
        return self.email

    def get_credits(self):
        return self.credits
    
    def avatar(self, size):
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return 'https://www.gravatar.com/avatar/{}?d=identicon&s={}'.format(digest, size)

class UserPredictions(db.Model):

    __tablename__ = 'user_predictions_association'

    prediction_id = db.Column(db.Integer, ForeignKey('prediction_log.id'), primary_key=True)
    user_id = db.Column(db.Integer, ForeignKey('users.id'), primary_key=True)
    snowday_status = db.Column(db.Integer, nullable=True)

    user_rel = relationship("User", back_populates="predictions")
    report = relationship("PreditionReport", back_populates="users_ids")

class UnauthUserPredictions(db.Model):

    __tablename__ = 'unauthuser_predictions_association'

    prediction_id = db.Column(db.Integer, ForeignKey('prediction_log.id'), primary_key=True)
    unauth_user_id = db.Column(db.Integer, ForeignKey('unauth_users.id'), primary_key=True)
    snowday_status = db.Column(db.Integer, nullable=True)

    unauth_user_rel = relationship("UnauthUser", back_populates="predictions")
    report = relationship("PreditionReport", back_populates="unauth_users_ids")

class PreditionReport(db.Model):

    __tablename__ = 'prediction_log'

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime(), unique=True, nullable=False, default=dt.datetime.now)
    zip_code = db.Column(db.String(5), nullable=False)
    num_snowdays = db.Column(db.Integer(), nullable=False)
    model_inputs = db.Column(db.String(300), nullable=False)
    model_prediction = db.Column(db.String(30), nullable=False)
    emailed = db.Column(db.Boolean(), nullable=False, default=False)
    weather_text = db.Column(db.String(200), nullable=True)
    first_prediction_date = db.Column(db.Date(), nullable=False)

    unauth_users_ids = relationship("UnauthUserPredictions", back_populates="report")
    users_ids = relationship("UserPredictions", back_populates="report")

    @classmethod
    def get_recent_prediction(cls, zip_code):
        zip_code_entry = cls.query.order_by(PreditionReport.created_at.desc()).filter_by(zip_code=zip_code).first()
        if zip_code_entry is not None and zip_code_entry.created_at > datetime.datetime.now()-datetime.timedelta(hours=1):
            return zip_code_entry
        
        return None

class UnauthUser(db.Model):

    __tablename__ = 'unauth_users'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(32), unique=True, nullable=False)
    email = db.Column(db.String(80), unique=True, nullable=True)

    predictions = relationship("UnauthUserPredictions", back_populates="unauth_user_rel")
