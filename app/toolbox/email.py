from threading import Thread
from flask_mail import Message
from flask import current_app
from app.extensions import mail
from app import app
from environs import Env

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

env = Env()
env.read_env()

def send(recipient, subject, body, from_email=None, sendgrid_only=False, personalizations=None):
    '''
    Send a mail to a recipient. The body is usually a rendered HTML template.
    The sender's credentials has been configured in the config.py file.
    '''
    if from_email is None:
        from_email = current_app.config['DEFAULT_FROM_EMAIL']
    
    if (current_app.config['USE_MAIL']) and not sendgrid_only:
        sender = from_email
        message = Message(subject, sender=sender, recipients=[recipient])
        message.html = body
        # Create a new thread
        thr = Thread(target=send_async, args=[app, message])
        thr.start()
        return ("success", None)

    sendgrid_key = current_app.config["SENDGRID_API_KEY"]
    if sendgrid_key != "False":
        params = {
            'from_email': from_email,
            'subject': subject,
            'html_content': body
        }
        if recipient is not None:
            params['to_emails'] = recipient
        
        message = Mail(**params)

        if personalizations is not None:
            [message.add_personalization(p) for p in personalizations]
        
        try:
            sg = SendGridAPIClient(sendgrid_key)
            response = sg.send(message)
            return ("success", response)
        except Exception as e:
            return ("fail", e)
    


def send_async(app, message):
    ''' Send the mail asynchronously. '''
    with app.app_context():
        mail.send(message)