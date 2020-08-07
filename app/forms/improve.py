from flask_wtf import FlaskForm
from wtforms import TextField, PasswordField, IntegerField
from wtforms.validators import Required, Email

class Help(FlaskForm):

    ''' Main help email info form. '''

    email = TextField(validators=[Required(), Email()],
                      description='Email address')