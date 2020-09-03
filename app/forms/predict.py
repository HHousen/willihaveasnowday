from flask_wtf import FlaskForm
from wtforms import TextField, PasswordField, IntegerField
from wtforms.validators import Required, InputRequired, ValidationError, EqualTo, NumberRange, Optional

class Predict(FlaskForm):

    ''' Main prediction info form. '''

    zip_code = TextField(validators=[Required()],
                      description='ZIP Code')
    num_snowdays = IntegerField(validators=[InputRequired(), NumberRange(min=0, max=42)],
                     description='Snow Days this Year')