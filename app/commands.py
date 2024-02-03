import click
from flask.cli import with_appcontext
from werkzeug.exceptions import MethodNotAllowed, NotFound

from app import app, models
from app.extensions import db
from termcolor import colored
from distutils import util

# Run with `flask initdb`
@click.command()
def initdb():
    ''' Create the SQL database. '''
    db.create_all(app=app.create_app())
    print(colored('The SQL database has been created', 'green'))

@click.command()
def dropdb():
    ''' Delete the SQL database. '''
    user_input = input('Are you sure you want to lose all your SQL data? ')
    if util.strtobool(user_input) == 1:
        db.drop_all(app=app.create_app())
        print(colored('The SQL database has been deleted', 'green'))
    else:
        print(colored('Canceled', 'green'))

@click.command()
def recycledb():
    ''' Recycle the SQL database. '''
    user_input = input('Are you sure you want recreate the SQL database? All data will be lost. ')
    if util.strtobool(user_input) == 1:
        db.drop_all(app=app.create_app())
        db.create_all(app=app.create_app())
        print(colored('The SQL database has been recreated', 'green'))
    else:
        print(colored('Canceled', 'green'))

@click.command()
def sendemails():
    from app.views.main import send_follow_up_emails
    app.create_app()
    send_follow_up_emails()
