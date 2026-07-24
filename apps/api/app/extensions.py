"""
Flask extensions are instantiated here (without a bound app) and imported
everywhere. The actual app binding happens in create_app() via init_app(),
which is the standard Flask app-factory pattern.
"""

from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
jwt = JWTManager()
bcrypt = Bcrypt()
migrate = Migrate()
