import os
import time
import threading
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval

TOKEN = "8828337019:AAFW_gB43Hqrueg1bP9y3RJKHGFUGWR9LUw"
PASSWORD = "7154" # <-- غير هذا لرقمك السري
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
authorized = set() # الناس اللي دخلوا الباسوورد صح

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
        return d5, final, f"H1:{p1h}% | 15m:{p15}% | 5m:{p5}%\n{decision}", decision
    return "NO_TRADE", 0, f"H1:{p1h}% {d1h} | 15m:{p15}% {d15} | 5m:{p5}% {d5}\n\n❌ لا تدخل - السوق متضارب", "متضارب"

def show_markets(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("🔥 البحث عن الفرصة الذهبية (5m+15m+1h)", callback_data="golden"))
    for name in MARKETS:
        markup.add(InlineKeyboardButton(name, callback_data=f"market_{name}"))
    bot.send_message(chat_id, "👋 بوت احترافي Triple TF\nاختر:", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id in authorized:
        show_markets(msg.chat.id)
    else:
        bot.send_message(msg.chat.id, "🔒 البوت محمي\nأدخل الرقم السري:")

@bot.message_handler(func=lambda m: m.text and m.from_user.id not in authorized)
def check_pass(msg):
    if msg.text.strip() == PASSWORD:
        authorized.add(msg.from_user.id)
        bot.send_message(msg.chat.id, "✅ تم فتح البوت")
        show_markets(msg.chat.id)
    else:
        bot.send_message(msg.chat.id, "❌ رقم سري خطأ - حاول مرة ثانية")

@bot.callback_query_handler(func=lambda c: c.data=="golden")
def golden(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id, "⏳ افحص 25 سوق...")
    loading = bot.send_message(call.message.chat.id, "⏳ جاري فحص 25 سوق 5m+15m+1h...")
    goldens = []
    for name, sym in MARKETS.items():
        d, p, det, dec = get_confluence_signal(sym)
        if "ذهبي" in dec:
            emoji = "🟢 BUY" if d=="BUY" else "🔴 SELL"
            goldens.append(f"{emoji} {name} - {p}%\n{det}\n")
        time.sleep(0.4)
    if not goldens:
        bot.edit_message_text("❌ لا يوجد فرص ذهبية الان", call.message.chat.id, loading.message_id)
    else:
        txt = "🔥🔥 الفرص الذهبية 🔥🔥\n\n" + "\n".join(goldens)
        bot.edit_message_text(txt, call.message.chat.id, loading.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_"))
def choose_market(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    name = call.data.replace("market_", "")
    user_data[call.from_user.id] = MARKETS[name], name
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔍 فحص شامل H1+15m+5m", callback_data="time_ALL"))
    markup.add(InlineKeyboardButton("5m فقط", callback_data="time_5"), InlineKeyboardButton("15m فقط", callback_data="time_15"))
    bot.send_message(call.message.chat.id, f"اخترت {name}\nاختر نوع الفحص:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("time_"))
def choose_time(call):
    if call.from_user.id not in authorized: return
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
        direction, percent, details, dec = get_confluence_signal(symbol)
        if direction == "NO_TRADE":
            bot.edit_message_text(f"📊 {name}\n{details}", call.message.chat.id, loading.message_id)
            return
        emoji = "🟢 BUY صعود" if direction == "BUY" else "🔴 SELL هبوط"
        bot.edit_message_text(f"📊 {name}\n{emoji}\n💪 ثقة: {percent}%\n\n{details}", call.message.chat.id, loading.message_id)
    else:
        tf_map = {"5": Interval.INTERVAL_5_MINUTES, "15": Interval.INTERVAL_15_MINUTES}
        d, p = get_tf_signal(symbol, tf_map)
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
