from flask import Blueprint, render_template, request, jsonify
from ..models import Account
from .. import db
from binance.client import Client
from binance.exceptions import BinanceAPIException

accounts_bp = Blueprint('accounts', __name__)

def verify_binance_keys(api_key, api_secret, is_testnet):
    """
    ট্রেডিং পারমিশন আছে কিনা তা নিশ্চিত করার জন্য একটি ছোট টেস্ট অর্ডার প্লেস করে।
    """
    try:
        client = Client(api_key, api_secret, testnet=is_testnet)
        # প্রথমে অ্যাকাউন্টের তথ্য চেক করা
        client.futures_account()
        
        # এখন একটি ছোট, অসম্ভব লিমিট অর্ডার দিয়ে ট্রেডিং পারমিশন চেক করা
        # এই অর্ডারটি কখনো পূরণ হবে না এবং আমরা সাথে সাথেই এটি বাতিল করে দেব
        test_order = client.futures_create_order(
            symbol='BTCUSDT',
            side='BUY',
            type='LIMIT',
            timeInForce='GTC', # Good till cancelled
            quantity=0.001,
            price=1 # একটি অবাস্তব কম দাম
        )
        # অর্ডার সফলভাবে প্লেস হলে, সাথে সাথে বাতিল করা
        client.futures_cancel_order(symbol='BTCUSDT', orderId=test_order['orderId'])
        
        return True, "API Keys are valid and have trading permissions!"
    except BinanceAPIException as e:
        return False, f"Verification Failed: {e.message}"
    except Exception as e:
        return False, f"An unexpected error occurred during verification: {e}"

@accounts_bp.route('/')
def manage_accounts():
    return render_template('accounts.html')

@accounts_bp.route('/api', methods=['GET', 'POST'])
def handle_accounts_api():
    if request.method == 'POST':
        data = request.json
        is_valid, message = verify_binance_keys(data['api_key'], data['api_secret'], data['is_testnet'])
        
        if not is_valid:
            return jsonify({'success': False, 'message': message}), 400
        
        acc = Account.query.first()
        if not acc:
            acc = Account(id=1, name=data['name'])
        
        acc.name = data['name']
        acc.api_key = data['api_key']
        acc.api_secret = data['api_secret']
        acc.is_testnet = data['is_testnet']
        db.session.add(acc)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Account saved and verified successfully!'})
    
    account = Account.query.first()
    acc_data = {}
    if account:
        acc_data = {
            'name': account.name, 
            'api_key': account.api_key, 
            'api_secret': account.api_secret, 
            'is_testnet': account.is_testnet
        }
    return jsonify(acc_data)

@accounts_bp.route('/api/main-balance')
def get_main_balance():
    account = Account.query.first()
    if not account:
        return jsonify({'error': 'No account configured'}), 404
    
    try:
        client = Client(account.api_key, account.api_secret, testnet=account.is_testnet)
        balance_info = client.futures_account_balance()
        usdt_balance = next((item['balance'] for item in balance_info if item['asset'] == 'USDT'), "0.00")
        return jsonify({'balance': f"{float(usdt_balance):.2f}"})
    except Exception as e:
        return jsonify({'error': str(e)}), 500