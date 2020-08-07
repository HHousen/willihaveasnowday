# Setup the database
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

# Setup the mail server
from flask_mail import Mail
mail = Mail()

# Setup the debug toolbar
from flask_debugtoolbar import DebugToolbarExtension
toolbar = DebugToolbarExtension()

# Setup the password crypting
from flask_bcrypt import Bcrypt
bcrypt = Bcrypt()

# Setup the user login process
from flask_login import LoginManager
login_manager = LoginManager()

# Moment.js - Times & Dates
from flask_moment import Moment
moment = Moment()

# Setup rate limiting on prediction API
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)