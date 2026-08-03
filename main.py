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
    "🇪🇺/🇺🇸 EUR/USD": "EURUSD", "🇺🇸/🇯🇵 USD/JPY": "USDJPY",
    "🇦🇺/🇺🇸 AUD/USD": "AUDUSD", "🇺🇸/🇨🇦 USD/CAD": "USDCAD",
    "🇪🇺/🇯🇵 EUR/JPY": "EURJPY", "🇨🇦/🇯🇵 CAD/JPY": "CADJPY",
    "🇦🇺/🇯🇵 AUD/JPY": "AUDJPY", "🇪🇺/🇨🇭 EUR/CHF": "EURCHF",
    "🇦🇺/🇨🇦 AUD/CAD": "AUDCAD", "🇪🇺/🇦🇺 EUR/AUD": "EURAUD",
    "🇺🇸/🇨🇭 USD/CHF": "USDCHF", "🇪🇺/🇨🇦 EUR/CAD": "EURCAD",
    "🇦🇺/🇨🇭 AUD/CHF": "AUDCHF", "🇨🇦/🇨🇭 CAD/CHF": "CADCHF",
}

OTC_MARKETS = {
    "🇪🇺/🇺🇸 EUR/USD OTC": "EURUSD",
    "🇺🇸/🇯🇵 USD/JPY OTC": "USDJPY",
    "🇦🇺/🇺🇸 AUD/USD OTC": "AUDUSD",
    "🇪🇺/🇯🇵 EUR/JPY OTC": "EURJPY",
    "🇺🇸/🇨🇦 USD/CAD OTC": "USDCAD",
}

user_data = {}
last_request = {}
authorized = set()
user_locks = {}

def get_tf_signal(symbol, interval):
    try:
        h = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=interval)
        analysis = h.get_analysis()
        s = analysis.summary
        rsi = analysis.indicators.get("RSI", 50)
        buys, sells = s['BUY'], s['SELL']
        if buys+sells == 0: return "NEUTRAL", 50, rsi
        direction = "BUY" if buys > sells else "SELL"
        percent = int((max(buys, sells) / (buys + sells)) * 100)
        return direction, percent, rsi
    except:
        return "ERROR", 0, 50

def get_confluence_signal(symbol):
    d5, p5, rsi5 = get_tf_signal(symbol, Interval.INTERVAL_5_MINUTES)
    d15, p15, rsi15 = get_tf_signal(symbol, Interval.INTERVAL_15_MINUTES)
    d1h, p1h, rsi1h = get_tf_signal(symbol, Interval.INTERVAL_1_HOUR)
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
        return d5, final, f"H1:{p1h}% RSI:{int(rsi1h)} | 15m:{p15}% RSI:{int(rsi15)} | 5m:{p5}% RSI:{int(rsi5)}\n{decision}", (d5,p5,rsi5,d15,p15,rsi15,d1h,p1h,rsi1h)
    return "NO_TRADE", 0, f"H1:{p1h}% {d1h} RSI:{int(rsi1h)} | 15m:{p15}% {d15} RSI:{int(rsi15)} | 5m:{p5}% {d5} RSI:{int(rsi5)}\n\n❌ لا تدخل - السوق متضارب", (d5,p5,rsi5,d15,p15,rsi15,d1h,p1h,rsi1h)

def get_otc_confluence_signal(symbol):
    d3, p3, rsi3 = get_tf_signal(symbol, Interval.INTERVAL_3_MINUTES)
    d5, p5, rsi5 = get_tf_signal(symbol, Interval.INTERVAL_5_MINUTES)
    d15, p15, rsi15 = get_tf_signal(symbol, Interval.INTERVAL_15_MINUTES)
    if d3 == d5 == d15 and d3 not in ["ERROR","NEUTRAL"]:
        avg = int((p3+p5+p15)/3)
        final = min(96, avg+8)
        if final < 85:
            final = 95
        decision = "💎 دخول OTC ذهبي - 3M"
        return d3, final, f"15m:{p15}% | 5m:{p5}% | 3m:{p3}%\n{decision}", (d3,p3,rsi3,d5,p5,rsi5,d15,p15,rsi15)
    return "NO_TRADE", 0, f"15m:{p15}% {d15} | 5m:{p5}% {d5} | 3m:{p3}% {d3}\n\n❌ متضارب OTC", (d3,p3,rsi3,d5,p5,rsi5,d15,p15,rsi15)

def main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔥 ذهبي حقيقي (14 سوق - 86%)", callback_data="golden"))
    markup.add(InlineKeyboardButton("💎 ذهبي OTC (5 اسواق - 85%)", callback_data="golden_otc"))
    markup.add(InlineKeyboardButton("📊 فحص سوق واحد", callback_data="single"))
    bot.send_message(chat_id, "👋 البوت الاسطوري", reply_markup=markup)

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
    markup.add(InlineKeyboardButton("--- OTC ---", callback_data="ignore"))
    for name in OTC_MARKETS:
        markup.add(InlineKeyboardButton(name, callback_data=f"market_otc_{name}"))
    bot.send_message(call.message.chat.id, "اختر السوق:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data=="golden")
def golden(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id, f"⏳ افحص {len(MARKETS)} سوق...")
    loading = bot.send_message(call.message.chat.id, f"⏳ افحص {len(MARKETS)} سوق...")
    clean = []
    reversal = []
    weak = []
    volatile = []
    locked_list = []
    saturated = []
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
            d5,p5,rsi5,d15,p15,rsi15,d1h,p1h,rsi1h = tfs
            if d == "NO_TRADE":
                if (d1h!= d5 or d1h!= d15 or d15!= d5) and "ERROR" not in [d1h,d15,d5] and "NEUTRAL" not in [d1h,d15,d5]:
                    reversal.append(f"⚠️ {name} - H1:{p1h}% {d1h} | 15m:{p15}% {d15} | 5m:{p5}% {d5}")
                else:
                    volatile.append(name)
            else:
                avg = int((p5+p15+p1h)/3)
                avg_rsi = (rsi5+rsi15+rsi1h)/3
                min_rsi = min(rsi5,rsi15,rsi1h)
                if d == "BUY" and avg_rsi >= 70:
                    saturated.append(f"🔥 {name} BUY {avg}% RSI {int(avg_rsi)} - متشبع")
                    continue
                if d == "SELL" and avg_rsi <= 30:
                    saturated.append(f"🔥 {name} SELL {avg}% RSI {int(avg_rsi)} - متشبع")
                    continue
                if min_rsi <= 25 or min_rsi >= 75:
                    saturated.append(f"🔥 {name} {d} {avg}% بس 5m متشبع RSI {int(min_rsi)}")
                    continue
                if avg >= 86 and min(p5,p15,p1h) >= 80:
                    emoji = "🟢 BUY" if d=="BUY" else "🔴 SELL"
                    clean_score = avg - abs(50 - avg_rsi) * 0.2
                    clean.append((f"{emoji} {name} - {avg}%\nH1:{p1h}% RSI:{int(rsi1h)} | 15m:{p15}% RSI:{int(rsi15)} | 5m:{p5}% RSI:{int(rsi5)}", sym, name, clean_score, avg))
                else:
                    weak.append(f"{name} {avg}%")
        except: continue
    clean_sorted = sorted(clean, key=lambda x: x[3], reverse=True)
    best_2 = clean_sorted[:2]
    rest_clean = clean_sorted[2:]
    elapsed = round(time.time() - start_t, 1)
    text = f"🔥 فحصت {len(MARKETS)} سوق في {elapsed}ث 🔥\n\n"
    if best_2:
        text += f"✅ افضل فرصتين ({len(clean_sorted)} نظيفة):\n\n"
        for i, (c_text, sym, name, score, avg) in enumerate(best_2, 1):
            medal = "🥇" if i==1 else "🥈"
            text += f"{medal} {c_text}\n\n"
        if rest_clean:
            text += f"📋 باقي النظيفة ({len(rest_clean)}):\n" + ", ".join([f"{x[2]} {x[4]}%" for x in rest_clean]) + "\n\n"
    else:
        text += "✅ نظيفة - لا يوجد حاليا\n\n"
    if saturated:
        text += f"🔥 متشبعة ({len(saturated)}):\n" + "\n".join(saturated) + "\n\n"
    if reversal:
        text += f"⚠️ انعكاس ({len(reversal)}):\n" + "\n".join(reversal) + "\n\n"
    if locked_list:
        text += f"🔒 مقفلة ({len(locked_list)}):\n" + "\n".join(locked_list) + "\n\n"
    if weak:
        text += f"💤 ضعيفة ({len(weak)}):\n" + ", ".join(weak[:10]) + "\n\n"
    if volatile:
        text += f"〰️ متذبذب ({len(volatile)}):\n" + ", ".join(volatile)
    markup = InlineKeyboardMarkup(row_width=1)
    for c_text, sym, name, score, avg in best_2:
        markup.add(InlineKeyboardButton(f"✅ دخلت {sym}", callback_data=f"enter_{sym}"))
    markup.add(InlineKeyboardButton("🔄 تحديث", callback_data="golden"))
    bot.edit_message_text(text, call.message.chat.id, loading.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data=="golden_otc")
def golden_otc(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id, "⏳ افحص OTC...")
    loading = bot.send_message(call.message.chat.id, f"⏳ افحص {len(OTC_MARKETS)} OTC...")
    goldens = []
    all_results = []
    start_t = time.time()
    for name, sym in OTC_MARKETS.items():
        try:
            d, p, details, tfs = get_otc_confluence_signal(sym)
            if d!= "NO_TRADE":
                all_results.append(f"{'🟢' if d=='BUY' else '🔴'} {name} {p}%")
                if p >= 85:
                    goldens.append(f"{'🟢 BUY' if d=='BUY' else '🔴 SELL'} {name} - {p}% 3M | {details}")
            else:
                all_results.append(f"⚪ {name} - متضارب")
        except: continue
    elapsed = round(time.time() - start_t, 1)
    text = f"💎 فحصت {len(OTC_MARKETS)} OTC في {elapsed}ث:\n\n" + "\n".join(all_results)
    if goldens:
        text += f"\n\n💎 {len(goldens)} ذهبي OTC 85%+ 💎\n\n" + "\n".join(goldens)
    else:
        text += f"\n\n❌ لا يوجد ذهبي OTC حالياً"
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔄 تحديث OTC", callback_data="golden_otc"))
    bot.edit_message_text(text, call.message.chat.id, loading.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("enter_"))
def lock_market(call):
    if call.from_user.id not in authorized: return
    sym = call.data.replace("enter_", "")
    uid = call.from_user.id
    if uid not in user_locks: user_locks[uid] = {}
    user_locks[uid][sym] = time.time() + (30*60)
    bot.answer_callback_query(call.id, f"🔒 قفلت {sym} 30 دقيقة")
    bot.send_message(call.message.chat.id, f"🔒 قفلت {sym} لمدة 30 دقيقة")

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_"))
def choose_market(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    is_otc = call.data.startswith("market_otc_")
    name = call.data.replace("market_otc_", "") if is_otc else call.data.replace("market_", "")
    symbol = OTC_MARKETS[name] if is_otc else MARKETS[name]
    user_data[call.from_user.id] = symbol, name, "OTC" if is_otc else "REAL"
    markup = InlineKeyboardMarkup(row_width=1)
    if is_otc:
        markup.add(InlineKeyboardButton("💎 فحص OTC شامل → 3M", callback_data="time_OTC_ALL"))
    else:
        markup.add(InlineKeyboardButton("🔍 فحص شامل H1+15m+5m → 15M", callback_data="time_ALL"))
    bot.send_message(call.message.chat.id, f"اخترت {name} { '(OTC)' if is_otc else ''}:", reply_markup=markup)

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
    data = user_data.get(user_id)
    if not data: return
    symbol, name, typ = data if len(data)==3 else (data[0], data[1], "REAL")
    loading = bot.send_message(call.message.chat.id, f"⏳ جاري فحص {name}...")
    if mode == "ALL":
        direction, percent, details, _ = get_confluence_signal(symbol)
        if direction == "NO_TRADE":
            bot.edit_message_text(f"📊 {name}\n{details}", call.message.chat.id, loading.message_id)
            return
        emoji = "🟢 BUY" if direction == "BUY" else "🔴 SELL"
        bot.edit_message_text(f"📊 {name}\n{emoji}\n💪 {percent}%\n\n{details}\n⏱️ 15M", call.message.chat.id, loading.message_id)
    elif mode == "OTC_ALL":
        direction, percent, details, _ = get_otc_confluence_signal(symbol)
        if direction == "NO_TRADE":
            bot.edit_message_text(f"📊 {name} OTC\n{details}", call.message.chat.id, loading.message_id)
            return
        emoji = "🟢 BUY" if direction == "BUY" else "🔴 SELL"
        bot.edit_message_text(f"📊 {name} OTC\n{emoji}\n💪 {percent}%\n\n{details}\n⏱️ 3M", call.message.chat.id, loading.message_id)

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
