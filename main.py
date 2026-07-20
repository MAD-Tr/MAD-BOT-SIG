import os
import time
import threading
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval

TOKEN = "8828337019:AAHu5HxEgw5qFTeOd7DTWA1ELJXDH00yK1E"
bot = telebot.TeleBot(TOKEN, threaded=False)

PASSWORD = "7154"
allowed = set()

def is_allowed(user_id):
    return user_id in allowed

@bot.message_handler(commands=['pass'])
def pass_check(m):
    parts = m.text.split()
    if len(parts) > 1 and parts[1] == PASSWORD:
        allowed.add(m.from_user.id)
        bot.reply_to(m, "✅ تم فتح البوت لك، اكتب /start")
    else:
        bot.reply_to(m, "❌ الرقم السري غلط")

@bot.message_handler(commands=['lock'])
def lock(m):
    allowed.discard(m.from_user.id)
    bot.reply_to(m, "🔒 قفلت البوت")

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

def get_tf_signal(symbol, interval):
    try:
        h = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=interval)
        s = h.get_analysis().summary
        buys, sells = s['BUY'], s['SELL']
        if buys+sells == 0: return "NEUTRAL", 50
        direction = "BUY" if buys > sells else "SELL"
        percent = int((max(buys, sells) / (buys + sells)) * 100)
        return direction, percent
    except:
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
        elif p5 >= 60 and p15 >= 60 and p1h >= 60:
            decision = "⚠️ دخول ضعيف - يفضل عدم الدخول"
        else:
            decision = "❌ لا تدخل - ثقة ضعيفة"
        avg = int((p5+p15+p1h)/3)
        final = min(94, avg+5)
        return d5, final, f"H1:{p1h}% | 15m:{p15}% | 5m:{p5}%\n{decision}", p5, p15, p1h
    return "NO_TRADE", 0, f"H1:{p1h}% {d1h} | 15m:{p15}% {d15} | 5m:{p5}% {d5}\n\n❌ لا تدخل - السوق متضارب", p5, p15, p1h

@bot.callback_query_handler(func=lambda c: c.data == "scan_golden")
def scan_golden(call):
    if not is_allowed(call.from_user.id):
        bot.answer_callback_query(call.id, "🔒 مقفل")
        return
    user_id = call.from_user.id
    now = time.time()
    if user_id in last_request and now - last_request[user_id] < 10:
        bot.answer_callback_query(call.id, "⏳ انتظر 10 ثواني")
        return
    last_request[user_id] = now
    bot.answer_callback_query(call.id, "🔍 بدأ الفحص...")
    loading = bot.send_message(call.message.chat.id, "🔍 جاري فحص كل الأسواق 5m+15m+1H...\nقد يأخذ 30 ثانية ⏳")
    golden_found = []
    for display_name, symbol in MARKETS.items():
        direction, percent, details, p5, p15, p1h = get_confluence_signal(symbol)
        if direction!= "NO_TRADE" and p5 >= 80 and p15 >= 80 and p1h >= 80:
            emoji = "🟢 صعود" if direction == "BUY" else "🔴 هبوط"
            golden_found.append(f"🔥 {display_name} {emoji} - ثقة {percent}%\n H1:{p1h}% | 15m:{p15}% | 5m:{p5}%")
    if golden_found:
        text = f"💎 وجدت {len(golden_found)} فرص ذهبية قوية جداً الآن:\n\n" + "\n\n".join(golden_found)
    else:
        text = "🔴 لا يوجد فرص ذهبية حالياً\nجرب بعد 5 دقايق"
    try:
        bot.edit_message_text(text, call.message.chat.id, loading.message_id)
    except:
        bot.send_message(call.message.chat.id, text)

@bot.message_handler(commands=['start'])
def start(msg):
    if not is_allowed(msg.from_user.id):
        bot.send_message(msg.chat.id, "🔒 البوت خاص\nادخل الرقم السري بهالطريقة:\n/pass الرقم")
        return
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("💎 بحث عن الفرص الذهبية 5m 15m 1h", callback_data="scan_golden"))
    for name in MARKETS:
        markup.add(InlineKeyboardButton(name, callback_data=f"market_{name}"))
    bot.send_message(msg.chat.id, "👋 بوت احترافي Triple TF\nاختر السوق أو ابحث عن الفرص الذهبية:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_"))
def choose_market(call):
    if not is_allowed(call.from_user.id):
        bot.answer_callback_query(call.id, "🔒 مقفل")
        return
    bot.answer_callback_query(call.id)
    name = call.data.replace("market_", "")
    user_data[call.from_user.id] = MARKETS[name], name
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔍 فحص شامل H1+15m+5m", callback_data="time_ALL"))
    markup.add(InlineKeyboardButton("5m فقط", callback_data="time_5"), InlineKeyboardButton("15m فقط", callback_data="time_15"))
    bot.send_message(call.message.chat.id, f"اخترت {name}\nاختر نوع الفحص:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("time_"))
def choose_time(call):
    if not is_allowed(call.from_user.id):
        bot.answer_callback_query(call.id, "🔒 مقفل")
        return
    user_id = call.from_user.id
    now = time.time()
    if user_id in last_request and now - last_request[user_id] < 5:
        bot.answer_callback_query(call.id, "⏳ انتظر")
        return
    last_request[user_id] = now
    bot.answer_callback_query(call.id)
    mode = call.data.replace("time_", "")
    symbol, name = user_data.get(user_id, (None, None))
    if not symbol: return
    loading = bot.send_message(call.message.chat.id, f"⏳ جاري فحص {name}...")
    if mode == "ALL":
        direction, percent, details, p5, p15, p1h = get_confluence_signal(symbol)
        if direction == "NO_TRADE":
            bot.edit_message_text(f"📊 {name}\n{details}", call.message.chat.id, loading.message_id)
            return
        emoji = "🟢 BUY صعود" if direction == "BUY" else "🔴 SELL هبوط"
        bot.edit_message_text(f"📊 {name}\n{emoji}\n💪 ثقة: {percent}%\n\n{details}", call.message.chat.id, loading.message_id)
    else:
        tf_map = {"5": Interval.INTERVAL_5_MINUTES, "15": Interval.INTERVAL_15_MINUTES}
        d, p = get_tf_signal(symbol, tf_map[mode])
        bot.edit_message_text(f"📊 {name} {mode}m\n{'🟢 BUY' if d=='BUY' else '🔴 SELL'}\n💪 {p}%\n\n{'✅ ادخل' if p>=80 else '❌ لا تدخل'}", call.message.chat.id, loading.message_id)

app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Live!"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask, daemon=True).start()
bot.remove_webhook()
time.sleep(1)
bot.infinity_polling(skip_pending=True)
