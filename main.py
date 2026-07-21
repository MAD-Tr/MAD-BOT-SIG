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
def is_allowed(uid): return uid in allowed

@bot.message_handler(commands=['pass'])
def pass_check(m):
    try: bot.delete_message(m.chat.id, m.message_id)
    except: pass
    try:
        if m.text.split()[1] == PASSWORD:
            allowed.add(m.from_user.id)
            msg = bot.send_message(m.chat.id, "✅ تم - ارسل /start")
            time.sleep(2)
            try: bot.delete_message(m.chat.id, msg.message_id)
            except: pass
    except: pass

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
qs = {}

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

def get_confluence_85(symbol):
    try:
        h5 = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=Interval.INTERVAL_5_MINUTES).get_analysis()
        h15 = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=Interval.INTERVAL_15_MINUTES).get_analysis()
        h1h = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=Interval.INTERVAL_1_HOUR).get_analysis()
        d5, p5 = get_tf_signal(symbol, Interval.INTERVAL_5_MINUTES)
        d15, p15 = get_tf_signal(symbol, Interval.INTERVAL_15_MINUTES)
        d1h, p1h = get_tf_signal(symbol, Interval.INTERVAL_1_HOUR)
        if not (d5 == d15 == d1h and d5 in ["BUY","SELL"]):
            return "NO_TRADE", 0, ""
        avg = int((p5+p15+p1h)/3)
        if avg < 85:
            return "NO_TRADE", 0, ""
        rsi5 = h5.indicators.get("RSI", 50)
        rsi15 = h15.indicators.get("RSI", 50)
        if d5=="BUY" and (rsi5>75 or rsi15>75): return "NO_TRADE",0,f"RSI متشبع {int(rsi5)}"
        if d5=="SELL" and (rsi5<25 or rsi15<25): return "NO_TRADE",0,f"RSI متشبع {int(rsi5)}"
        ema20_1h = h1h.indicators.get("EMA20",0)
        ema50_1h = h1h.indicators.get("EMA50",0)
        if d5=="BUY" and ema20_1h < ema50_1h: return "NO_TRADE",0,"عكس الترند"
        if d5=="SELL" and ema20_1h > ema50_1h: return "NO_TRADE",0,"عكس الترند"
        macd_15 = h15.indicators.get("MACD.macd",0)
        macd_sig_15 = h15.indicators.get("MACD.signal",0)
        if d5=="BUY" and macd_15 < macd_sig_15: return "NO_TRADE",0,"MACD سلبي"
        if d5=="SELL" and macd_15 > macd_sig_15: return "NO_TRADE",0,"MACD ايجابي"
        return d5, min(94, avg+5), f"5m:{p5}% 15m:{p15}% 1h:{p1h}% | RSI:{int(rsi5)} EMA:OK MACD:OK"
    except:
        return "NO_TRADE",0,""

def quotex_menu(uid):
    s = qs.get(uid, {"amount": 20, "trades": 6, "running": False})
    mk = InlineKeyboardMarkup(row_width=3)
    mk.add(InlineKeyboardButton(f"💰 المبلغ: {s['amount']}﷼", callback_data="none_q"))
    mk.add(InlineKeyboardButton("10﷼", callback_data="qa_10"),InlineKeyboardButton("20﷼", callback_data="qa_20"),InlineKeyboardButton("50﷼", callback_data="qa_50"))
    mk.add(InlineKeyboardButton("100﷼", callback_data="qa_100"),InlineKeyboardButton("200﷼", callback_data="qa_200"))
    mk.add(InlineKeyboardButton(f"🔢 عدد الصفقات: {s['trades']}", callback_data="none_q2"))
    mk.add(InlineKeyboardButton("3", callback_data="qt_3"),InlineKeyboardButton("4", callback_data="qt_4"),InlineKeyboardButton("6", callback_data="qt_6"),InlineKeyboardButton("8", callback_data="qt_8"))
    mk.add(InlineKeyboardButton("🔐 تسجيل دخول كوتكس", callback_data="qx_login"))
    mk.add(InlineKeyboardButton("🛑 ايقاف" if s['running'] else "✅ تشغيل محترف 85%+ (15m)", callback_data="qx_stop" if s['running'] else "qx_start"))
    mk.add(InlineKeyboardButton("⬅️ رجوع", callback_data="back_main"))
    return mk

def main_menu():
    mk = InlineKeyboardMarkup(row_width=1)
    mk.add(InlineKeyboardButton("📈 بوكت اوبشن - اشارات Triple TF", callback_data="mode_pocket"))
    mk.add(InlineKeyboardButton("🤖 كوتكس بوت محترف - 85%+", callback_data="mode_quotex"))
    return mk

@bot.message_handler(commands=['start'])
def start(msg):
    if not is_allowed(msg.from_user.id):
        bot.send_message(msg.chat.id, "🔒 خاص\nارسل /pass ثم الرقم السري")
        return
    bot.send_message(msg.chat.id, "👋 بوت محترف - Triple TF + RSI + EMA + MACD\nاختر المنصة:", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data=="back_main")
def back_main_h(call):
    bot.edit_message_text("👋 بوت محترف - Triple TF + RSI + EMA + MACD\nاختر المنصة:", call.message.chat.id, call.message.message_id, reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data=="mode_pocket")
def mode_pocket(call):
    markup = InlineKeyboardMarkup(row_width=2)
    for name in MARKETS:
        markup.add(InlineKeyboardButton(name, callback_data=f"market_{name}"))
    bot.send_message(call.message.chat.id, "📈 بوكت اوبشن - اختر السوق:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data=="mode_quotex")
def mode_quotex(call):
    if call.from_user.id not in qs:
        qs[call.from_user.id] = {"amount": 20, "trades": 6, "running": False, "email": None}
    bot.edit_message_text("🤖 كوتكس محترف\n85%+ | RSI فلتر | EMA ترند | MACD تأكيد\nمدة 15m", call.message.chat.id, call.message.message_id, reply_markup=quotex_menu(call.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data.startswith("qa_"))
def set_amount_q(call):
    qs[call.from_user.id]["amount"] = int(call.data.replace("qa_",""))
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=quotex_menu(call.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data.startswith("qt_"))
def set_trades_q(call):
    qs[call.from_user.id]["trades"] = int(call.data.replace("qt_",""))
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=quotex_menu(call.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data=="qx_login")
def qx_login_btn(call):
    bot.send_message(call.message.chat.id, "ارسل:\n/login ايميلك باسوردك")

@bot.message_handler(commands=['login'])
def login_q(m):
    try: bot.delete_message(m.chat.id, m.message_id)
    except: pass
    parts = m.text.split()
    if len(parts) < 3: return
    if m.from_user.id not in qs:
        qs[m.from_user.id] = {"amount": 20, "trades": 6, "running": False}
    qs[m.from_user.id]["email"] = parts[1]
    qs[m.from_user.id]["password"] = parts[2]
    bot.send_message(m.chat.id, f"✅ تم حفظ كوتكس: {parts[1]}")

def runner_quotex(uid, cid):
    try:
        # ===== هنا التعديل اللي يصلح الخطأ =====
        try:
            from quotexapi.stable_api import Quotex
        except:
            import subprocess, sys
            bot.send_message(cid, "⏳ أول مرة - جاري تثبيت مكتبة كوتكس 30 ثانية...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "git+https://github.com/cleitonleonel/quotexapi.git", "--quiet"])
            from quotexapi.stable_api import Quotex

        s = qs[uid]
        qx = Quotex(s["email"], s["password"])
        ok, reason = qx.connect()
        if not ok:
            return bot.send_message(cid, f"❌ فشل: {reason}")
        start_bal = qx.get_balance()
        bot.send_message(cid, f"✅ محترف دخل | رصيد: {start_bal}$\n🎯 {s['trades']} صفقات | {s['amount']}﷼ | فلتر RSI+EMA+MACD | 15m")
        done = 0
        while qs[uid]["running"] and done < s["trades"]:
            for name,sym in MARKETS.items():
                if not qs[uid]["running"] or done >= s["trades"]: break
                d, per, detail = get_confluence_85(sym)
                if d!= "NO_TRADE":
                    usd = round(s["amount"] / 3.75, 2)
                    status, _id = qx.buy(usd, sym, d.lower(), 15)
                    if status:
                        done += 1
                        bot.send_message(cid, f"🔥 صفقة محترفة #{done}/{s['trades']}\n{name}\n{d} {per}%\n{detail}\n💰 {s['amount']}﷼ - 15m")
                        time.sleep(75)
            time.sleep(20)
        qs[uid]["running"] = False
        try:
            end_bal = qx.get_balance()
            profit = round(end_bal - start_bal, 2)
            bot.send_message(cid, f"🏁 انتهى البوت المحترف\n📊 نفذ: {done}/{s['trades']}\n💰 ربح: {profit}$\nرصيد: {end_bal}$")
        except:
            bot.send_message(cid, f"🏁 انتهى {done} صفقات")
    except Exception as e:
        bot.send_message(cid, f"❌ خطأ: {e}")

@bot.callback_query_handler(func=lambda c: c.data=="qx_start")
def qx_start(call):
    if qs[call.from_user.id].get("email") is None:
        return bot.answer_callback_query(call.id, "سجل دخول اول")
    qs[call.from_user.id]["running"] = True
    threading.Thread(target=runner_quotex, args=(call.from_user.id, call.message.chat.id), daemon=True).start()
    bot.answer_callback_query(call.id, "بدأ المحترف")

@bot.callback_query_handler(func=lambda c: c.data=="qx_stop")
def qx_stop(call):
    qs[call.from_user.id]["running"] = False
    bot.answer_callback_query(call.id, "وقف")

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

app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Live - Pro 85%+"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask, daemon=True).start()
bot.remove_webhook()
time.sleep(2)
while True:
    try:
        bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"Polling error {e}, retry in 5s")
        time.sleep(5)
