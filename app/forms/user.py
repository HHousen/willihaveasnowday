from flask_wtf import FlaskForm
from wtforms import TextField, PasswordField, IntegerField
from wtforms.validators import Required, Length, Email, ValidationError, EqualTo, NumberRange, Optional
from app.models import User


class Unique(object):

    '''
    Custom validator to check an object's attribute
    is unique. For example users should not be able
    to create an account if the account's email
    address is already in the database. This class
    supposes you are using SQLAlchemy to query the
    database.
    '''

    def __init__(self, model, field, message):
        self.model = model
        self.field = field
        self.message = message

    def __call__(self, form, field):
        check = self.model.query.filter(self.field == field.data).first()
        if check:
            raise ValidationError(self.message)


class Forgot(FlaskForm):

    ''' User forgot password form. '''

    email = TextField(validators=[Required(), Email()],
                      description='Email address')


class Reset(FlaskForm):

    ''' User reset password form. '''

    password = PasswordField(validators=[
        Required(), Length(min=6),
        EqualTo('confirm', message='Passwords must match.')
    ], description='Password')
    confirm = PasswordField(description='Confirm password')


class Login(FlaskForm):

    ''' User login form. '''

    email = TextField(validators=[Required(), Email()],
                      description='Email address')
    password = PasswordField(validators=[Required()],
                             description='Password')


class SignUp(FlaskForm):

    ''' User sign up form. '''

    first_name = TextField(validators=[Required(), Length(min=2)],
                     description='First name')
    last_name = TextField(validators=[Required(), Length(min=2)],
                        description='Last name')
    phone = TextField(validators=[Required(), Length(min=6)],
                      description='Phone number')
    email = TextField(validators=[Required(), Email(),
                                  Unique(User, User.email,
                                         'This email address is ' +
                                         'already linked to an account.')],
                      description='Email address')
    password = PasswordField(validators=[
        Required(), Length(min=6),
        EqualTo('confirm', message='Passwords must match.')
    ], description='Password')
    confirm = PasswordField(description='Confirm password')

class Credits(FlaskForm):
    credits = IntegerField(validators=[Required(), NumberRange(min=1)],
                     description='Number of Credits')

class Plan(FlaskForm):
    plan = TextField(validators=[Required()])