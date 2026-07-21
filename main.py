import os
import time
import threading
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval

TOKEN = "8828337019:AAFW_gB43Hqrueg1bP9y3RJKHGFUGWR9LUw"
PASSWORD = "7154"
bot = telebot.TeleBot(TOKEN, threaded=False)

MARKETS = {
    "🇪🇺/🇺🇸 EUR/USD": "EURUSD", "🇬🇧/🇺🇸 GBP/USD": "GBPUSD", "🇺🇸/🇯🇵 USD/JPY": "USDJPY",
    "🇦🇺/🇺🇸 AUD/USD": "AUDUSD", "🇺🇸/🇨🇦 USD/CAD": "USDCAD", "🇪🇺/🇯🇵 EUR/JPY": "EURJPY",
    "🇨🇦/🇯🇵 CAD/JPY": "CADJPY", "🇪🇺/🇬🇧 EUR/GBP": "EURGBP", "🇦🇺/🇯🇵 AUD/JPY": "AUDJPY",
    "🇳🇿/🇺🇸 NZD/USD": "NZDUSD", "🇪🇺/🇨🇭 EUR/CHF": "EURCHF", "🇬🇧/🇯🇵 GBP/JPY": "GBPJPY",
    "🇦🇺/🇨🇦 AUD/CAD": "AUDCAD", "🇪🇺/🇦🇺 EUR/AUD": "EURAUD", "🇬🇧/🇨🇭 GBP/CHF": "GBPCHF",
    "🇺🇸/🇨🇭 USD/CHF": "USDCHF", "🇪🇺/🇨🇦 EUR/CAD": "EURCAD", "🇦🇺/🇨🇭 AUD/CHF": "AUDCHF",
    "🇬🇧/🇦🇺 GBP/AUD": "GBPAUD", "🇨🇦/🇨🇭 CAD/CHF": "CADCHF", "🇪🇺/🇳🇿 EUR/NZD": "EURNZD",
    "🇬🇧/🇳🇿 GBP/NZD": "GBPNZD",
    "🇪🇺/🇺🇸 EUR/USD OTC": "EURUSD", "🇬🇧/🇺🇸 GBP/USD OTC": "GBPUSD", "🇺🇸/🇯🇵 USD/JPY OTC": "USDJPY"
}

user_data = {}
last_request = {}
authorized = set()
cache = {}

def get_tf_signal(symbol, interval):
    key = f"{symbol}_{interval}"
    now = time.time()
    if key in cache and now - cache[key][2] < 60:
        return cache[key][0], cache[key][1]
    for _ in range(3):
        try:
            time.sleep(1.2) # <-- هذا السطر الجديد اللي يمنع البلوك
            h = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=interval)
            s = h.get_analysis().summary
            buys, sells = s['BUY'], s['SELL']
            if buys+sells == 0:
                time.sleep(1)
                continue
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
    if d5 == d15 == d1h and d5!= "ERROR":
        if p5 >= 80 and p15 >= 80 and p1h >= 80:
            decision = "🔥🔥 دخول قوي ذهبي - ادخل 2% 🔥🔥"
        elif p5 >= 75 and p15 >= 75 and p1h >= 70:
            decision = "✅ دخول جيد - ادخل 1% بحذر"
        else:
            decision = "⚠️ دخول ضعيف"
        avg = int((p5+p15+p1h)/3)
        return d5, min(94, avg+5), f"H1:{p1h}% | 15m:{p15}% | 5m:{p5}%\n{decision}", decision
    return "NO_TRADE", 0, f"H1:{p1h}% {d1h} | 15m:{p15}% {d15} | 5m:{p5}% {d5}\n\n❌ لا تدخل - السوق متضارب", "متضارب"

def show_markets(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("🔥 البحث عن الفرصة الذهبية", callback_data="golden"))
    for name in MARKETS:
        markup.add(InlineKeyboardButton(name, callback_data=f"market_{name}"))
    bot.send_message(chat_id, "👋 بوت احترافي\nاختر:", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id in authorized:
        show_markets(msg.chat.id)
    else:
        bot.send_message(msg.chat.id, "🔒 أدخل الرقم السري:")

@bot.message_handler(func=lambda m: m.text and m.from_user.id not in authorized)
def check_pass(msg):
    if msg.text.strip() == PASSWORD:
        authorized.add(msg.from_user.id)
        bot.send_message(msg.chat.id, "✅ تم فتح البوت")
        show_markets(msg.chat.id)
    else:
        bot.send_message(msg.chat.id, "❌ خطأ")

@bot.callback_query_handler(func=lambda c: c.data=="golden")
def golden(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id, "⏳ افحص...")
    loading = bot.send_message(call.message.chat.id, "⏳ جاري فحص 25 سوق...")
    goldens = []
    for name, sym in MARKETS.items():
        d, p, det, dec = get_confluence_signal(sym)
        if "ذهبي" in dec:
            emoji = "🟢 BUY" if d=="BUY" else "🔴 SELL"
            goldens.append(f"{emoji} {name} - {p}%\n{det}\n")
        time.sleep(1.2) # <-- وهذا السطر الثاني اللي عدلته
    if not goldens:
        bot.edit_message_text("❌ لا يوجد فرص ذهبية الان", call.message.chat.id, loading.message_id)
    else:
        bot.edit_message_text("🔥🔥 الفرص الذهبية 🔥🔥\n\n" + "\n".join(goldens), call.message.chat.id, loading.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_"))
def choose_market(call):
    if call.from_user.id not in authorized: return
    name = call.data.replace("market_", "")
    user_data[call.from_user.id] = MARKETS[name], name
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔍 فحص شامل H1+15m+5m", callback_data="time_ALL"))
    bot.send_message(call.message.chat.id, f"اخترت {name}", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("time_"))
def choose_time(call):
    if call.from_user.id not in authorized: return
    symbol, name = user_data.get(call.from_user.id, (None, None))
    loading = bot.send_message(call.message.chat.id, f"⏳ جاري فحص {name}...")
    d, p, details, dec = get_confluence_signal(symbol)
    if d == "NO_TRADE":
        bot.edit_message_text(f"📊 {name}\n{details}", call.message.chat.id, loading.message_id)
    else:
        emoji = "🟢 BUY" if d == "BUY" else "🔴 SELL"
        bot.edit_message_text(f"📊 {name}\n{emoji} {p}%\n{details}", call.message.chat.id, loading.message_id)

app = Flask(__name__)
@app.route('/')
def home(): return "Bot Live"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
threading.Thread(target=run_flask, daemon=True).start()
bot.remove_webhook()
time.sleep(1)
bot.infinity_polling(skip_pending=True)
