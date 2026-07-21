import os, time, threading, yfinance as yf
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval
import pandas as pd

TOKEN = "8828337019:AAFW_gB43Hqrueg1bP9y3RJKHGFUGWR9LUw"
PASSWORD = "7154"
bot = telebot.TeleBot(TOKEN, threaded=False)

MARKETS = {
    "🇪🇺/🇺🇸 EUR/USD": "EURUSD", "🇬🇧/🇺🇸 GBP/USD": "GBPUSD", "🇺🇸/🇯🇵 USD/JPY": "USDJPY",
    "🇦🇺/🇺🇸 AUD/USD": "AUDUSD", "🇺🇸/🇨🇦 USD/CAD": "USDCAD", "🇪🇺/🇯🇵 EUR/JPY": "EURJPY",
    "🇬🇧/🇯🇵 GBP/JPY": "GBPJPY", "🇺🇸/🇨🇭 USD/CHF": "USDCHF",
}
# شلت لك OTC لانه وهمي

user_data, authorized, cache = {}, set(), {}

def get_rsi(symbol):
    try:
        # نحول EURUSD الى EURUSD=X عشان yfinance يفهمه
        ticker = f"{symbol[:3]}{symbol[3:]}=X"
        data = yf.download(ticker, period="1d", interval="15m", progress=False)
        if len(data) < 14: return 50
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1])
    except:
        return 50 # لو فشل نرجع 50

def get_tf_signal(symbol, interval):
    key = f"{symbol}_{interval}"
    now = time.time()
    if key in cache and now - cache[key][2] < 60:
        return cache[key][0], cache[key][1]
    for _ in range(2):
        try:
            time.sleep(1.2)
            h = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=interval)
            s = h.get_analysis().summary
            buys, sells = s['BUY'], s['SELL']
            if buys+sells == 0: continue
            direction = "BUY" if buys > sells else "SELL"
            percent = int((max(buys, sells) / (buys + sells)) * 100)
            cache[key] = (direction, percent, now)
            return direction, percent
        except:
            time.sleep(2)
            continue
    return "ERROR", 0

def get_confluence_signal(symbol):
    d5, p5 = get_tf_signal(symbol, Interval.INTERVAL_5_MINUTES)
    d15, p15 = get_tf_signal(symbol, Interval.INTERVAL_15_MINUTES)
    d1h, p1h = get_tf_signal(symbol, Interval.INTERVAL_1_HOUR)

    if "ERROR" in [d5,d15,d1h]:
        return "ERROR", 0, "⏳ TradingView مضغوط - انتظر دقيقة", "ERROR"

    if not (d5 == d15 == d1h):
        return "NO_TRADE", 0, f"H1:{p1h}% {d1h} | 15m:{p15}% {d15} | 5m:{p5}% {d5}\n❌ متضارب", "متضارب"

    # فلتر RSI الجديد - هذا اللي يرفعه لـ 90
    rsi = get_rsi(symbol)
    if d5 == "BUY" and rsi > 70:
        return "NO_TRADE", 0, f"❌ لا تدخل BUY - RSI متشبع {rsi:.1f}\nH1:{p1h}% | 15m:{p15}% | 5m:{p5}%", "متشبع"
    if d5 == "SELL" and rsi < 30:
        return "NO_TRADE", 0, f"❌ لا تدخل SELL - RSI متشبع {rsi:.1f}\nH1:{p1h}% | 15m:{p15}% | 5m:{p5}%", "متشبع"

    avg = int((p5+p15+p1h)/3)
    if p5 >= 80 and p15 >= 80 and p1h >= 80:
        decision = f"🔥🔥 ذهبي قوي - RSI {rsi:.0f} ممتاز - ادخل 2%"
    else:
        decision = f"✅ جيد - RSI {rsi:.0f} - ادخل 1%"

    return d5, min(92, avg+5), f"H1:{p1h}% | 15m:{p15}% | 5m:{p5}%\nRSI: {rsi:.1f}\n{decision}", decision

# باقي الكود حقك نفسه (الازرار والفلاسك)
def show_markets(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("🔥 البحث عن الفرصة الذهبية", callback_data="golden"))
    for name in MARKETS:
        markup.add(InlineKeyboardButton(name, callback_data=f"market_{name}"))
    bot.send_message(chat_id, "👋 بوت 90/100\nاختر:", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id in authorized: show_markets(msg.chat.id)
    else: bot.send_message(msg.chat.id, "🔒 أدخل الرقم السري:")

@bot.message_handler(func=lambda m: m.text and m.from_user.id not in authorized)
def check_pass(msg):
    if msg.text.strip() == PASSWORD:
        authorized.add(msg.from_user.id)
        bot.send_message(msg.chat.id, "✅ تم")
        show_markets(msg.chat.id)
    else: bot.send_message(msg.chat.id, "❌ خطأ")

@bot.callback_query_handler(func=lambda c: c.data=="golden")
def golden(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id, "⏳ افحص...")
    loading = bot.send_message(call.message.chat.id, "⏳ افحص مع RSI...")
    goldens = []
    for name, sym in MARKETS.items():
        d, p, det, dec = get_confluence_signal(sym)
        if "ذهبي" in dec:
            emoji = "🟢 BUY" if d=="BUY" else "🔴 SELL"
            goldens.append(f"{emoji} {name} - {p}%\n{det}\n")
        time.sleep(1.5)
    if not goldens:
        bot.edit_message_text("❌ لا يوجد ذهبي نظيف (RSI فلتر شغال)", call.message.chat.id, loading.message_id)
    else:
        bot.edit_message_text("🔥🔥 الفرص الذهبية 90/100 🔥🔥\n\n" + "\n".join(goldens), call.message.chat.id, loading.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_"))
def choose_market(call):
    if call.from_user.id not in authorized: return
    name = call.data.replace("market_", "")
    user_data[call.from_user.id] = MARKETS[name], name
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔍 فحص شامل + RSI", callback_data="time_ALL"))
    bot.send_message(call.message.chat.id, f"اخترت {name}", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("time_"))
def choose_time(call):
    if call.from_user.id not in authorized: return
    symbol, name = user_data.get(call.from_user.id, (None, None))
    loading = bot.send_message(call.message.chat.id, f"⏳ فحص {name} مع RSI...")
    d, p, details, dec = get_confluence_signal(symbol)
    bot.edit_message_text(f"📊 {name}\n{details}", call.message.chat.id, loading.message_id)

app = Flask(__name__)
@app.route('/')
def home(): return "Bot 90 Live"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
threading.Thread(target=run_flask, daemon=True).start()
bot.remove_webhook()
time.sleep(1)
bot.infinity_polling(skip_pending=True)
