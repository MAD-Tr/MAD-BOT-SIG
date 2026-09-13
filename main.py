"""
M2NRU LEGENDARY HYBRID BOT - Pocket Option
Real Markets from TradingView + OTC Markets from Binance
Token: 8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes
Secret: 7154
"""
import requests, time, threading, os
import pandas as pd
from flask import Flask, request
from datetime import datetime

app = Flask(__name__)

# ========== الإعدادات ==========
BOT_TOKEN = "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
CHAT_ID = "YOUR_CHAT_ID" # روح ل @userinfobot وجيب الايدي حقك وحطه هنا
SECRET_KEY = "7154"

# جميع الأسواق الحقيقية في بوكت أوبشن
REAL_MARKETS = [
    "🇪🇺/🇺🇸 EUR/USD", "🇬🇧/🇺🇸 GBP/USD", "🇺🇸/🇯🇵 USD/JPY", "🇦🇺/🇺🇸 AUD/USD",
    "🇺🇸/🇨🇦 USD/CAD", "🇺🇸/🇨🇭 USD/CHF", "🇪🇺/🇯🇵 EUR/JPY", "🇬🇧/🇯🇵 GBP/JPY",
    "🇪🇺/🇬🇧 EUR/GBP", "🇦🇺/🇯🇵 AUD/JPY", "🇪🇺/🇦🇺 EUR/AUD", "🇬🇧/🇦🇺 GBP/AUD",
    "🇪🇺/🇨🇦 EUR/CAD", "🇳🇿/🇺🇸 NZD/USD", "🇪🇺/🇨🇭 EUR/CHF", "🇬🇧/🇨🇭 GBP/CHF",
    "💰 XAU/USD (ذهب)", "💰 XAG/USD (فضة)", "🛢️ USOIL", "₿ BTC/USD", "Ξ ETH/USD"
]

# جميع أسواق OTC
OTC_MARKETS_LIST = [
    "🇪🇺/🇺🇸 EUR/USD (OTC)", "🇬🇧/🇺🇸 GBP/USD (OTC)", "🇺🇸/🇯🇵 USD/JPY (OTC)",
    "🇦🇺/🇺🇸 AUD/USD (OTC)", "🇺🇸/🇨🇭 USD/CHF (OTC)", "🇪🇺/🇯🇵 EUR/JPY (OTC)",
    "🇬🇧/🇯🇵 GBP/JPY (OTC)", "🇦🇺/🇯🇵 AUD/JPY (OTC)", "🇪🇺/🇬🇧 EUR/GBP (OTC)",
    "🇳🇿/🇺🇸 NZD/USD (OTC)", "🇪🇺/🇦🇺 EUR/AUD (OTC)", "🇬🇧/🇦🇺 GBP/AUD (OTC)",
    "🇺🇸/🇨🇦 USD/CAD (OTC)", "💵/🇲🇽 USD/MXN (OTC)", "₿ BTC/USD (OTC)",
    "Ξ ETH/USD (OTC)", "🪙 BNB/USD (OTC)", "🪙 SOL/USD (OTC)"
]

# ربط الـ OTC مع بينانس
OTC_BINANCE_MAP = {
    "EUR/USD (OTC)": "EURUSDT",
    "GBP/USD (OTC)": "GBPUSDT", 
    "USD/JPY (OTC)": "BTCUSDT", # نستخدم BTC كمحرك قوي للـ OTC
    "AUD/USD (OTC)": "AUDUSDT",
    "USD/CHF (OTC)": "ETHUSDT",
    "EUR/JPY (OTC)": "EURUSDT",
    "GBP/JPY (OTC)": "GBPUSDT",
    "AUD/JPY (OTC)": "AUDUSDT",
    "BTC/USD (OTC)": "BTCUSDT",
    "ETH/USD (OTC)": "ETHUSDT",
}

BINANCE_SYMBOLS_TO_WATCH = ["BTCUSDT", "ETHUSDT", "EURUSDT", "GBPUSDT", "AUDUSDT", "BNBUSDT", "SOLUSDT"]

TIMEFRAME = "1m"
COOLDOWN = 120
last_signal_time = {}
user_settings = {"mode": "ALL"} # ALL, REAL, OTC

def get_telegram_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🟢 تفعيل الأسواق الحقيقية فقط", "callback_data": "mode_REAL"},
             {"text": "🔵 تفعيل أسواق OTC فقط", "callback_data": "mode_OTC"}],
            [{"text": "👑 تفعيل الكل (أسطوري)", "callback_data": "mode_ALL"}],
            [{"text": "📊 حالة البوت", "callback_data": "status"}]
        ]
    }

def send_telegram(pair, action, source, price, rsi_val, market_flag="REAL"):
    # فلترة حسب اختيار المستخدم
    if user_settings["mode"] == "REAL" and market_flag == "OTC":
        return
    if user_settings["mode"] == "OTC" and market_flag == "REAL":
        return

    if action == "BUY":
        direction = "🟢 صعود - CALL"
        color = "🟢🟢🟢"
    else:
        direction = "🔴 هبوط - PUT"
        color = "🔴🔴🔴"

    market_type = "سوق حقيقي REAL" if market_flag == "REAL" else "سوق OTC"

    msg = f"""
{color}
**إشارة {market_type} وصلت!**

{pair}
📊 الاتجاه: **{direction}**
💰 السعر: `{price}`
📈 RSI: `{rsi_val}`
🏦 المصدر: `{source}`
⏰ المدة: 1M - 3M

⚡️ **ادخل الآن في Pocket Option**
"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    keyboard = {
        "inline_keyboard": [[
            {"text": "🚀 افتح بوكت أوبشن", "url": "https://pocketoption.com/"},
            {"text": "📈 شارت إضافي", "url": f"https://www.tradingview.com/chart/?symbol=BINANCE%3A{source}"}
        ]]
    }
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "reply_markup": keyboard})
    except Exception as e:
        print(e)

# Webhook للأسواق الحقيقية من TradingView
@app.route('/webhook', methods=['POST'])
@app.route('/webhook/tradingview', methods=['POST'])
def tradingview_webhook():
    if request.args.get('key') != SECRET_KEY:
        return "Unauthorized - Wrong Key", 401
    data = request.get_json(silent=True) or {}
    print(f"REAL SIGNAL: {data}")
    pair_raw = data.get('pair', 'EUR/USD')
    # اضافة علم
    pair = f"🇪🇺/🇺🇸 {pair_raw}" if "EURUSD" in pair_raw else pair_raw
    action = data.get('action', 'BUY').upper()
    price = data.get('price', '---')
    send_telegram(pair, action, "TRADINGVIEW", price, "TV", "REAL")
    return "OK", 200

# محرك OTC
def get_binance_klines(symbol, limit=100):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={TIMEFRAME}&limit={limit}"
        r = requests.get(url, timeout=5)
        data = r.json()
        if isinstance(data, dict): return None
        df = pd.DataFrame(data, columns=['time','open','high','low','close','vol','ct','qa','nt','tb','tq','i'])
        df['close'] = df['close'].astype(float)
        return df
    except Exception as e:
        print(f"Binance Error {symbol}: {e}")
        return None

def analyze_otc():
    print("OTC Engine Started...")
    while True:
        for otc_name, binance_symbol in OTC_BINANCE_MAP.items():
            df = get_binance_klines(binance_symbol)
            if df is None or len(df) < 30: continue
            
            df['ema9'] = df['close'].ewm(span=9).mean()
            df['ema21'] = df['close'].ewm(span=21).mean()
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            last = df.iloc[-1]
            prev = df.iloc[-2]
            price = round(last['close'], 5)
            rsi_val = round(last['rsi'], 1)

            action = None
            if prev['ema9'] < prev['ema21'] and last['ema9'] > last['ema21'] and 50 < last['rsi'] < 70:
                action = "BUY"
            elif prev['ema9'] > prev['ema21'] and last['ema9'] < last['ema21'] and 30 < last['rsi'] < 50:
                action = "SELL"

            if action:
                now = time.time()
                if otc_name not in last_signal_time or now - last_signal_time[otc_name] > COOLDOWN:
                    last_signal_time[otc_name] = now
                    # نضيف العلم
                    flag_pair = f"🔵 {otc_name}"
                    send_telegram(flag_pair, action, binance_symbol, price, rsi_val, "OTC")
        time.sleep(10)

# استقبال ضغطات الأزرار
@app.route('/webhook/telegram', methods=['POST'])
def telegram_updates():
    data = request.get_json()
    if "callback_query" in data:
        cq = data["callback_query"]
        mode = cq["data"].replace("mode_", "")
        chat_id = cq["message"]["chat"]["id"]
        
        if mode in ["REAL", "OTC", "ALL"]:
            user_settings["mode"] = mode
            text = f"تم ✅ الآن البوت يرسل إشارات: {mode}"
        else:
            text = f"👑 البوت شغال\nالوضع الحالي: {user_settings['mode']}\nOTC: {len(OTC_BINANCE_MAP)} زوج\nREAL: TradingView Webhook"
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
        requests.post(url, json={"callback_query_id": cq["id"], "text": text})
        
        url2 = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url2, json={"chat_id": chat_id, "text": text, "reply_markup": get_telegram_keyboard()})
    elif "message" in data:
        msg = data["message"]
        if msg.get("text") == "/start":
            url2 = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            requests.post(url2, json={
                "chat_id": msg["chat"]["id"], 
                "text": "👑 أهلاً بك في بوت M2NRU الأسطوري\n\nاختر نوع السوق:", 
                "reply_markup": get_telegram_keyboard()
            })
    return "OK"

threading.Thread(target=analyze_otc, daemon=True).start()

@app.route('/')
def home():
    return f"Legendary Bot Running | Mode: {user_settings['mode']} | Real: {len(REAL_MARKETS)} | OTC: {len(OTC_MARKETS_LIST)}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
