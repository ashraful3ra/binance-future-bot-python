import threading
import time
import json
from . import db, create_app, socketio
from .models import Bot, Account, Trade
from binance.client import Client
from binance.exceptions import BinanceAPIException
from datetime import datetime

running_bots = {} 

def get_symbol_precision(client, symbol):
    try:
        exchange_info = client.futures_exchange_info()
        for s in exchange_info['symbols']:
            if s['symbol'] == symbol:
                return s['quantityPrecision']
    except Exception as e:
        print(f"Error getting precision for {symbol}: {e}")
    return 0

def calculate_quantity(margin_usdt, leverage, price, precision):
    if price == 0: return 0
    total_usdt = margin_usdt * leverage
    quantity = total_usdt / price
    return f"{quantity:.{precision}f}"

def symbol_trader(bot_id, symbol, stop_event):
    app = create_app()
    with app.app_context():
        bot = Bot.query.get(bot_id)
        if not bot: return

        print(f"✅ Starting REAL trader for {symbol} under Bot '{bot.name}'")
        account = bot.account
        client = Client(account.api_key, account.api_secret, testnet=account.is_testnet)
        
        timeframe_map = {'1m': 60, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600, '4h': 14400}
        wait_seconds = timeframe_map.get(bot.timeframe, 60)
        
        try:
            client.futures_change_leverage(symbol=symbol, leverage=bot.leverage)
            precision = get_symbol_precision(client, symbol)
        except Exception as e:
            print(f"Failed to set leverage for {symbol}: {e}")
            return

        while not stop_event.is_set():
            try:
                position_amount = 0.0
                entry_price = 0.0
                positions = client.futures_position_information(symbol=symbol)

                if positions:
                    position_amount = float(positions[0]['positionAmt'])
                    entry_price = float(positions[0]['entryPrice'])

                if position_amount != 0:
                    close_side = Client.SIDE_SELL if position_amount > 0 else Client.SIDE_BUY
                    print(f"Bot '{bot.name}' ({symbol}): Attempting to CLOSE position of {position_amount}...")
                    client.futures_create_order(symbol=symbol, side=close_side, type=Client.ORDER_TYPE_MARKET, quantity=abs(position_amount))
                    
                    time.sleep(2)
                    
                    # --- সমাধান: এখানে ফাংশনের নামটি ঠিক করা হয়েছে ---
                    pnl_history = client.futures_account_trades(symbol=symbol, limit=1)
                    
                    if pnl_history:
                        last_trade = pnl_history[0]
                        realized_pnl = float(last_trade['realizedPnl'])
                        exit_price = float(last_trade['price'])
                        roi = (realized_pnl / bot.margin_usd) * 100 if bot.margin_usd > 0 else 0

                        new_trade = Trade(
                            bot_id=bot.id, symbol=symbol, entry_price=entry_price,
                            exit_price=exit_price, entry_time=datetime.utcnow(),
                            exit_time=datetime.utcnow(), margin_used=bot.margin_usd,
                            pnl=realized_pnl, roi_percent=roi,
                            close_reason="Candle Close", side="LONG" if position_amount > 0 else "SHORT"
                        )
                        db.session.add(new_trade)
                        db.session.commit()
                        print(f"Bot '{bot.name}' ({symbol}): Logged REAL closed trade. PNL: {realized_pnl:.2f} USDT")

                klines = client.futures_klines(symbol=symbol, interval=bot.timeframe, limit=2)
                if len(klines) < 2:
                    print(f"Bot '{bot.name}' ({symbol}): Not enough historical data. Waiting...")
                    stop_event.wait(wait_seconds)
                    continue

                last_candle = klines[-2]
                open_price, close_price = float(last_candle[1]), float(last_candle[4])
                print(f"Bot '{bot.name}' ({symbol}): Analyzing {bot.timeframe} candle. O:{open_price}, C:{close_price}")
                
                side = None
                if bot.trade_mode == 'follow':
                    if close_price > open_price: side = Client.SIDE_BUY
                    elif close_price < open_price: side = Client.SIDE_SELL
                elif bot.trade_mode == 'opposite':
                    if close_price > open_price: side = Client.SIDE_SELL
                    elif close_price < open_price: side = Client.SIDE_BUY

                if side:
                    quantity = calculate_quantity(bot.margin_usd, bot.leverage, close_price, precision)
                    if float(quantity) > 0:
                        print(f"Bot '{bot.name}' ({symbol}): Placing NEW {side} order for {quantity} units.")
                        client.futures_create_order(symbol=symbol, side=side, type=Client.ORDER_TYPE_MARKET, quantity=quantity)
                else:
                    print(f"Bot '{bot.name}' ({symbol}): No trade condition met.")
                
                stop_event.wait(wait_seconds)
            except BinanceAPIException as e:
                print(f"Binance API Error in {symbol} trader for Bot '{bot.name}': {e.message}")
                stop_event.wait(30)
            except Exception as e:
                print(f"Error in {symbol} trader for Bot '{bot.name}': {e}")
                stop_event.wait(30)
    
    print(f"🛑 Trader for {symbol} under Bot '{bot.name}' stopped.")