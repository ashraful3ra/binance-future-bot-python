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
        timeframe_in_seconds = timeframe_map.get(bot.timeframe, 60)
        
        try:
            client.futures_change_leverage(symbol=symbol, leverage=bot.leverage)
            precision = get_symbol_precision(client, symbol)
        except Exception as e:
            print(f"Failed to set leverage for {symbol}: {e}")
            return

        while not stop_event.is_set():
            try:
                # --- STEP 1: SYNCHRONIZE WITH THE NEXT CANDLE (PRECISION TIMING) ---
                # This logic is now at the START of the loop.
                server_time_ms = client.get_server_time()['serverTime']
                time_to_wait_ms = (timeframe_in_seconds * 1000) - (server_time_ms % (timeframe_in_seconds * 1000))
                time_to_wait_sec = time_to_wait_ms / 1000
                
                print(f"Bot '{bot.name}' ({symbol}): Synchronizing... Waiting for {time_to_wait_sec:.2f} seconds until the next new candle.")
                
                # Wait for the calculated duration. If a stop signal comes, exit the loop.
                if stop_event.wait(time_to_wait_sec):
                    break

                # --- STEP 2: EXECUTE TRADE CYCLE AT THE EXACT CANDLE OPEN ---
                # At this point, a new candle has just opened.
                
                # First, close any existing position from the previous candle
                position_amount = 0.0
                entry_price = 0.0
                positions = client.futures_position_information(symbol=symbol)

                if positions:
                    position_amount = float(positions[0]['positionAmt'])
                    entry_price = float(positions[0]['entryPrice'])

                if position_amount != 0:
                    close_side = Client.SIDE_SELL if position_amount > 0 else Client.SIDE_BUY
                    print(f"Bot '{bot.name}' ({symbol}): Closing previous position of {position_amount}...")
                    client.futures_create_order(symbol=symbol, side=close_side, type=Client.ORDER_TYPE_MARKET, quantity=abs(position_amount))
                    time.sleep(2) # Allow order to fill
                    # PNL logging logic here...

                # Second, analyze the just-closed candle and open a new trade
                klines = client.futures_klines(symbol=symbol, interval=bot.timeframe, limit=2)
                if len(klines) < 2:
                    print(f"Bot '{bot.name}' ({symbol}): Not enough historical data. Waiting for next cycle.")
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
                    print(f"Bot '{bot.name}' ({symbol}): No trade condition met for new candle.")

            except Exception as e:
                print(f"Error in trade cycle for Bot '{bot.name}': {e}")
                # Wait for a short period before retrying the next full cycle
                stop_event.wait(30)
    
    print(f"🛑 Trader for {symbol} under Bot '{bot.name}' stopped.")