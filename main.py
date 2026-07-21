import os, time, threading, logging
logging.basicConfig(level=logging.INFO)

from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval

TOKEN = "8828337019:AAHu5HxEgw5qFTeOd7DTWA1ELJXDH00yK1E"
bot = telebot.TeleBot(TOKEN, threaded=False)

PASSWORD = "7154"
allowed = set()

def is_allowed(uid):
    return uid in allowed

# ========= باسورد مخفي 100% =========
@bot.message_handler(commands=['pass'])
def pass_check(m):
    # يمسح رسالتك اللي فيها الرقم فورا
    try:
        bot.delete_message(m.chat.id, m.message_id)
    except:
        pass

    try:
        parts = m.text.split()
        if len(parts) < 2:
            msg = bot.send_message(m.chat.id, "🔒 ارسل /pass ثم الرقم السري")
            time.sleep(3)
            try: bot.delete_message(m.chat.id, msg.message_id)
            except: pass
            return

        if parts[1] == PASSWORD:
            allowed.add(m.from_user.id)
            msg = bot.send_message(m.chat.id, "✅ تم الدخول - الحين ارسل /start")
            time.sleep(3)
            try: bot.delete_message(m.chat.id, msg.message_id)
            except: pass
        else:
            msg = bot.send_message(m.chat.id, "❌ الرقم غلط")
            time.sleep(3)
            try: bot.delete_message(m.chat.id, msg.message_id)
            except: pass
    except:
        pass

# ========= الاسواق مع الاعلام =========
MARKETS = {
    "🇪🇺/🇺🇸 EUR/USD": "EURUSD",
    "🇬🇧/🇺🇸 GBP/USD": "GBPUSD",
    "🇺🇸/🇯🇵 USD/JPY": "USDJPY",
    "🇦🇺/🇺🇸 AUD/USD": "AUDUSD",
    "🇺🇸/🇨🇦 USD/CAD": "USDCAD",
    "🇺🇸/🇨🇭 USD/CHF": "USDCHF",
    "🇳🇿/🇺🇸 NZD/USD": "NZDUSD",
    "🇪🇺/🇬🇧 EUR/GBP": "EURGBP",
    "🇪🇺/🇯🇵 EUR/JPY": "EURJPY",
    "🇪🇺/🇦🇺 EUR/AUD": "EURAUD",
    "🇬🇧/🇯🇵 GBP/JPY": "GBPJPY",
    "🇦🇺/🇯🇵 AUD/JPY": "AUDJPY",
    "🇪🇺/🇨🇦 EUR/CAD": "EURCAD",
    "🇬🇧/🇨🇦 GBP/CAD": "GBPCAD",
    "🇪🇺/🇨🇭 EUR/CHF": "EURCHF",
    "🇬🇧/🇨🇭 GBP/CHF": "GBPCHF",
    "🇦🇺/🇨🇦 AUD/CAD": "AUDCAD",
    "🇨🇭/🇯🇵 CHF/JPY": "CHFJPY",
    "🇪🇺/🇳🇿 EUR/NZD": "EURNZD",
    "🇬🇧/🇦🇺 GBP/AUD": "GBPAUD",
    "🇺🇸/🇸🇬 USD/SGD": "USDSGD",
    "🇪🇺/🇸🇬 EUR/SGD": "EURSGD"
}

qs = {}

def get_sig(sym, interval):
    try:
        h = TA_Handler(symbol=sym, screener="forex", exchange="FX", interval=interval)
        s = h.get_analysis().summary
        b,se = s['BUY'], s['SELL']
        if b+se==0: return "NEUTRAL",50
        return ("BUY" if b>se else "SELL"), int((max(b,se)/(b+se))*100)
    except: return "ERROR",0

def confluence(sym):
    d5,p5 = get_sig(sym, Interval.INTERVAL_5_MINUTES)
    d15,p15 = get_sig(sym, Interval.INTERVAL_15_MINUTES)
    d1h,p1h = get_sig(sym, Interval.INTERVAL_1_HOUR)
    if d5==d15==d1h and d5!="ERROR":
        return d5, min(94,int((p5+p15+p1h)/3)+5), ""
    return "NO_TRADE",0,""

@bot.message_handler(commands=['start'])
def start(msg):
    if not is_allowed(msg.from_user.id):
        # هنا كان يطلع الرقم - الحين ما يطلع شي
        bot.send_message(msg.chat.id, "🔒 خاص\nارسل /pass ثم الرقم السري")
        return
    mk=InlineKeyboardMarkup()
    mk.add(InlineKeyboardButton("كوتكس تلقائي 🤖", callback_data="qa"))
    bot.send_message(msg.chat.id, "اختار:", reply_markup=mk)

def q_menu(uid):
    s=qs.get(uid,{"amount":25,"trades":4,"running":False})
    mk=InlineKeyboardMarkup(row_width=3)
    mk.add(InlineKeyboardButton(f"💰 {s['amount']} ر.س", callback_data="none"))
    mk.add(InlineKeyboardButton("10", callback_data="qa_10"),InlineKeyboardButton("25", callback_data="qa_25"),InlineKeyboardButton("50", callback_data="qa_50"))
    mk.add(InlineKeyboardButton(f"🔢 عدد الصفقات {s['trades']}", callback_data="none"))
    mk.add(InlineKeyboardButton("2", callback_data="qt_2"),InlineKeyboardButton("4", callback_data="qt_4"),InlineKeyboardButton("6", callback_data="qt_6"))
    mk.add(InlineKeyboardButton("🔐 دخول كوتكس", callback_data="qx_login"))
    mk.add(InlineKeyboardButton("🛑 إيقاف" if s['running'] else "✅ تشغيل تلقائي", callback_data="qx_stop" if s['running'] else "qx_start"))
    return mk

@bot.callback_query_handler(func=lambda c: c.data=="qa")
def qa_menu(call):
    if not is_allowed(call.from_user.id): return
    if call.from_user.id not in qs: qs[call.from_user.id]={"amount":25,"trades":4,"running":False,"email":None}
    try: bot.edit_message_text("🤖 كوتكس تلقائي", call.message.chat.id, call.message.message_id, reply_markup=q_menu(call.from_user.id))
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("qa_"))
def set_a(call):
    qs[call.from_user.id]["amount"]=int(call.data.replace("qa_",""))
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=q_menu(call.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data.startswith("qt_"))
def set_t(call):
    qs[call.from_user.id]["trades"]=int(call.data.replace("qt_",""))
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=q_menu(call.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data=="qx_login")
def ql(call): bot.send_message(call.message.chat.id, "ارسل:\n/login ايميلك باسوردك")

@bot.message_handler(commands=['login'])
def login(m):
    try: bot.delete_message(m.chat.id, m.message_id)
    except: pass
    p=m.text.split()
    if len(p)<3: return
    if m.from_user.id not in qs: qs[m.from_user.id]={"amount":25,"trades":4,"running":False}
    qs[m.from_user.id]["email"]=p[1]; qs[m.from_user.id]["password"]=p[2]
    msg = bot.send_message(m.chat.id,f"✅ تم حفظ {p[1]}")
    time.sleep(3)
    try: bot.delete_message(m.chat.id, msg.message_id)
    except: pass

def runner(uid,cid):
    try:
        from quotexapi.stable_api import Quotex
        s=qs[uid]; qx=Quotex(s["email"], s["password"])
        ok,rea=qx.connect()
        if not ok: return bot.send_message(cid,f"❌ فشل: {rea}")
        bot.send_message(cid,f"✅ دخل | رصيد: {qx.get_balance()} | {s['amount']} ر.س")
        done=0
        while qs[uid]["running"] and done<s["trades"]:
            for name,sym in MARKETS.items():
                if not qs[uid]["running"] or done>=s["trades"]: break
                d,per,_=confluence(sym)
                if d!="NO_TRADE" and per>=85:
                    usd=round(s["amount"]/3.75,2)
                    st,_id=qx.buy(usd,sym,d.lower(),1)
                    if st:
                        done+=1; bot.send_message(cid,f"✅ #{done} {name} {d} {per}%"); time.sleep(70)
            time.sleep(10)
        qs[uid]["running"]=False; bot.send_message(cid,"🏁 خلصت")
    except Exception as e:
        logging.exception("runner"); bot.send_message(cid,f"❌ {e}")

@bot.callback_query_handler(func=lambda c: c.data=="qx_start")
def qs_start(call):
    if qs[call.from_user.id].get("email") is None: return bot.send_message(call.message.chat.id,"لازم /login اول")
    qs[call.from_user.id]["running"]=True
    threading.Thread(target=runner, args=(call.from_user.id, call.message.chat.id), daemon=True).start()
    bot.answer_callback_query(call.id, "بدأ ✅")

@bot.callback_query_handler(func=lambda c: c.data=="qx_stop")
def qs_stop(call):
    qs[call.from_user.id]["running"]=False
    bot.answer_callback_query(call.id, "وقف 🛑")

app=Flask(__name__)
@app.route('/')
def home(): return "Live OK"

def run_bot():
    bot.remove_webhook()
    time.sleep(3)
    while True:
        try:
            logging.info("polling start")
            bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
        except Exception as e:
            if "409" in str(e) or "Conflict" in str(e): time.sleep(20)
            else: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0", port=port)
