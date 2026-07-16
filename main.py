import os
import time
import threading
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval

TOKEN = "8828337019:AAHu5HxEgw5qFTeOd7DTWA1ELJXDH00yK1E"
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

# === الاضافات الاسطورية ===
GOLD_CONFIDENCE = 90
SLEEP_THRESHOLD = 55 # اذا كل الفريمات تحت 55 يعني السوق نايم

def check_market_sleep(p5, p15, p1h):
    # السوق نايم اذا كل الثقات ضعيفة
    return p5 < SLEEP_THRESHOLD and p15 < SLEEP_THRESHOLD and p1h < SLEEP_THRESHOLD

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

    # 1. فلتر السوق النايم
    if check_market_sleep(p5, p15, p1h):
        return "SLEEP", 0, f"5m:{p5}% | 15m:{p15}% | H1:{p1h}%"

    # 2. تطابق كامل = صفقة اسطورية
    if d5 == d15 == d1h and d5 not in ["ERROR", "NEUTRAL"]:
        avg_percent = int((p5 + p15 + p1h) / 3)
        final_percent = min(94, avg_percent + 12) # بوست اقوى
        return d5, final_percent, f"5m:{p5}% | 15m:{p15}% | H1:{p1h}% - تطابق كامل ✅"

    # 3. تطابق جزئي
    if d5 == d15 and d5 not in ["ERROR", "NEUTRAL"]:
        avg_percent = int((p5 + p15) / 2)
        return d5, avg_percent, f"5m:{p5}% | 15m:{p15}% | H1:{p1h}% {d1h} - تطابق جزئي ⚠️"

    return "NO_TRADE", 0, f"5m:{d5} {p5}% | 15m:{d15} {p15}% | H1:{d1h} {p1h}% - متضاربة ❌"

@bot.message_handler(commands=['start'])
def start(msg):
    markup = InlineKeyboardMarkup(row_width=2)
    for name in MARKETS:
        markup.add(InlineKeyboardButton(name, callback_data=f"market_{name}"))
    bot.send_message(msg.chat.id, "👋 البوت الاسطوري Triple TF + فلتر النوم\nاختر السوق:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_"))
def choose_market(call):
    bot.answer_callback_query(call.id)
    name = call.data.replace("market_", "")
    user_data[call.from_user.id] = MARKETS[name], name
    markup = InlineKeyboardMarkup(row_width=1)
    # خليناها زر واحد بس عشان ما تتلخبط - الشامل هو الصح
    markup.add(InlineKeyboardButton("🔍 فحص اسطوري شامل", callback_data="time_ALL"))
    bot.send_message(call.message.chat.id, f"اخترت {name}\nاضغط فحص:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("time_"))
def choose_time(call):
    user_id = call.from_user.id
    now = time.time()
    if user_id in last_request and now - last_request[user_id] < 5:
        bot.answer_callback_query(call.id, "⏳ انتظر")
        return
    last_request[user_id] = now
    bot.answer_callback_query(call.id)

    symbol, name = user_data.get(user_id, (None, None))
    if not symbol: return

    loading = bot.send_message(call.message.chat.id, f"⏳ جاري الفحص الاسطوري لـ {name}...")

    direction, percent, details = get_confluence_signal(symbol)

    if direction == "SLEEP":
        bot.edit_message_text(f"😴 {name}\n{details}\n\n💤 السوق نايم لا تدخل - انتظر 15 دقيقة", call.message.chat.id, loading.message_id)
        return

    if direction == "NO_TRADE":
        bot.edit_message_text(f"📊 {name}\n{details}\n\n❌ لا تدخل السوق متضارب", call.message.chat.id, loading.message_id)
        return

    if percent < 60:
        bot.edit_message_text(f"📊 {name}\n{details}\n\n⚠️ ثقة ضعيفة {percent}% لا تدخل", call.message.chat.id, loading.message_id)
        return

    # صياغة الرسالة الاسطورية
    is_gold = percent >= GOLD_CONFIDENCE and "تطابق كامل" in details
    emoji = "🟢 صعود BUY" if direction == "BUY" else "🔴 هبوط SELL"

    if is_gold:
        text = f"""🔥🔥🔥 صفقة ذهبية 🔥🔥🔥
📊 {name}

{emoji}
💎 الثقة: {percent}%
{details}

⏰ مدة الصفقة في بوكت اوبشن: 15 دقيقة
💰 هذي هي ادخل وانت مغمض"""
    else:
        text = f"""📊 {name} - فحص شامل
{emoji}
💪 الثقة: {percent}%

{details}

⏰ مدة الصفقة: 15 دقيقة
{"✅ تطابق كامل" if "تطابق كامل" in details else "⚠️ تطابق جزئي - ادخل بحذر"}"""

    bot.edit_message_text(text, call.message.chat.id, loading.message_id)

app = Flask(__name__)
@app.route('/')
def home(): return "Legendary Bot is Live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask, daemon=True).start()
bot.remove_webhook()
time.sleep(1)
bot.infinity_polling(skip_pending=True)
