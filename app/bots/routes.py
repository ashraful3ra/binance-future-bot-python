from flask import Blueprint, render_template, request, jsonify
from ..models import Bot, Account, Trade
from .. import db, socketio
from ..bot_logic import running_bots, symbol_trader
from sqlalchemy import func
import threading
import json

bots_bp = Blueprint('bots', __name__)

@bots_bp.route('/')
def dashboard():
    return render_template('dashboard.html')

@bots_bp.route('/bot-setup')
def bot_setup_page():
    return render_template('bot_setup.html')

@bots_bp.route('/report')
def report_list():
    bots = Bot.query.all()
    return render_template('report_list.html', bots=bots)

@bots_bp.route('/report/<int:bot_id>')
def report_detail(bot_id):
    bot = Bot.query.get_or_404(bot_id)
    trades = bot.trades.order_by(Trade.entry_time.desc()).all()
    
    total_trades = len(trades)
    total_profit = db.session.query(func.sum(Trade.pnl)).filter(Trade.bot_id == bot.id, Trade.pnl > 0).scalar() or 0
    total_loss = db.session.query(func.sum(Trade.pnl)).filter(Trade.bot_id == bot.id, Trade.pnl < 0).scalar() or 0
    
    stats = {
        'total_trades': total_trades,
        'win_trades': len([t for t in trades if t.pnl > 0]),
        'loss_trades': len([t for t in trades if t.pnl < 0]),
        'breakeven_trades': len([t for t in trades if t.pnl == 0]),
        'total_profit': f"{total_profit:.2f}",
        'total_loss': f"{abs(total_loss):.2f}",
        'net_result': f"{total_profit + total_loss:.2f}"
    }
    
    return render_template('report_detail.html', bot=bot, trades=trades, stats=stats)


@bots_bp.route('/api/bot-setup', methods=['GET', 'POST'])
def handle_bot_setup():
    if request.method == 'POST':
        data = request.json
        account = Account.query.first()
        if not account:
            return jsonify({'success': False, 'message': 'Please set up an API account first.'}), 400
        
        bot = Bot.query.filter_by(name=data['name']).first()
        if not bot:
            bot = Bot(name=data['name'], account_id=account.id)

        bot.timeframe = data['timeframe']
        bot.symbols = json.dumps(data['symbols'])
        bot.trade_mode = data['trade_mode']
        bot.leverage = int(data['leverage'])
        bot.margin_mode = data['margin_mode']
        bot.margin_usd = float(data['margin_usd'])
        bot.recovery_roi_threshold = float(data['recovery_roi_threshold']) if data.get('recovery_roi_threshold') else None
        bot.max_recovery_margin = float(data['max_recovery_margin']) if data.get('max_recovery_margin') else None
        bot.roi_targets = json.dumps(data['roi_targets'])
        bot.conditions = json.dumps(data['conditions'])
        bot.run_mode = data['run_mode']
        bot.max_trades_limit = int(data['max_trades_limit']) if data.get('max_trades_limit') else None
        
        db.session.add(bot)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Bot configuration saved successfully!'})

    bots = Bot.query.all()
    bot_data = {}
    if bots:
        b = bots[0]
        bot_data = {
            'name': b.name, 'timeframe': b.timeframe, 'symbols': b.get_symbols_list(),
            'trade_mode': b.trade_mode, 'leverage': b.leverage, 'margin_mode': b.margin_mode,
            'margin_usd': b.margin_usd, 'recovery_roi_threshold': b.recovery_roi_threshold,
            'max_recovery_margin': b.max_recovery_margin, 'roi_targets': json.loads(b.roi_targets or '{}'),
            'conditions': json.loads(b.conditions or '{}'), 'run_mode': b.run_mode, 
            'max_trades_limit': b.max_trades_limit
        }
    return jsonify(bot_data)


@bots_bp.route('/api/bots', methods=['GET'])
def get_bots():
    bots = Bot.query.all()
    return jsonify([b.to_dict() for b in bots])


@bots_bp.route('/api/bots/<int:bot_id>/start', methods=['POST'])
def start_bot(bot_id):
    if bot_id in running_bots: return jsonify({'success': False, 'message': 'Bot is already running.'})
    
    bot = Bot.query.get_or_404(bot_id)
    stop_event = threading.Event()
    running_bots[bot_id] = {'threads': {}, 'stop_event': stop_event}

    for symbol in bot.get_symbols_list():
        thread = threading.Thread(target=symbol_trader, args=(bot_id, symbol, stop_event), daemon=True)
        running_bots[bot_id]['threads'][symbol] = thread
        thread.start()
    
    bot.status = 'running'
    db.session.commit()
    socketio.emit('bot_status_update', bot.to_dict())
    return jsonify({'success': True, 'message': f"Bot '{bot.name}' started."})


@bots_bp.route('/api/bots/<int:bot_id>/close', methods=['POST'])
def stop_bot(bot_id):
    bot_info = running_bots.pop(bot_id, None)
    bot = Bot.query.get_or_404(bot_id)
    
    if bot_info:
        bot_info['stop_event'].set()
        for thread in bot_info['threads'].values():
            thread.join(timeout=5)
    
    bot.status = 'stopped'
    db.session.commit()
    socketio.emit('bot_status_update', bot.to_dict())
    return jsonify({'success': True, 'message': f"Bot '{bot.name}' stopped."})