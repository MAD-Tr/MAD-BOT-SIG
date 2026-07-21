import os, time, threading
from flask import Flask, request
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval

TOKEN = os.getenv("BOT_TOKEN") # لا تحط التوكن هنا - حطه في Render Environment
bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

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
        return d5, final, f"H1:{p1h}% | 15m:{p15}% | 5m:{p5}%\n{decision}"

    return "NO_TRADE", 0, f"H1:{p1h}% {d1h} | 15m:{p15}% {d15} | 5m:{p5}% {d5}\n\n❌ لا تدخل - السوق متضارب"

@bot.message_handler(commands=['start'])
def start(msg):
    markup = InlineKeyboardMarkup(row_width=2)
    for name in MARKETS:
        markup.add(InlineKeyboardButton(name, callback_data=f"market_{name}"))
    bot.send_message(msg.chat.id, "👋 بوت احترافي Triple TF\nاختر السوق:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_"))
def choose_market(call):
    bot.answer_callback_query(call.id)
    name = call.data.replace("market_", "")
    user_data[call.from_user.id] = MARKETS[name], name
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔍 فحص شامل H1+15m+5m", callback_data="time_ALL"))
    markup.add(InlineKeyboardButton("5m فقط", callback_data="time_5"), InlineKeyboardButton("15m فقط", callback_data="time_15"))
    bot.send_message(call.message.chat.id, f"اخترت {name}\nاختر نوع الفحص:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("time_"))
def choose_time(call):
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
        direction, percent, details = get_confluence_signal(symbol)
        if direction == "NO_TRADE":
            bot.edit_message_text(f"📊 {name}\n{details}", call.message.chat.id, loading.message_id)
            return
        emoji = "🟢 BUY صعود" if direction == "BUY" else "🔴 SELL هبوط"
        bot.edit_message_text(f"📊 {name}\n{emoji}\n💪 ثقة: {percent}%\n\n{details}", call.message.chat.id, loading.message_id)
    else:
        tf_map = {"5": Interval.INTERVAL_5_MINUTES, "15": Interval.INTERVAL_15_MINUTES}
        d, p = get_tf_signal(symbol, tf_map[mode])
        bot.edit_message_text(f"📊 {name} {mode}m\n{'🟢 BUY' if d=='BUY' else '🔴 SELL'}\n💪 {p}%\n\n{'✅ ادخل' if p>=80 else '❌ لا تدخل'}", call.message.chat.id, loading.message_id)

@app.route('/', methods=["GET"])
def home(): return "Bot is Live!"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_json(force=True))])
    return "ok"

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
