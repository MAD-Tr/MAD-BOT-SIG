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
def is_allowed(uid): return uid in allowed

@bot.message_handler(commands=['pass'])
def pass_check(m):
    try: bot.delete_message(m.chat.id, m.message_id)
    except: pass
    try:
        if m.text.split()[1] == PASSWORD:
            allowed.add(m.from_user.id)
            msg = bot.send_message(m.chat.id, "✅ تم /start")
            time.sleep(2)
            try: bot.delete_message(m.chat.id, msg.message_id)
            except: pass
    except: pass

MARKETS = {
    "🇪🇺/🇺🇸 EUR/USD": "EURUSD", "🇬🇧/🇺🇸 GBP/USD": "GBPUSD",
    "🇺🇸/🇯🇵 USD/JPY": "USDJPY", "🇦🇺/🇺🇸 AUD/USD": "AUDUSD",
    "🇺🇸/🇨🇦 USD/CAD": "USDCAD", "🇺🇸/🇨🇭 USD/CHF": "USDCHF",
    "🇳🇿/🇺🇸 NZD/USD": "NZDUSD", "🇪🇺/🇬🇧 EUR/GBP": "EURGBP",
    "🇪🇺/🇯🇵 EUR/JPY": "EURJPY", "🇬🇧/🇯🇵 GBP/JPY": "GBPJPY",
    "🇦🇺/🇯🇵 AUD/JPY": "AUDJPY", "🇪🇺/🇦🇺 EUR/AUD": "EURAUD",
    "🇪🇺/🇨🇦 EUR/CAD": "EURCAD", "🇬🇧/🇨🇦 GBP/CAD": "GBPCAD",
    "🇪🇺/🇨🇭 EUR/CHF": "EURCHF", "🇬🇧/🇨🇭 GBP/CHF": "GBPCHF",
    "🇦🇺/🇨🇦 AUD/CAD": "AUDCAD", "🇨🇭/🇯🇵 CHF/JPY": "CHFJPY",
    "🇪🇺/🇳🇿 EUR/NZD": "EURNZD", "🇬🇧/🇦🇺 GBP/AUD": "GBPAUD",
}

qs = {}
ps = {} # pocket

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
        return d5, min(94,int((p5+p15+p1h)/3)+5)
    return "NO_TRADE",0

# ====== القوائم ======
def main_menu():
    mk=InlineKeyboardMarkup(row_width=1)
    mk.add(InlineKeyboardButton("🤖 كوتكس تلقائي", callback_data="qa"))
    mk.add(InlineKeyboardButton("📈 بوكت اوبشن تلقائي", callback_data="pa"))
    mk.add(InlineKeyboardButton("📊 اشارات فقط", callback_data="sig"))
    return mk

def q_menu(uid):
    s=qs.get(uid,{"amount":25,"trades":4,"running":False})
    mk=InlineKeyboardMarkup(row_width=3)
    mk.add(InlineKeyboardButton(f"💰 {s['amount']}", callback_data="none"))
    mk.add(InlineKeyboardButton("10", callback_data="qa_10"),InlineKeyboardButton("25", callback_data="qa_25"),InlineKeyboardButton("50", callback_data="qa_50"))
    mk.add(InlineKeyboardButton(f"🔢 {s['trades']}", callback_data="none"))
    mk.add(InlineKeyboardButton("2", callback_data="qt_2"),InlineKeyboardButton("4", callback_data="qt_4"),InlineKeyboardButton("6", callback_data="qt_6"))
    mk.add(InlineKeyboardButton("🔐 دخول كوتكس", callback_data="qx_login"))
    mk.add(InlineKeyboardButton("🛑 وقف" if s['running'] else "✅ تشغيل كوتكس", callback_data="qx_stop" if s['running'] else "qx_start"))
    mk.add(InlineKeyboardButton("⬅️ رجوع", callback_data="back_main"))
    return mk

def p_menu(uid):
    s=ps.get(uid,{"amount":25,"trades":4,"running":False})
    mk=InlineKeyboardMarkup(row_width=3)
    mk.add(InlineKeyboardButton(f"💰 {s['amount']}", callback_data="none2"))
    mk.add(InlineKeyboardButton("10", callback_data="pa_10"),InlineKeyboardButton("25", callback_data="pa_25"),InlineKeyboardButton("50", callback_data="pa_50"))
    mk.add(InlineKeyboardButton(f"🔢 {s['trades']}", callback_data="none2"))
    mk.add(InlineKeyboardButton("2", callback_data="pt_2"),InlineKeyboardButton("4", callback_data="pt_4"),InlineKeyboardButton("6", callback_data="pt_6"))
    mk.add(InlineKeyboardButton("🔐 دخول بوكت", callback_data="po_login"))
    mk.add(InlineKeyboardButton("🛑 وقف" if s['running'] else "✅ تشغيل بوكت", callback_data="po_stop" if s['running'] else "po_start"))
    mk.add(InlineKeyboardButton("⬅️ رجوع", callback_data="back_main"))
    return mk

@bot.message_handler(commands=['start'])
def start(msg):
    if not is_allowed(msg.from_user.id):
        bot.send_message(msg.chat.id, "🔒 خاص\nارسل /pass ثم الرقم السري")
        return
    bot.send_message(msg.chat.id, "اختار المنصة:", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data=="back_main")
def back_main_c(call):
    bot.edit_message_text("اختار المنصة:", call.message.chat.id, call.message.message_id, reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data=="qa")
def qa_menu(call):
    if call.from_user.id not in qs: qs[call.from_user.id]={"amount":25,"trades":4,"running":False,"email":None}
    bot.edit_message_text("🤖 كوتكس تلقائي", call.message.chat.id, call.message.message_id, reply_markup=q_menu(call.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data=="pa")
def pa_menu_c(call):
    if call.from_user.id not in ps: ps[call.from_user.id]={"amount":25,"trades":4,"running":False,"email":None}
    bot.edit_message_text("📈 بوكت اوبشن تلقائي", call.message.chat.id, call.message.message_id, reply_markup=p_menu(call.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data.startswith("qa_"))
def set_a_q(call):
    qs[call.from_user.id]["amount"]=int(call.data.replace("qa_",""))
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=q_menu(call.from_user.id))
@bot.callback_query_handler(func=lambda c: c.data.startswith("qt_"))
def set_t_q(call):
    qs[call.from_user.id]["trades"]=int(call.data.replace("qt_",""))
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=q_menu(call.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data.startswith("pa_"))
def set_a_p(call):
    ps[call.from_user.id]["amount"]=int(call.data.replace("pa_",""))
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=p_menu(call.from_user.id))
@bot.callback_query_handler(func=lambda c: c.data.startswith("pt_"))
def set_t_p(call):
    ps[call.from_user.id]["trades"]=int(call.data.replace("pt_",""))
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=p_menu(call.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data=="qx_login")
def ql(call): bot.send_message(call.message.chat.id, "ارسل:\n/login ايميلك باسوردك")
@bot.callback_query_handler(func=lambda c: c.data=="po_login")
def pl(call): bot.send_message(call.message.chat.id, "ارسل:\n/pologin ايميلك باسوردك")

@bot.message_handler(commands=['login'])
def login_q(m):
    try: bot.delete_message(m.chat.id, m.message_id)
    except: pass
    p=m.text.split()
    if len(p)<3: return
    if m.from_user.id not in qs: qs[m.from_user.id]={"amount":25,"trades":4,"running":False}
    qs[m.from_user.id]["email"]=p[1]; qs[m.from_user.id]["password"]=p[2]
    bot.send_message(m.chat.id,f"✅ كوتكس: {p[1]}")

@bot.message_handler(commands=['pologin'])
def login_p(m):
    try: bot.delete_message(m.chat.id, m.message_id)
    except: pass
    p=m.text.split()
    if len(p)<3: return
    if m.from_user.id not in ps: ps[m.from_user.id]={"amount":25,"trades":4,"running":False}
    ps[m.from_user.id]["email"]=p[1]; ps[m.from_user.id]["password"]=p[2]
    bot.send_message(m.chat.id,f"✅ بوكت: {p[1]}")

# تشغيل كوتكس
def runner_q(uid,cid):
    try:
        from quotexapi.stable_api import Quotex
        s=qs[uid]; qx=Quotex(s["email"], s["password"])
        ok,rea=qx.connect()
        if not ok: return bot.send_message(cid,f"❌ {rea}")
        bot.send_message(cid,f"✅ كوتكس دخل | {s['amount']}"); done=0
        while qs[uid]["running"] and done<s["trades"]:
            for name,sym in MARKETS.items():
                if not qs[uid]["running"] or done>=s["trades"]: break
                d,per=confluence(sym)
                if d!="NO_TRADE" and per>=85:
                    usd=round(s["amount"]/3.75,2)
                    st,_id=qx.buy(usd,sym,d.lower(),1)
                    if st:
                        done+=1; bot.send_message(cid,f"✅ #{done} {name} {d} {per}%"); time.sleep(70)
            time.sleep(10)
        qs[uid]["running"]=False; bot.send_message(cid,"🏁 خلص كوتكس")
    except Exception as e: bot.send_message(cid,f"❌ {e}")

# تشغيل بوكت
def runner_p(uid,cid):
    try:
        from pocketoptionapi import PocketOption
        s=ps[uid]; po=PocketOption(s["email"], s["password"])
        ok=po.connect()
        if not ok: return bot.send_message(cid,"❌ فشل بوكت")
        bot.send_message(cid,f"✅ بوكت دخل | {s['amount']}"); done=0
        while ps[uid]["running"] and done<s["trades"]:
            for name,sym in MARKETS.items():
                if not ps[uid]["running"] or done>=s["trades"]: break
                d,per=confluence(sym)
                if d!="NO_TRADE" and per>=85:
                    st=po.buy(sym, s["amount"], d.lower(), 1)
                    if st:
                        done+=1; bot.send_message(cid,f"✅ بوكت #{done} {name} {d} {per}%"); time.sleep(70)
            time.sleep(10)
        ps[uid]["running"]=False; bot.send_message(cid,"🏁 خلص بوكت")
    except Exception as e: bot.send_message(cid,f"❌ بوكت: {e} - تأكد من مكتبة pocketoptionapi")

@bot.callback_query_handler(func=lambda c: c.data=="qx_start")
def qs_start(call):
    if qs[call.from_user.id].get("email") is None: return bot.send_message(call.message.chat.id,"/login اول")
    qs[call.from_user.id]["running"]=True
    threading.Thread(target=runner_q, args=(call.from_user.id, call.message.chat.id), daemon=True).start()
    bot.answer_callback_query(call.id, "بدأ كوتكس")
@bot.callback_query_handler(func=lambda c: c.data=="qx_stop")
def qs_stop(call):
    qs[call.from_user.id]["running"]=False; bot.answer_callback_query(call.id, "وقف")

@bot.callback_query_handler(func=lambda c: c.data=="po_start")
def ps_start(call):
    if ps[call.from_user.id].get("email") is None: return bot.send_message(call.message.chat.id,"/pologin اول")
    ps[call.from_user.id]["running"]=True
    threading.Thread(target=runner_p, args=(call.from_user.id, call.message.chat.id), daemon=True).start()
    bot.answer_callback_query(call.id, "بدأ بوكت")
@bot.callback_query_handler(func=lambda c: c.data=="po_stop")
def ps_stop(call):
    ps[call.from_user.id]["running"]=False; bot.answer_callback_query(call.id, "وقف")

@bot.callback_query_handler(func=lambda c: c.data=="sig")
def sigs(call):
    txt="📊 اشارات لايف:\n"
    for name,sym in list(MARKETS.items())[:8]:
        d,per=confluence(sym)
        if d!="NO_TRADE": txt+=f"{name} {d} {per}%\n"
    bot.send_message(call.message.chat.id, txt if txt!="📊 اشارات لايف:\n" else "لا يوجد اشارات قوية حاليا")

app=Flask(__name__)
@app.route('/')
def home(): return "Live OK"
def run_bot():
    bot.remove_webhook(); time.sleep(3)
    while True:
        try:
            logging.info("polling start")
            bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
        except:
            time.sleep(5)
if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
