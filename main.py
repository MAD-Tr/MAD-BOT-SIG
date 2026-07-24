import os
import time
import threading
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval

TOKEN = os.environ.get("TOKEN") or "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
PASSWORD = os.environ.get("PASSWORD") or "7154"
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
}

user_data = {}
last_request = {}
authorized = set()
user_locks = {}

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
    if d5 == d15 == d1h and d5 not in ["ERROR","NEUTRAL"]:
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
        return d5, final, f"H1:{p1h}% | 15m:{p15}% | 5m:{p5}%\n{decision}", (d5,p5,d15,p15,d1h,p1h)
    return "NO_TRADE", 0, f"H1:{p1h}% {d1h} | 15m:{p15}% {d15} | 5m:{p5}% {d5}\n\n❌ لا تدخل - السوق متضارب", (d5,p5,d15,p15,d1h,p1h)

def main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔥 البحث عن الفرصة الذهبية (22 سوق)", callback_data="golden"))
    markup.add(InlineKeyboardButton("📊 فحص سوق واحد", callback_data="single"))
    bot.send_message(chat_id, "👋 بوت احترافي Triple TF\nاختر:", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id not in authorized:
        bot.send_message(msg.chat.id, "🔒 ارسل كلمة السر:")
        return
    main_menu(msg.chat.id)

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def check_pass(m):
    if m.text.strip() == PASSWORD:
        authorized.add(m.from_user.id)
        bot.send_message(m.chat.id, "✅ تم فتح البوت")
        main_menu(m.chat.id)
    else:
        bot.send_message(m.chat.id, "❌ كلمة سر غلط")

@bot.callback_query_handler(func=lambda c: c.data=="single")
def single(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup(row_width=2)
    for name in MARKETS:
        markup.add(InlineKeyboardButton(name, callback_data=f"market_{name}"))
    bot.send_message(call.message.chat.id, "اختر السوق:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data=="golden")
def golden(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id, "⏳ افحص 22 سوق...")
    loading = bot.send_message(call.message.chat.id, f"⏳ افحص {len(MARKETS)} سوق (25 ثانية)...")
    clean = []
    reversal = []
    weak = []
    volatile = []
    locked_list = []
    now = time.time()
    uid = call.from_user.id
    if uid not in user_locks: user_locks[uid] = {}
    start_t = time.time()
    for name, sym in MARKETS.items():
        if sym in user_locks[uid]:
            expiry = user_locks[uid][sym]
            if now < expiry:
                remain = int((expiry - now) / 60) + 1
                locked_list.append(f"🔒 {name} - باقي {remain} دقيقة")
                continue
            else:
                del user_locks[uid][sym]
        try:
            d, p, details, tfs = get_confluence_signal(sym)
            d5,p5,d15,p15,d1h,p1h = tfs
            if d == "NO_TRADE":
                if (d1h!= d5 or d1h!= d15 or d15!= d5) and "ERROR" not in [d1h,d15,d5] and "NEUTRAL" not in [d1h,d15,d5]:
                    reversal.append(f"⚠️ {name} - H1:{p1h}% {d1h} | 15m:{p15}% {d15} | 5m:{p5}% {d5}")
                else:
                    volatile.append(name)
            else:
                avg = int((p5+p15+p1h)/3)
                if avg >= 86 and min(p5,p15,p1h) >= 80:
                    emoji = "🟢 BUY" if d=="BUY" else "🔴 SELL"
                    clean.append((f"{emoji} {name} - {avg}%\nH1:{p1h}% | 15m:{p15}% | 5m:{p5}%", sym, name))
                else:
                    weak.append(f"{name} {avg}%")
        except: continue
    elapsed = round(time.time() - start_t, 1)
    text = f"🔥 فحصت {len(MARKETS)} سوق ثقة 86%+ في {elapsed}ث 🔥\n\n"
    if clean:
        text += f"✅ نظيفة - ادخل وانت مرتاح ({len(clean)}):\n\n"
        for c_text, sym, name in clean:
            text += c_text + "\n\n"
    else:
        text += "✅ نظيفة - لا يوجد حاليا\n\n"
    if reversal:
        text += f"⚠️ انعكاس - لا تدخل عكس الترند ({len(reversal)}):\n" + "\n".join(reversal) + "\n\n"
    if locked_list:
        text += f"🔒 مقفلة - لا تدخل ورا بعض ({len(locked_list)}):\n" + "\n".join(locked_list) + "\n\n"
    if weak:
        text += f"💤 ضعيفة ({len(weak)}):\n" + ", ".join(weak[:10]) + "\n\n"
    if volatile:
        text += f"〰️ متذبذب ({len(volatile)}):\n" + ", ".join(volatile)
    markup = InlineKeyboardMarkup(row_width=1)
    for c_text, sym, name in clean:
        markup.add(InlineKeyboardButton(f"✅ دخلت {sym}", callback_data=f"enter_{sym}"))
    markup.add(InlineKeyboardButton("🔄 تحديث جديد", callback_data="golden"))
    bot.edit_message_text(text, call.message.chat.id, loading.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("enter_"))
def lock_market(call):
    if call.from_user.id not in authorized: return
    sym = call.data.replace("enter_", "")
    uid = call.from_user.id
    if uid not in user_locks: user_locks[uid] = {}
    user_locks[uid][sym] = time.time() + (30*60)
    bot.answer_callback_query(call.id, f"🔒 قفلت {sym} لمدة 30 دقيقة")
    bot.send_message(call.message.chat.id, f"🔒 تمام قفلت {sym} لمدة 30 دقيقة - ما راح اطلعه لك في النظيفة الين ينتهي الوقت.")

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
    if user_id in last_request and now - last_request[user_id] < 3:
        bot.answer_callback_query(call.id, "⏳ انتظر 3 ثواني")
        return
    last_request[user_id] = now
    bot.answer_callback_query(call.id)
    mode = call.data.replace("time_", "")
    symbol, name = user_data.get(user_id, (None, None))
    if not symbol: return
    loading = bot.send_message(call.message.chat.id, f"⏳ جاري فحص {name}...")
    if mode == "ALL":
        direction, percent, details, _ = get_confluence_signal(symbol)
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
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

threading.Thread(target=run_flask, daemon=True).start()
bot.remove_webhook()
time.sleep(2)
while True:
    try:
        bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)
