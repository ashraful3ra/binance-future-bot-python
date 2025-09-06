from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
import os

db = SQLAlchemy()
socketio = SocketIO()

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    
    app.config['SECRET_KEY'] = 'a_super_secret_key_for_production_change_it'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'database.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    db.init_app(app)
    socketio.init_app(app)

    with app.app_context():
        from . import models
        db.create_all()

        from .accounts.routes import accounts_bp
        from .bots.routes import bots_bp
        app.register_blueprint(accounts_bp, url_prefix='/accounts')
        app.register_blueprint(bots_bp, url_prefix='/')
        
        # The following lines that reset the status have been removed.
        # This was the cause of the problem.

    return app