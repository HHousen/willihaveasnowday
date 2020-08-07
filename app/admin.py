import os.path as op

from flask import request, Response, Blueprint, current_app
from werkzeug.exceptions import HTTPException
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_admin.contrib.fileadmin import FileAdmin
from app.models import User
from app.extensions import db

def init_admin(admin_panel):
    # Users
    admin_panel.add_view(ModelView(User, db.session))

    # Static files
    path = op.join(op.dirname(__file__), 'static')
    admin_panel.add_view(FileAdmin(path, '/static/', name='Static'))
    return None

class ModelView(ModelView):

    def is_accessible(self):
        auth = request.authorization or request.environ.get('REMOTE_USER')  # workaround for Apache
        if not auth or (auth.username, auth.password) != current_app.config['ADMIN_CREDENTIALS']:
            raise HTTPException('', Response('You have to an administrator.', 401,
                {'WWW-Authenticate': 'Basic realm="Login Required"'}
            ))
        return True

