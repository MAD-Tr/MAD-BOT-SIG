import os, time, threading
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
    try:
        if m.text.split()[1] == PASSWORD:
            allowed.add(m.from_user.id)
            bot.reply_to(m, "✅ فتحت البوت /start")
        else:
            bot.reply_to(m, "❌ غلط")
    except:
        bot.reply_to(m, "❌ اكتب /pass 7154")

MARKETS = {"EUR/USD":"EURUSD","GBP/USD":"GBPUSD","USD/JPY":"USDJPY","AUD/USD":"AUDUSD","USD/CAD":"USDCAD","EUR/JPY":"EURJPY","GBP/JPY":"GBPJPY"}
user_data, quotex_settings = {}, {}

def get_tf_signal(sym, interval):
    try:
        h = TA_Handler(symbol=sym, screener="forex", exchange="FX", interval=interval)
        s = h.get_analysis().summary
        b, se = s['BUY'], s['SELL']
        if b+se==0: return "NEUTRAL", 50
        d = "BUY" if b>se else "SELL"
        return d, int((max(b,se)/(b+se))*100)
    except: return "ERROR", 0

def get_confluence(sym):
    d5,p5 = get_tf_signal(sym, Interval.INTERVAL_5_MINUTES)
    d15,p15 = get_tf_signal(sym, Interval.INTERVAL_15_MINUTES)
    d1h,p1h = get_tf_signal(sym, Interval.INTERVAL_1_HOUR)
    if d5==d15==d1h and d5!="ERROR":
        avg=int((p5+p15+p1h)/3)
        return d5, min(94,avg+5), f"H1:{p1h}% 15m:{p15}% 5m:{p5}%"
    return "NO_TRADE",0,f"H1:{p1h}% {d1h} | 15m:{p15}% {d15} | 5m:{p5}% {d5}"

@bot.message_handler(commands=['start'])
def start(msg):
    if not is_allowed(msg.from_user.id):
        bot.send_message(msg.chat.id, "🔒 خاص\nادخل الرقم السري:\n/pass [الرقم]")
        return
    mk = InlineKeyboardMarkup()
    mk.add(InlineKeyboardButton("بوكت أوبشن يدوي", callback_data="pocket"))
    mk.add(InlineKeyboardButton("كوتكس تلقائي", callback_data="quotex_auto"))
    bot.send_message(msg.chat.id, "اختار:", reply_markup=mk)

def q_menu(uid):
    s=quotex_settings.get(uid,{"amount":25,"trades":4,"running":False})
    mk=InlineKeyboardMarkup(row_width=3)
    mk.add(InlineKeyboardButton(f"💰 {s['amount']} ر.س", callback_data="none"))
    mk.add(InlineKeyboardButton("10", callback_data="qa_10"),InlineKeyboardButton("25", callback_data="qa_25"),InlineKeyboardButton("50", callback_data="qa_50"))
    mk.add(InlineKeyboardButton(f"🔢 {s['trades']}", callback_data="none"))
    mk.add(InlineKeyboardButton("2", callback_data="qt_2"),InlineKeyboardButton("4", callback_data="qt_4"),InlineKeyboardButton("6", callback_data="qt_6"))
    mk.add(InlineKeyboardButton("🔐 تسجيل كوتكس", callback_data="qx_login"))
    mk.add(InlineKeyboardButton("🛑 ايقاف" if s['running'] else "✅ تفعيل", callback_data="qx_stop" if s['running'] else "qx_start"))
    return mk

@bot.callback_query_handler(func=lambda c: c.data=="quotex_auto")
def qa(call):
    if not is_allowed(call.from_user.id): return
    if call.from_user.id not in quotex_settings: quotex_settings[call.from_user.id]={"amount":25,"trades":4,"running":False,"email":None}
    bot.edit_message_text("كوتكس تلقائي\n/login ايميلك باسوردك\nثم فعل", call.message.chat.id, call.message.message_id, reply_markup=q_menu(call.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data.startswith("qa_"))
def set_a(call):
    quotex_settings[call.from_user.id]["amount"]=int(call.data.replace("qa_",""))
    bot.edit_message_text("كوتكس تلقائي", call.message.chat.id, call.message.message_id, reply_markup=q_menu(call.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data.startswith("qt_"))
def set_t(call):
    quotex_settings[call.from_user.id]["trades"]=int(call.data.replace("qt_",""))
    bot.edit_message_text("كوتكس تلقائي", call.message.chat.id, call.message.message_id, reply_markup=q_menu(call.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data=="qx_login")
def ql(call): bot.send_message(call.message.chat.id, "ارسل:\n/login ايميلك باسوردك")

@bot.message_handler(commands=['login'])
def login(m):
    p=m.text.split()
    if len(p)<3: return bot.reply_to(m,"❌ /login ايميل باسورد")
    if m.from_user.id not in quotex_settings: quotex_settings[m.from_user.id]={"amount":25,"trades":4,"running":False}
    quotex_settings[m.from_user.id]["email"]=p[1]; quotex_settings[m.from_user.id]["password"]=p[2]
    bot.reply_to(m,f"✅ حفظ {p[1]}")

def runner(uid, cid):
    try:
        try:
            from quotexapi.stable_api import Quotex
        except:
            from quotexapi.api import Quotex
        s=quotex_settings[uid]
        qx=Quotex(s["email"], s["password"])
        ok, rea = qx.connect()
        if not ok: return bot.send_message(cid, f"❌ فشل دخول كوتكس: {rea}")
        bot.send_message(cid, f"✅ دخل كوتكس بنجاح\n💰 {s['amount']} ر.س | {s['trades']} صفقات")
        done=0
        while quotex_settings[uid]["running"] and done < s["trades"]:
            for name, sym in MARKETS.items():
                if not quotex_settings[uid]["running"] or done>=s["trades"]: break
                d, per, _ = get_confluence(sym)
                if d!="NO_TRADE" and per>=85:
                    usd=round(s["amount"]/3.75,2)
                    st, _id = qx.buy(usd, sym, d.lower(), 1)
                    if st:
                        done+=1
                        bot.send_message(cid, f"✅ صفقة #{done} {name} {d} {per}% - {usd}$")
                        time.sleep(70)
            time.sleep(10)
        quotex_settings[uid]["running"]=False
        bot.send_message(cid, f"🏁 انتهى - دخل {done} صفقات")
    except Exception as e:
        bot.send_message(cid, f"❌ خطأ: {e}")

@bot.callback_query_handler(func=lambda c: c.data=="qx_start")
def qs(call):
    if quotex_settings[call.from_user.id].get("email") is None: return bot.send_message(call.message.chat.id,"❌ سوي /login اول")
    quotex_settings[call.from_user.id]["running"]=True
    threading.Thread(target=runner, args=(call.from_user.id, call.message.chat.id), daemon=True).start()
    bot.send_message(call.message.chat.id, "⏳ جاري التشغيل...")

@bot.callback_query_handler(func=lambda c: c.data=="qx_stop")
def qstop(call):
    quotex_settings[call.from_user.id]["running"]=False
    bot.send_message(call.message.chat.id, "🛑 تم الايقاف")

@bot.callback_query_handler(func=lambda c: c.data=="pocket")
def pocket(call):
    mk=InlineKeyboardMarkup()
    for n in MARKETS: mk.add(InlineKeyboardButton(n, callback_data=f"m_{n}"))
    bot.edit_message_text("اختر السوق:", call.message.chat.id, call.message.message_id, reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("m_"))
def cm(call):
    name=call.data.replace("m_","")
    user_data[call.from_user.id]=MARKETS[name], name
    mk=InlineKeyboardMarkup()
    mk.add(InlineKeyboardButton("🔍 فحص شامل 5m 15m 1h", callback_data="t_ALL"))
    mk.add(InlineKeyboardButton("5m فقط", callback_data="t_5"), InlineKeyboardButton("15m فقط", callback_data="t_15"))
    bot.send_message(call.message.chat.id, f"اخترت {name}:", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("t_"))
def ct(call):
    sym, name = user_data.get(call.from_user.id, (None,None))
    if not sym: return
    loading=bot.send_message(call.message.chat.id, f"⏳ فحص {name}...")
    d,p,det=get_confluence(sym)
    if d=="NO_TRADE": bot.edit_message_text(f"📊 {name}\n{det}\n\n❌ لا تدخل", call.message.chat.id, loading.message_id)
    else: bot.edit_message_text(f"📊 {name}\n{'🟢 صعود' if d=='BUY' else '🔴 هبوط'} {p}%\n{det}", call.message.chat.id, loading.message_id)

app=Flask(__name__)
@app.route('/')
def home(): return "Bot Live"
threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000))), daemon=True).start()
bot.remove_webhook(); time.sleep(1)
bot.infinity_polling(skip_pending=True)
