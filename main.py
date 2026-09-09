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

# --- تم التعديل فقط هنا: إضافة إعادة محاولة وتأخير لتجاوز حظر TradingView ---
def get_tf_signal(symbol, interval, retries=3):
    for attempt in range(retries):
        try:
            h = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=interval)
            s = h.get_analysis().summary
            buys, sells = s['BUY'], s['SELL']
            if buys+sells == 0:
                return "NEUTRAL", 50
            direction = "BUY" if buys > sells else "SELL"
            percent = int((max(buys, sells) / (buys + sells)) * 100)
            return direction, percent
        except Exception as e:
            # محاولة اخيرة فاشلة -> ارجع ERROR
            if attempt < retries - 1:
                time.sleep(1.5)  # انتظار قبل إعادة المحاولة لتجاوز الـ rate limit
                continue
            else:
                print(f"TF Error {symbol} {interval}: {e}")
                return "ERROR", 0

def get_confluence_signal(symbol):
    d5, p5 = get_tf_signal(symbol, Interval.INTERVAL_5_MINUTES)
    time.sleep(0.6)
    d15, p15 = get_tf_signal(symbol, Interval.INTERVAL_15_MINUTES)
    time.sleep(0.6)
    d1h, p1h = get_tf_signal(symbol, Interval.INTERVAL_1_HOUR)

    # --- تم التعديل فقط هنا: لو فريم واحد ERROR لا تعتبر السوق كله متضارب، اعد المحاولة ---
    # اذا كلها ERROR فعلاً
    if d5 == "ERROR" and d15 == "ERROR" and d1h == "ERROR":
        return "NO_TRADE", 0, f"H1:{p1h}% ERROR | 15m:{p15}% ERROR | 5m:{p5}% ERROR\n\n❌ لا تدخل - فشل الاتصال بـ TradingView، حاول بعد 10 ثواني"

    # اذا فريم واحد فقط ERROR تجاهله واحسب على الباقي
    signals = []
    if d5 != "ERROR": signals.append((d5, p5))
    if d15 != "ERROR": signals.append((d15, p15))
    if d1h != "ERROR": signals.append((d1h, p1h))

    # لو فشل فريم واحد، نكمل بالموجود
    if len(signals) < 3:
        # اذا باقي فريمين متفقين
        if len(signals) >= 2 and signals[0][0] == signals[1][0]:
            d5_eff = signals[0][0]
            avg = int(sum(p for _, p in signals) / len(signals))
            final = min(94, avg+2)
            if final >= 75:
                decision = "✅ دخول جيد - ادخل 1% بحذر (فريم واحد غير متاح)"
            else:
                decision = "⚠️ دخول ضعيف - يفضل عدم الدخول"
            return d5_eff, final, f"H1:{p1h}% {d1h} | 15m:{p15}% {d15} | 5m:{p5}% {d5}\n{decision}"
        else:
            return "NO_TRADE", 0, f"H1:{p1h}% {d1h} | 15m:{p15}% {d15} | 5m:{p5}% {d5}\n\n❌ لا تدخل - السوق متضارب"

    # المنطق الأصلي - 3 فريمات متوفرة
    if d5 == d15 == d1h and d5 != "ERROR":
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
    goldens = []
    start_t = time.time()
    for name, sym in MARKETS.items():
        try:
            d, p, details = get_confluence_signal(sym)
            time.sleep(0.8) # <-- إضافة بسيطة لتجنب الحظر عند فحص الكل
            if d!= "NO_TRADE" and p >= 80:
                emoji = "🟢 BUY" if d=="BUY" else "🔴 SELL"
                goldens.append(f"{emoji} {name} - {p}%\n{details}\n")
        except: continue
    elapsed = round(time.time() - start_t, 1)
    if not goldens:
        bot.edit_message_text(f"❌ فحصت {len(MARKETS)} سوق في {elapsed}ث - لا يوجد ذهبي نظيف\nجرب بعد 5 دقايق", call.message.chat.id, loading.message_id)
    else:
        text = f"🔥🔥 {len(goldens)} فرص من {len(MARKETS)} سوق في {elapsed}ث 🔥🔥\n\n" + "\n".join(goldens)
        bot.edit_message_text(text, call.message.chat.id, loading.message_id)

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
        direction, percent, details = get_confluence_signal(symbol)
        if direction == "NO_TRADE":
            bot.edit_message_text(f"📊 {name}\n{details}", call.message.chat.id, loading.message_id)
            return
        emoji = "🟢 BUY صعود" if direction == "BUY" else "🔴 SELL هبوط"
        bot.edit_message_text(f"📊 {name}\n{emoji}\n💪 ثقة: {percent}%\n\n{details}", call.message.chat.id, loading.message_id)
    else:
        tf_map = {"5": Interval.INTERVAL_5_MINUTES, "15": Interval.INTERVAL_15_MINUTES}
        d, p = get_tf_signal(symbol, tf_map[mode])
        # اذا ERROR اعط رسالة اوضح
        if d == "ERROR":
            bot.edit_message_text(f"📊 {name} {mode}m\n❌ فشل الاتصال، حاول مرة ثانية بعد 5 ثواني", call.message.chat.id, loading.message_id)
        else:
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
