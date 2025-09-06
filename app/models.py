from . import db
import json
from datetime import datetime

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    api_key = db.Column(db.String(200), nullable=False)
    api_secret = db.Column(db.String(200), nullable=False)
    is_testnet = db.Column(db.Boolean, default=False)
    bots = db.relationship('Bot', backref='account', lazy=True, cascade="all, delete-orphan")

class Bot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    timeframe = db.Column(db.String(10), nullable=False)
    symbols = db.Column(db.Text, nullable=False)
    trade_mode = db.Column(db.String(20), nullable=False)
    leverage = db.Column(db.Integer, nullable=False)
    margin_mode = db.Column(db.String(20), nullable=False)
    margin_usd = db.Column(db.Float, nullable=False)
    recovery_roi_threshold = db.Column(db.Float, nullable=True)
    max_recovery_margin = db.Column(db.Float, nullable=True)
    roi_targets = db.Column(db.Text, nullable=True)
    conditions = db.Column(db.Text, nullable=True)
    run_mode = db.Column(db.String(20), nullable=False)
    max_trades_limit = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), default='stopped')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    trades = db.relationship('Trade', backref='bot', lazy='dynamic', cascade="all, delete-orphan")
    
    def get_symbols_list(self):
        return json.loads(self.symbols) if self.symbols else []

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'status': self.status,
            'symbols': self.get_symbols_list(),
            'account_name': self.account.name,
            'is_testnet': self.account.is_testnet
        }

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('bot.id'), nullable=False)
    symbol = db.Column(db.String(20), nullable=False)
    entry_price = db.Column(db.Float)
    exit_price = db.Column(db.Float)
    entry_time = db.Column(db.DateTime, default=datetime.utcnow)
    exit_time = db.Column(db.DateTime)
    margin_used = db.Column(db.Float)
    pnl = db.Column(db.Float)
    roi_percent = db.Column(db.Float)
    close_reason = db.Column(db.String(100))
    side = db.Column(db.String(10))