from flask import Blueprint, render_template, request, jsonify
from ..models import Account
from .. import db
from binance.client import Client
from binance.exceptions import BinanceAPIException

accounts_bp = Blueprint('accounts', __name__)

def get_btc_precision(client):
    """Fetches quantity precision for BTCUSDT."""
    try:
        exchange_info = client.futures_exchange_info()
        for s in exchange_info['symbols']:
            if s['symbol'] == 'BTCUSDT':
                return s['quantityPrecision']
    except Exception as e:
        print(f"Error getting BTC precision: {e}")
    return 3 # Default to 3 if API fails

def verify_binance_keys(api_key, api_secret, is_testnet):
    """
    Checks for trading permissions by placing and immediately canceling a valid limit order
    that meets the minimum notional value requirement.
    """
    try:
        client = Client(api_key, api_secret, testnet=is_testnet)
        client.futures_account() # Check for basic connectivity
        
        # --- পরিবর্তিত অংশ শুরু ---
        
        # Define minimum notional value for the test order
        MIN_NOTIONAL = 101.0  # Set to slightly above 100 for safety

        # 1. Get current price to calculate a safe, non-executable test price
        mark_price_info = client.futures_mark_price(symbol='BTCUSDT')
        current_price = float(mark_price_info['markPrice'])
        test_price = round(current_price * 0.5, 1) # 50% below market, rounded for BTC tick size

        # 2. Get quantity precision for BTCUSDT
        precision = get_btc_precision(client)

        # 3. Calculate quantity needed to meet the minimum notional value at the low test price
        test_quantity = round(MIN_NOTIONAL / test_price, precision)

        print(f"Verification: Using test price {test_price} and calculated quantity {test_quantity}")

        # 4. Place the test order with the calculated price and quantity
        test_order = client.futures_create_order(
            symbol='BTCUSDT',
            side='BUY',
            type='LIMIT',
            timeInForce='GTC',
            quantity=test_quantity,
            price=test_price
        )
        
        # 5. Immediately cancel the test order
        client.futures_cancel_order(symbol='BTCUSDT', orderId=test_order['orderId'])
        # --- পরিবর্তিত অংশ শেষ ---
        
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