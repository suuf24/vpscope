import json
import requests
import time
from tradingview_ta import TA_Handler, Interval, Exchange
from dotenv import load_dotenv
import os
import logging
from datetime import datetime, timedelta
from threading import Thread

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID', "-1002436604197")  # Default channel ID if not set

# Files for managing trades
ACTIVE_TRADES_FILE = 'active_trades.json'
HISTORICAL_DATA_FILE = 'historical_data.json'
SUSPEND_PAIRS_FILE = 'suspend.json'

# Constants for trading logic
VOLUME_MULTIPLIER = 2.5

def validate_price(price):
    return isinstance(price, (int, float)) and price > 0

def validate_trade_params(trade_params):
    expected_keys = ['entry', 'stop_loss', 'take_profits', 'side']
    if not all(k in trade_params for k in expected_keys):
        return False

    if not validate_price(trade_params['entry']) or not validate_price(trade_params['stop_loss']):
        return False

    if not isinstance(trade_params['take_profits'], dict):
        return False

    for tp in trade_params['take_profits'].values():
        if not validate_price(tp):
            return False

    if trade_params['side'] not in ['long', 'short']:
        return False

    return True

def send_telegram_message(message, reply_to_message_id=None):
    try:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
            raise ValueError("Telegram bot token or channel ID not set.")

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHANNEL_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }
        if reply_to_message_id:
            payload['reply_to_message_id'] = reply_to_message_id

        max_retries = 3  # Number of times to retry in case of rate limit hit
        for attempt in range(max_retries):
            response = requests.post(url, json=payload)
            if response.status_code == 429:  # Rate limit error
                retry_after = response.headers.get('Retry-After')  # Check if there's a specific time to wait
                if retry_after:
                    wait_time = int(retry_after)
                else:
                    wait_time = 5  # Default wait time if not specified
                logger.info(f'Rate limit hit. Waiting {wait_time} seconds before retry...')
                time.sleep(wait_time)
            else:
                if response.status_code != 200:
                    logger.error(f'Failed to send Telegram message. Status code: {response.status_code}')
                break  # If the request was successful or any other error, break the loop
        else:
            logger.error('Failed to send Telegram message after all retries')

    except Exception as e:
        logger.error(f'Error sending Telegram message: {e}')

def custom_round(value):
    if value >= 1000:
        return round(value)
    elif value >= 100:
        return round(value, 2)
    elif value >= 10:
        return round(value, 3)
    elif value >= 1:
        return round(value, 3)
    elif value >= 0.1:
        return round(value, 5)
    else:
        return round(value, 6)

def load_active_trades():
    try:
        with open(ACTIVE_TRADES_FILE, 'r') as file:
            trades = json.load(file)
            # Validate each trade's parameters
            valid_trades = {k: v for k, v in trades.items() if validate_trade_params(v)}
            return valid_trades
    except Exception as e:
        logger.info('No existing or invalid active trades file found. Creating new.')
        return {}

def save_active_trades(trades):
    try:
        with open(ACTIVE_TRADES_FILE, 'w') as file:
            json.dump(trades, file, indent=4)
        logger.info(f'Saved {len(trades)} active trades')
    except Exception as e:
        logger.error(f'Error saving active trades: {e}')

def load_historical_data():
    try:
        with open(HISTORICAL_DATA_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_historical_data(data):
    with open(HISTORICAL_DATA_FILE, 'w') as file:
        json.dump(data, file, indent=4)

def load_suspended_pairs():
    try:
        with open(SUSPEND_PAIRS_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_suspended_pairs(pairs):
    with open(SUSPEND_PAIRS_FILE, 'w') as file:
        json.dump(pairs, file, indent=4)

def fetch_indicators(symbol, interval):
    try:
        handler = TA_Handler(
            symbol=symbol,
            screener="crypto",
            exchange="BYBIT",
            interval=interval
        )

        analysis = handler.get_analysis()
        indicators = {
            'close_price': analysis.indicators['close'],
            'ema5': analysis.indicators['EMA5'],
            'ema10': analysis.indicators['EMA10'],
            'ema20': analysis.indicators['EMA20'],
            'ema200': analysis.indicators['EMA200'],
            'RSI': analysis.indicators['RSI'],
            'RSI.prev': analysis.indicators.get('RSI[1]', None),  # Use get with a default value
            'MACD.macd': analysis.indicators['MACD.macd'],
            'MACD.signal': analysis.indicators['MACD.signal'],
            'BB.upper': analysis.indicators['BB.upper'],
            'BB.lower': analysis.indicators['BB.lower']
        }
        return indicators
    except Exception as e:
        logger.error(f'Error fetching indicators for {symbol} on {interval} timeframe: {e}')
        return None

def long_entry_conditions(indicators_5m, indicators_15m, indicators_30m, indicators_1h):
    bb_upper_5m = indicators_5m.get('BB.upper')
    
    return (
        bb_upper_5m is not None and (
            indicators_5m['close_price'] > indicators_5m['ema10'] > indicators_5m['ema20'] > indicators_5m['ema200'] and
            indicators_5m['RSI'] > 65 and
            (indicators_5m['ema10'] - indicators_5m['ema200']) / indicators_5m['ema10'] <= 0.025 and
            indicators_5m['MACD.macd'] > indicators_5m['MACD.signal'] and
            indicators_15m['close_price'] > indicators_15m['ema5'] > indicators_15m['ema200'] and
            indicators_15m['RSI.prev'] is not None and indicators_15m['RSI'] > indicators_15m['RSI.prev'] and
            indicators_30m['close_price'] > indicators_30m['ema5'] > indicators_30m['ema200'] and
            indicators_30m['RSI.prev'] is not None and indicators_30m['RSI'] > indicators_30m['RSI.prev'] and
            indicators_1h['close_price'] > indicators_1h['ema5'] > indicators_1h['ema200'] and
            indicators_1h['RSI.prev'] is not None and indicators_1h['RSI'] > indicators_1h['RSI.prev']
        )
    )

def short_entry_conditions(indicators_5m, indicators_15m, indicators_30m, indicators_1h):
    bb_lower_5m = indicators_5m.get('BB.lower')
    
    return (
        bb_lower_5m is not None and (
            indicators_5m['close_price'] < indicators_5m['ema10'] < indicators_5m['ema20'] < indicators_5m['ema200'] and
            indicators_5m['RSI'] < 35 and
            (indicators_5m['ema200'] - indicators_5m['ema10']) / indicators_5m['ema200'] <= 0.025 and
            indicators_5m['MACD.macd'] < indicators_5m['MACD.signal'] and
            indicators_15m['close_price'] < indicators_15m['ema5'] < indicators_15m['ema200'] and
            indicators_15m['RSI.prev'] is not None and indicators_15m['RSI'] < indicators_15m['RSI.prev'] and
            indicators_30m['close_price'] < indicators_30m['ema5'] < indicators_30m['ema200'] and
            indicators_30m['RSI.prev'] is not None and indicators_30m['RSI'] < indicators_30m['RSI.prev'] and
            indicators_1h['close_price'] < indicators_1h['ema5'] < indicators_1h['ema200'] and
            indicators_1h['RSI.prev'] is not None and indicators_1h['RSI'] < indicators_1h['RSI.prev']
        )
    )

def calculate_trade_parameters(indicators, side):
    close_price = indicators['close_price']
    if side == 'long':
        stoploss = custom_round(close_price * 0.98)  # Apply custom rounding to stop loss
        risk = close_price - stoploss
        tp1 = custom_round(close_price + (risk * 1.68))
        tp2 = custom_round(close_price + (risk * 2.68))
        tp3 = custom_round(close_price + (risk * 3.68))
    else:  # short
        stoploss = custom_round(close_price * 1.02)  # Apply custom rounding to stop loss
        risk = stoploss - close_price
        tp1 = custom_round(close_price - risk * 1.68)
        tp2 = custom_round(close_price - 2.68 * risk)
        tp3 = custom_round(close_price - 3.68 * risk)

    return {
        'entry': close_price,
        'stop_loss': stoploss,
        'take_profits': {
            'TP1': tp1,
            'TP2': tp2,
            'TP3': tp3
        }
    }
# ... (rest of the script remains unchanged)

import requests
from datetime import datetime

def add_new_trade(symbol, trade_params, active_trades, historical_data, side):
    emoji = '🟢' if side == 'long' else '🔴'
    message = f'*{emoji} {side.title()} Entry for {symbol}*\n\n*Entry:* `{trade_params["entry"]}`\n*Stop Loss:* `{trade_params["stop_loss"]}`\n*Take Profits:*\n  - TP1: `{trade_params["take_profits"]["TP1"]}`\n  - TP2: `{trade_params["take_profits"]["TP2"]}`\n  - TP3: `{trade_params["take_profits"]["TP3"]}`'
    
    try:
        # Send the message and get the message_id
        response = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json={
            'chat_id': TELEGRAM_CHANNEL_ID,
            'text': message,
            'parse_mode': 'Markdown',
            'reply_markup': {
                'inline_keyboard': [
                    [{
                        'text': 'View Chart on TradingView',
                        'url': f'https://www.tradingview.com/chart/?symbol=BYBIT%3A{symbol}&interval=5'
                    }]
                ]
            }
        })
        
        if response.status_code == 200:
            entry_message_id = response.json()['result']['message_id']
            trade_params['entry_message_id'] = entry_message_id
            logger.info(f"Entry message ID stored for {symbol}: {entry_message_id}")
        else:
            logger.error(f"Failed to send entry message for {symbol}. Status code: {response.status_code}")
    
    except Exception as e:
        logger.error(f"Failed to send Telegram message for {symbol}: {e}")
    
    trade_params['side'] = side
    trade_params['start_time'] = datetime.now().isoformat()
    trade_params['status'] = 'open'

    active_trades[symbol] = trade_params
    historical_data.setdefault(symbol, []).append({**trade_params, 'end_time': None, 'result': 'pending'})
    logger.info(f"Added new trade to active_trades: {symbol}")
    # Ensure save happens after adding a trade
    save_active_trades(active_trades)
    save_historical_data(historical_data)

def update_trade_status(trade, indicators, symbol, historical_data, active_trades, suspended_pairs):
    closed = False
    result = None
    current_price = indicators['close_price']
    entry_price = trade['entry']

    if trade['side'] == 'long':
        if current_price <= trade['stop_loss']:
            closed = True
            result = 'loss'
            if 'sl_message_sent' not in trade:
                message = f'🚨 *{symbol} Stop Loss Hit!* 🚨\n\n*Entry:* `{entry_price}`\n*Stop Loss:* `{trade["stop_loss"]}`\n*Current Price:* `{current_price}`'
                send_telegram_message(message, reply_to_message_id=trade.get('entry_message_id'))
                trade['sl_message_sent'] = True
            trade['status'] = 'closed'
            trade['end_time'] = datetime.now().isoformat()  # Set end_time for loss
            logger.info(f"SL message for long trade {symbol} sent")
        else:
            tp1_price = trade['take_profits']['TP1']
            if current_price >= tp1_price and 'TP1' not in trade.get('hit_tps', []):
                percentage_gain = ((current_price - entry_price) / entry_price) * 100
                message = f'💸 *{symbol} TP1 Hit!* ({percentage_gain:.2f}% from entry)\n\n*Entry:* `{entry_price}`\n*TP1:* `{tp1_price}`\n*Current Price:* `{current_price}`\n'
                send_telegram_message(message, reply_to_message_id=trade.get('entry_message_id'))

                trade.setdefault('hit_tps', []).append('TP1')
                
                # Close the trade immediately upon hitting TP1
                closed = True
                result = 'win'
                trade['status'] = 'closed'
                trade['end_time'] = datetime.now().isoformat()  # Set end_time for win
                
                # Move trade to suspend.json with a 2-hour suspension
                with open('suspend.json', 'r+') as f:
                    try:
                        current_suspend = json.load(f)
                    except json.JSONDecodeError:
                        current_suspend = {}
                    current_suspend[symbol] = {
                        'trade': trade,
                        'suspend_until': (datetime.now() + timedelta(hours=2)).isoformat()
                    }  
                    f.seek(0)
                    json.dump(current_suspend, f, indent=4)
                    f.truncate()
                
                logger.info(f"Trade for {symbol} closed at TP1 and moved to suspend.json")

    elif trade['side'] == 'short':
        if current_price >= trade['stop_loss']:
            closed = True
            result = 'loss'
            if 'sl_message_sent' not in trade:
                message = f'🚨 *{symbol} Stop Loss Hit!* 🚨\n\n*Entry:* `{entry_price}`\n*Stop Loss:* `{trade["stop_loss"]}`\n*Current Price:* `{current_price}`'
                send_telegram_message(message, reply_to_message_id=trade.get('entry_message_id'))
                trade['sl_message_sent'] = True
            trade['status'] = 'closed'
            trade['end_time'] = datetime.now().isoformat()  # Set end_time for loss
            logger.info(f"SL message for short trade {symbol} sent")
        else:
            tp1_price = trade['take_profits']['TP1']
            if current_price <= tp1_price and 'TP1' not in trade.get('hit_tps', []):
                percentage_gain = ((entry_price - current_price) / entry_price) * 100
                message = f'💸 *{symbol} TP1 Hit!* ({percentage_gain:.2f}% from entry)\n\n*Entry:* `{entry_price}`\n*TP1:* `{tp1_price}`\n*Current Price:* `{current_price}`\n'
                send_telegram_message(message, reply_to_message_id=trade.get('entry_message_id'))

                trade.setdefault('hit_tps', []).append('TP1')
                
                # Close the trade immediately upon hitting TP1
                closed = True
                result = 'win'
                trade['status'] = 'closed'
                trade['end_time'] = datetime.now().isoformat()  # Set end_time for win
                
                # Move trade to suspend.json with a 2-hour suspension
                with open('suspend.json', 'r+') as f:
                    try:
                        current_suspend = json.load(f)
                    except json.JSONDecodeError:
                        current_suspend = {}
                    current_suspend[symbol] = {
                        'trade': trade,
                        'suspend_until': (datetime.now() + timedelta(hours=2)).isoformat()
                    }
                    f.seek(0)
                    json.dump(current_suspend, f, indent=4)
                    f.truncate()
                
                logger.info(f"Trade for {symbol} closed at TP1 and moved to suspend.json")

    if closed:
        # Update historical data
        for hist_trade in historical_data[symbol]:
            if hist_trade['status'] == 'open' and hist_trade['start_time'] == trade['start_time']:
                if 'end_time' in trade:
                    hist_trade['end_time'] = trade['end_time']
                else:
                    logger.error(f"Trade for {symbol} closed without setting end_time")
                    hist_trade['end_time'] = datetime.now().isoformat()  # Fallback if end_time not set
                hist_trade['result'] = result
                break
        if result == 'win':
            send_telegram_message(f'*Trade for {symbol} closed with a win!*', reply_to_message_id=trade.get('entry_message_id'))
        
        # Remove from active trades whether it's a win or loss
        del active_trades[symbol]  
        save_active_trades(active_trades)
        save_historical_data(historical_data)
    return closed

def sleep_until_next_5_minute_interval():
    now = datetime.now()
    seconds_until_next_interval = (5 - now.minute % 5) * 60 - now.second
    logger.info(f"Sleeping for {seconds_until_next_interval} seconds until the next 5-minute interval.")
    time.sleep(seconds_until_next_interval)

def process_new_trades(active_trades, historical_data, suspended_pairs):
    try:
        with open('lists.json', 'r') as file:
            data = json.load(file)
            coin_pairs = data['coin_pairs']

        current_time = datetime.now()

        # Remove pairs from suspend list if their suspension time has passed
        expired_suspended = {k: v for k, v in suspended_pairs.items() if current_time >= datetime.fromisoformat(v['suspend_until'])}
        for symbol in expired_suspended:
            del suspended_pairs[symbol]
        save_suspended_pairs(suspended_pairs)

        for symbol in coin_pairs:
            logger.info(f'🔍 Scanning {symbol} for new trade entry')  # New log message for each pair
            
            if symbol in suspended_pairs:
                logger.info(f"Skipping suspended pair: {symbol}")
                continue  # Skip if still suspended

            if symbol in active_trades:
                logger.info(f"Trade already active for {symbol}")
                continue  # Skip if the symbol is already in active trades

            # Fetch indicators for different timeframes
            indicators_5m = fetch_indicators(symbol, Interval.INTERVAL_5_MINUTES)
            indicators_15m = fetch_indicators(symbol, Interval.INTERVAL_15_MINUTES)
            indicators_30m = fetch_indicators(symbol, Interval.INTERVAL_30_MINUTES)
            indicators_1h = fetch_indicators(symbol, Interval.INTERVAL_1_HOUR)

            if any(indicator is None for indicator in [indicators_5m, indicators_15m, indicators_30m, indicators_1h]):
                logger.error(f"Failed to fetch all required indicators for {symbol}")
                continue

            if long_entry_conditions(indicators_5m, indicators_15m, indicators_30m, indicators_1h):
                trade_params = calculate_trade_parameters(indicators_5m, 'long')
                add_new_trade(symbol, trade_params, active_trades, historical_data, 'long')
                logger.info(f"Long entry condition met for {symbol}")
            elif short_entry_conditions(indicators_5m, indicators_15m, indicators_30m, indicators_1h):
                trade_params = calculate_trade_parameters(indicators_5m, 'short')
                add_new_trade(symbol, trade_params, active_trades, historical_data, 'short')
                logger.info(f"Short entry condition met for {symbol}")

    except Exception as e:
        logger.error(f'Error in process_new_trades: {e}')

    # Ensure trades are saved after processing
    save_active_trades(active_trades)
    save_historical_data(historical_data)

def manage_active_trades(active_trades, historical_data, suspended_pairs):
    while True:
        for symbol in list(active_trades.keys()):  # Use list() to avoid modifying dict during iteration
            try:
                indicators = fetch_indicators(symbol, Interval.INTERVAL_5_MINUTES)
                if indicators:
                    if symbol in active_trades:  # Check if trade still exists before updating
                        trade = active_trades[symbol]
                        if trade['status'] == 'closed':
                            # If the trade is already marked as closed, handle according to its result
                            if 'result' in trade and trade['result'] == 'win':
                                # This is for TP1 hits - move to suspend.json
                                with open('suspend.json', 'r+') as f:
                                    try:
                                        current_suspend = json.load(f)
                                    except json.JSONDecodeError:
                                        current_suspend = {}
                                    current_suspend[symbol] = {
                                        'trade': trade,
                                        'suspend_until': (datetime.now() + timedelta(hours=2)).isoformat()
                                    }
                                    f.seek(0)
                                    json.dump(current_suspend, f, indent=4)
                                    f.truncate()
                                logger.info(f"Closed trade for {symbol} moved to suspend.json after TP1 hit")
                            # Regardless of win or loss, remove from active trades
                            del active_trades[symbol]
                            logger.info(f"Removed closed trade for {symbol} from active trades")
                            save_active_trades(active_trades)
                            save_historical_data(historical_data)
                        else:
                            # If the trade is not closed, proceed with the normal update
                            if update_trade_status(trade, indicators, symbol, historical_data, active_trades, suspended_pairs):
                                logger.info(f"Trade for {symbol} was closed.")
                            else:
                                logger.info(f"No updates for {symbol} trade.")
            except Exception as e:
                logger.error(f"Error managing trade for {symbol}: {e}")
        time.sleep(10)  # Check active trades every 10 seconds

def main():
    logger.info('🚀 Trading Bot Started 🚀')
    active_trades = load_active_trades()
    historical_data = load_historical_data()
    suspended_pairs = load_suspended_pairs()

    # Start the thread for managing active trades
    manage_trades_thread = Thread(target=manage_active_trades, args=(active_trades, historical_data, suspended_pairs), daemon=True)
    manage_trades_thread.start()

    while True:
        # Process new trades every 5 minutes
        process_new_trades(active_trades, historical_data, suspended_pairs)
        sleep_until_next_5_minute_interval()

if __name__ == "__main__":
    main()
