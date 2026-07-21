import os
import time
import threading
import subprocess, sys

try:
    import quotexapi
except:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "git+https://github.com/cleitonleonel/pyquotex.git"])

from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval

TOKEN = "8828337019:AAHu5HxEgw5qFTeOd7DTWA1ELJXDH00yK1E"
bot = telebot.TeleBot(TOKEN, threaded=False)

PASSWORD = "7154"
allowed = set()
def is_allowed(user_id): return user_id in allowed

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
quotex_settings = {}

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
    if not is_allowed(msg.from_user.id):
        bot.send_message(msg.chat.id, "🔒 البوت خاص\n\nادخل الرقم السري:\n/pass [الرقم]")
        return
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("منصة بوكت أوبشن", callback_data="platform_pocket"))
    markup.add(InlineKeyboardButton("منصة كوتكس تلقائي", callback_data="quotex_auto"))
    bot.send_message(msg.chat.id, "اختار المنصة:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "back_to_platforms")
def back_to_platforms(call):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("منصة بوكت أوبشن", callback_data="platform_pocket"))
    markup.add(InlineKeyboardButton("منصة كوتكس تلقائي", callback_data="quotex_auto"))
    bot.edit_message_text("اختار المنصة:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "platform_pocket")
def platform_pocket(call):
    if not is_allowed(call.from_user.id): return
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("💎 بحث عن الفرص الذهبية 5m 15m 1h", callback_data="scan_golden"))
    for name in MARKETS:
        markup.add(InlineKeyboardButton(name, callback_data=f"market_{name}"))
    markup.add(InlineKeyboardButton("⬅️ رجوع", callback_data="back_to_platforms"))
    bot.edit_message_text("منصة بوكت أوبشن:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "scan_golden")
def scan_golden(call):
    if not is_allowed(call.from_user.id): return
    user_id = call.from_user.id
    now = time.time()
    if user_id in last_request and now - last_request[user_id] < 15:
        bot.answer_callback_query(call.id, "⏳ انتظر 15 ثانية")
        return
    last_request[user_id] = now
    bot.answer_callback_query(call.id, "🔍 جاري البحث...")
    loading = bot.send_message(call.message.chat.id, "💎 جاري فحص كل الأسواق...")
    golden = []
    for display_name, symbol in MARKETS.items():
        d5, p5 = get_tf_signal(symbol, Interval.INTERVAL_5_MINUTES)
        d15, p15 = get_tf_signal(symbol, Interval.INTERVAL_15_MINUTES)
        d1h, p1h = get_tf_signal(symbol, Interval.INTERVAL_1_HOUR)
        if d5 == d15 == d1h and d5!= "ERROR" and d5!= "NEUTRAL":
            if p5 >= 80 and p15 >= 80 and p1h >= 80:
                avg = int((p5+p15+p1h)/3)
                final = min(94, avg+5)
                emoji = "🟢 صعود" if d5 == "BUY" else "🔴 هبوط"
                golden.append(f"🔥 {display_name} {emoji} - {final}%\n H1:{p1h}% | 15m:{p15}% | 5m:{p5}%")
        time.sleep(0.5)
    text = f"💎 وجدت {len(golden)} فرص:\n\n" + "\n\n".join(golden) if golden else "🔴 لا يوجد فرص ذهبية حالياً"
    try: bot.edit_message_text(text, call.message.chat.id, loading.message_id)
    except: bot.send_message(call.message.chat.id, text)

def get_quotex_menu(user_id):
    s = quotex_settings.get(user_id, {"amount_sar": 25, "trades": 4, "running": False})
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(InlineKeyboardButton(f"💰 المبلغ: {s['amount_sar']} ر.س", callback_data="none"))
    markup.add(InlineKeyboardButton("10 ر.س", callback_data="qx_set_amount_10"), InlineKeyboardButton("25 ر.س", callback_data="qx_set_amount_25"), InlineKeyboardButton("50 ر.س", callback_data="qx_set_amount_50"))
    markup.add(InlineKeyboardButton("100 ر.س", callback_data="qx_set_amount_100"), InlineKeyboardButton("200 ر.س", callback_data="qx_set_amount_200"))
    markup.add(InlineKeyboardButton(f"🔢 الصفقات: {s['trades']}", callback_data="none"))
    markup.add(InlineKeyboardButton("2", callback_data="qx_set_trades_2"), InlineKeyboardButton("4", callback_data="qx_set_trades_4"), InlineKeyboardButton("6", callback_data="qx_set_trades_6"))
    markup.add(InlineKeyboardButton("🔐 تسجيل دخول كوتكس", callback_data="qx_login"))
    if not s.get("running"):
        markup.add(InlineKeyboardButton("✅ تفعيل", callback_data="qx_start"))
    else:
        markup.add(InlineKeyboardButton("🛑 ايقاف", callback_data="qx_stop"))
    markup.add(InlineKeyboardButton("⬅️ رجوع", callback_data="back_to_platforms"))
    return markup

@bot.callback_query_handler(func=lambda c: c.data == "quotex_auto")
def quotex_auto_menu(call):
    if not is_allowed(call.from_user.id): return
    user_id = call.from_user.id
    if user_id not in quotex_settings:
        quotex_settings[user_id] = {"amount_sar": 25, "trades": 4, "running": False}
    s = quotex_settings[user_id]
    bot.edit_message_text(f"منصة كوتكس تلقائي\n\n💰 {s['amount_sar']} ر.س (~{round(s['amount_sar']/3.75,2)}$)\n🔢 {s['trades']} صفقات", call.message.chat.id, call.message.message_id, reply_markup=get_quotex_menu(user_id))

@bot.callback_query_handler(func=lambda c: c.data.startswith("qx_set_amount_"))
def qx_set_amount(call):
    quotex_settings[call.from_user.id]["amount_sar"] = int(call.data.replace("qx_set_amount_", ""))
    quotex_auto_menu(call)

@bot.callback_query_handler(func=lambda c: c.data.startswith("qx_set_trades_"))
def qx_set_trades(call):
    quotex_settings[call.from_user.id]["trades"] = int(call.data.replace("qx_set_trades_", ""))
    quotex_auto_menu(call)

@bot.callback_query_handler(func=lambda c: c.data == "qx_login")
def qx_login(call):
    bot.send_message(call.message.chat.id, "🔐 ارسل:\n/login ايميلك باسوردك")

@bot.message_handler(commands=['login'])
def handle_login(m):
    if not is_allowed(m.from_user.id): return
    parts = m.text.split()
    if len(parts) < 3:
        bot.reply_to(m, "❌ اكتب: /login ايميلك باسوردك")
        return
    if m.from_user.id not in quotex_settings: quotex_settings[m.from_user.id] = {"amount_sar":25,"trades":4,"running":False}
    quotex_settings[m.from_user.id]["email"] = parts[1]
    quotex_settings[m.from_user.id]["password"] = parts[2]
    bot.reply_to(m, f"✅ تم حفظ {parts[1]}")

def quotex_auto_runner(user_id, chat_id):
    try:
        from quotexapi.stable_api import Quotex
        s = quotex_settings[user_id]
        qx = Quotex(s["email"], s["password"])
        check, reason = qx.connect()
        if not check:
            bot.send_message(chat_id, f"❌ فشل: {reason}")
            return
        bot.send_message(chat_id, f"✅ دخل كوتكس\n💰 {s['amount_sar']} ر.س | {s['trades']} صفقات")
        done = 0
        while quotex_settings[user_id].get("running") and done < s["trades"]:
            for display_name, symbol in MARKETS.items():
                if not quotex_settings[user_id].get("running") or done >= s["trades"]: break
                direction, percent, details = get_confluence_signal(symbol)
                if direction!= "NO_TRADE" and percent >= 85:
                    amount_usd = round(s["amount_sar"] / 3.75, 2)
                    status, buy_id = qx.buy(amount_usd, symbol, direction.lower(), 1)
                    if status:
                        done += 1
                        bot.send_message(chat_id, f"✅ صفقة #{done}\n{display_name} {direction} ثقة {percent}%\n💰 {s['amount_sar']} ر.س")
                        time.sleep(65)
            time.sleep(10)
        quotex_settings[user_id]["running"] = False
        bot.send_message(chat_id, f"🏁 خلص - دخل {done} صفقات")
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطأ: {e}")

@bot.callback_query_handler(func=lambda c: c.data == "qx_start")
def qx_start(call):
    if quotex_settings[call.from_user.id].get("email") is None:
        bot.send_message(call.message.chat.id, "❌ سوي /login اول")
        return
    quotex_settings[call.from_user.id]["running"] = True
    threading.Thread(target=quotex_auto_runner, args=(call.from_user.id, call.message.chat.id), daemon=True).start()

@bot.callback_query_handler(func=lambda c: c.data == "qx_stop")
def qx_stop(call):
    quotex_settings[call.from_user.id]["running"] = False

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_"))
def choose_market(call):
    if not is_allowed(call.from_user.id): return
    name = call.data.replace("market_", "")
    user_data[call.from_user.id] = MARKETS[name], name
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔍 فحص شامل 5m 15m 1h", callback_data="time_ALL"))
    markup.add(InlineKeyboardButton("5m فقط", callback_data="time_5"), InlineKeyboardButton("15m فقط", callback_data="time_15"))
    bot.send_message(call.message.chat.id, f"اخترت {name}:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("time_"))
def choose_time(call):
    if not is_allowed(call.from_user.id): return
    user_id = call.from_user.id
    now = time.time()
    if user_id in last_request and now - last_request[user_id] < 5:
        bot.answer_callback_query(call.id, "⏳ انتظر")
        return
    last_request[user_id] = now
    symbol, name = user_data.get(user_id, (None, None))
    if not symbol: return
    loading = bot.send_message(call.message.chat.id, f"⏳ فحص {name}...")
    if call.data == "time_ALL":
        direction, percent, details = get_confluence_signal(symbol)
        if direction == "NO_TRADE":
            bot.edit_message_text(f"📊 {name}\n{details}", call.message.chat.id, loading.message_id)
            return
        emoji = "🟢 BUY" if direction == "BUY" else "🔴 SELL"
        bot.edit_message_text(f"📊 {name}\n{emoji}\n💪 {percent}%\n\n{details}", call.message.chat.id, loading.message_id)
    else:
        tf_map = {"5": Interval.INTERVAL_5_MINUTES, "15": Interval.INTERVAL_15_MINUTES}
        mode = call.data.replace("time_", "")
        d, p = get_tf_signal(symbol, tf_map)
        bot.edit_message_text(f"📊 {name} {mode}m\n{'🟢 BUY' if d=='BUY' else '🔴 SELL'}\n💪 {p}%", call.message.chat.id, loading.message_id)

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
