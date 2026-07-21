import os, sys, time, threading
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("BOT_TOKEN missing")
    sys.exit(1)

PASSWORD = "7154"
bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

allowed = set()
def is_allowed(uid): return uid in allowed
qs = {}

MARKETS = {
    "EUR/USD": "FX:EURUSD",
    "GBP/USD": "FX:GBPUSD",
    "USD/JPY": "FX:USDJPY",
    "EUR/JPY": "FX:EURJPY",
    "AUD/USD": "FX:AUDUSD",
    "USD/CHF": "FX:USDCHF",
    "EUR/GBP": "FX:EURGBP",
    "EUR/AUD": "FX:EURAUD",
    "GBP/JPY": "FX:GBPJPY",
    "AUD/JPY": "FX:AUDJPY",
    "NZD/USD": "FX:NZDUSD",
    "USD/CAD": "FX:USDCAD",
    "EUR/CAD": "FX:EURCAD",
    "GBP/AUD": "FX:GBPAUD",
    "EUR/CHF": "FX:EURCHF",
    "GBP/CHF": "FX:GBPCHF",
    "AUD/CAD": "FX:AUDCAD",
    "NZD/JPY": "FX:NZDJPY",
    "EUR/NZD": "FX:EURNZD",
    "GBP/NZD": "FX:GBPNZD"
}

def get_confluence_85(symbol):
    try:
        from tradingview_ta import TA_Handler, Interval
        tf_score = {"BUY": 0, "SELL": 0}
        details = []
        for interval in [Interval.INTERVAL_5_MINUTES, Interval.INTERVAL_15_MINUTES, Interval.INTERVAL_1_HOUR]:
            h = TA_Handler(symbol=symbol, exchange="FX", screener="forex", interval=interval)
            r = h.get_analysis().summary["RECOMMENDATION"]
            if "BUY" in r: tf_score["BUY"]+=1
            elif "SELL" in r: tf_score["SELL"]+=1
            details.append(f"{interval}:{r}")
        if tf_score["BUY"]>=2: return "BUY", 88, " | ".join(details)
        if tf_score["SELL"]>=2: return "SELL", 88, " | ".join(details)
        return "NO_TRADE", 0, " | ".join(details)
    except Exception as e:
        return "NO_TRADE", 0, str(e)

def quotex_menu(uid):
    s = qs.get(uid, {"amount": 20, "trades": 6})
    mk = InlineKeyboardMarkup(row_width=2)
    mk.add(InlineKeyboardButton(f"💰 المبلغ: {s['amount']}﷼", callback_data="qx_amount"))
    mk.add(InlineKeyboardButton(f"🔢 الصفقات: {s['trades']}", callback_data="qx_trades"))
    mk.add(InlineKeyboardButton("✅ تشغيل محترف 85%+", callback_data="qx_start"))
    mk.add(InlineKeyboardButton("🛑 ايقاف", callback_data="qx_stop"))
    mk.add(InlineKeyboardButton("⬅️ رجوع", callback_data="back_main"))
    return mk

def main_menu():
    mk = InlineKeyboardMarkup(row_width=1)
    mk.add(InlineKeyboardButton("📊 بوكت اوبشن", callback_data="mode_pocket"))
    mk.add(InlineKeyboardButton("🤖 كوتكس بوت 85%+", callback_data="mode_quotex"))
    return mk

@bot.message_handler(commands=['pass'])
def pass_check(m):
    if m.chat.type!= "private":
        try: bot.delete_message(m.chat.id, m.message_id)
        except: pass
        return bot.send_message(m.chat.id, "🔒 الرقم السري فقط في الخاص")
    try: bot.delete_message(m.chat.id, m.message_id)
    except: pass
    try:
        if m.text.split()[1] == PASSWORD:
            allowed.add(m.from_user.id)
            return bot.send_message(m.chat.id, "✅ تم الدخول - ارسل /start", reply_markup=main_menu())
        else:
            return bot.send_message(m.chat.id, "❌ رقم خطأ")
    except:
        return bot.send_message(m.chat.id, "❌ ارسل: /pass 7154")

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.chat.type!= "private":
        mk = InlineKeyboardMarkup()
        mk.add(InlineKeyboardButton("🔐 افتح الخاص للدخول", url=f"https://t.me/{bot.get_me().username}?start=start"))
        return bot.send_message(msg.chat.id, "🔒 البوت خاص\nاضغط الزر وادخل الرقم في الخاص:", reply_markup=mk)
    if not is_allowed(msg.from_user.id):
        return bot.send_message(msg.chat.id, "🔒 مرحبا\nارسل الرقم السري:\n/pass 7154\n\n⚠️ تنحذف لحالها")
    bot.send_message(msg.chat.id, "👋 بوت محترف - 85%+\nاختر:", reply_markup=main_menu())

@bot.message_handler(commands=['login'])
def login_q(m):
    if m.chat.type!= "private":
        try: bot.delete_message(m.chat.id, m.message_id)
        except: pass
        return bot.send_message(m.chat.id, "🔒 تسجيل الدخول فقط في الخاص")
    try:
        bot.delete_message(m.chat.id, m.message_id)
    except: pass
    parts = m.text.split()
    if len(parts) < 3:
        return bot.send_message(m.chat.id, "❌ الصيغة:\n/login ايميلك باسوردك")
    email, password = parts[1], parts[2]
    if m.from_user.id not in qs:
        qs[m.from_user.id] = {"amount": 20, "trades": 6, "running": False}
    qs[m.from_user.id]["email"] = email
    qs[m.from_user.id]["password"] = password
    bot.send_message(m.chat.id, f"✅ تم حفظ: {email}\nالحين /start > كوتكس", reply_markup=quotex_menu(m.from_user.id))

def runner_quotex(uid, cid):
    try:
        from quotexapi.stable_api import Quotex
        s = qs[uid]
        qx = Quotex(s["email"], s["password"])
        ok, reason = qx.connect()
        if not ok:
            return bot.send_message(cid, f"❌ فشل الدخول: {reason}")
        bal = qx.get_balance()
        bot.send_message(cid, f"✅ دخل | رصيد: {bal}$\n🎯 {s['trades']} صفقات | {s['amount']}﷼")
        done = 0
        while qs.get(uid, {}).get("running") and done < s["trades"]:
            for name, sym in MARKETS.items():
                if not qs.get(uid, {}).get("running") or done >= s["trades"]:
                    break
                d, per, detail = get_confluence_85(sym)
                if d!= "NO_TRADE":
                    usd = round(s["amount"] / 3.75, 2)
                    status, _ = qx.buy(usd, sym, d.lower(), 15)
                    if status:
                        done += 1
                        bot.send_message(cid, f"🔥 صفقة #{done}\n{name}\n{d} {per}%\n{detail}")
                        time.sleep(75)
            time.sleep(20)
        if uid in qs: qs[uid]["running"] = False
        bot.send_message(cid, f"🏁 انتهى {done} صفقات")
    except Exception as e:
        bot.send_message(cid, f"❌ خطأ: {e}")

@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def back_main_h(call):
    bot.edit_message_text("👋 بوت محترف - 85%+\nاختر:", call.message.chat.id, call.message.message_id, reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "mode_pocket")
def mode_pocket(call):
    mk = InlineKeyboardMarkup(row_width=2)
    for n in MARKETS: mk.add(InlineKeyboardButton(n, callback_data=f"market_{n}"))
    bot.send_message(call.message.chat.id, "اختر السوق:", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data == "mode_quotex")
def mode_quotex(call):
    if call.from_user.id not in qs:
        qs[call.from_user.id] = {"amount": 20, "trades": 6, "running": False, "email": "", "password": ""}
    if not qs[call.from_user.id].get("email"):
        return bot.send_message(call.message.chat.id, "❌ اول سجل:\n/login ايميلك باسوردك")
    bot.send_message(call.message.chat.id, "🤖 اعدادات كوتكس:", reply_markup=quotex_menu(call.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_"))
def market_h(call):
    n = call.data.split("_", 1)[1]
    sym = MARKETS.get(n)
    d, per, detail = get_confluence_85(sym)
    bot.send_message(call.message.chat.id, f"📊 {n}\n{d} {per}%\n{detail}")

@bot.callback_query_handler(func=lambda c: c.data == "qx_amount")
def qx_amount(call):
    mk = InlineKeyboardMarkup(row_width=3)
    mk.add(InlineKeyboardButton("10﷼", callback_data="qxa_10"), InlineKeyboardButton("20﷼", callback_data="qxa_20"), InlineKeyboardButton("50﷼", callback_data="qxa_50"))
    bot.send_message(call.message.chat.id, "اختر المبلغ:", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("qxa_"))
def qxa_set(call):
    amt = int(call.data.split("_")[1])
    qs[call.from_user.id]["amount"] = amt
    bot.send_message(call.message.chat.id, f"✅ المبلغ {amt}﷼", reply_markup=quotex_menu(call.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data == "qx_trades")
def qx_trades(call):
    mk = InlineKeyboardMarkup(row_width=3)
    mk.add(InlineKeyboardButton("3", callback_data="qxt_3"), InlineKeyboardButton("6", callback_data="qxt_6"), InlineKeyboardButton("8", callback_data="qxt_8"))
    bot.send_message(call.message.chat.id, "اختر عدد الصفقات:", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("qxt_"))
def qxt_set(call):
    t = int(call.data.split("_")[1])
    qs[call.from_user.id]["trades"] = t
    bot.send_message(call.message.chat.id, f"✅ الصفقات {t}", reply_markup=quotex_menu(call.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data == "qx_start")
def qx_start(call):
    if not qs.get(call.from_user.id, {}).get("email"):
        return bot.send_message(call.message.chat.id, "❌ سجل /login اول")
    qs[call.from_user.id]["running"] = True
    threading.Thread(target=runner_quotex, args=(call.from_user.id, call.message.chat.id), daemon=True).start()
    bot.send_message(call.message.chat.id, "🚀 بدأ التداول التلقائي...")

@bot.callback_query_handler(func=lambda c: c.data == "qx_stop")
def qx_stop(call):
    if call.from_user.id in qs: qs[call.from_user.id]["running"] = False
    bot.send_message(call.message.chat.id, "🛑 تم الايقاف")

@app.route("/", methods=["GET"])
def home(): return "Bot Live"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_json(force=True))])
    return "ok"

if __name__ == "__main__":
    from flask import request
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
