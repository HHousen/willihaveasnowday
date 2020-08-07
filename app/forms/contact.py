from flask_wtf import FlaskForm
from wtforms import TextField, TextAreaField
from wtforms.validators import Required, Email, Length

class Contact(FlaskForm):

    ''' Main contact form. '''

    name = TextField(validators=[Required(), Length(min=2)],
                     description='Name')
    email = TextField(validators=[Required(), Email()],
                      description='From email address')
    subject = TextField(validators=[Required(), Length(min=2)],
                        description='Subject')
    message = TextAreaField(validators=[Required(), Length(min=60)], 
                            description="Message")