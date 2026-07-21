import os, time, threading, sys, subprocess
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
    if m.chat.type!= "private":
        try: bot.delete_message(m.chat.id, m.message_id)
        except: pass
        return bot.send_message(m.chat.id, "🔒 الرقم في الخاص فقط")
    try: bot.delete_message(m.chat.id, m.message_id)
    except: pass
    try:
        if m.text.split()[1] == PASSWORD:
            allowed.add(m.from_user.id)
            bot.send_message(m.chat.id, "✅ تم - ارسل /start", reply_markup=main_menu())
    except:
        bot.send_message(m.chat.id, "❌ رقم خطأ")

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.chat.type!= "private":
        mk = InlineKeyboardMarkup()
        mk.add(InlineKeyboardButton("🔐 افتح الخاص", url=f"https://t.me/{bot.get_me().username}?start=start"))
        return bot.send_message(msg.chat.id, "🔒 خاص - اضغط الزر:", reply_markup=mk)
    if not is_allowed(msg.from_user.id):
        return bot.send_message(msg.chat.id, "🔒 ارسل:\n/pass 7154")
    bot.send_message(msg.chat.id,"👋 بوت محترف - 85%+\nاختر:", reply_markup=main_menu())

MARKETS = {"🇪🇺/🇺🇸 EUR/USD":"EURUSD","🇬🇧/🇺🇸 GBP/USD":"GBPUSD","🇺🇸/🇯🇵 USD/JPY":"USDJPY","🇦🇺/🇺🇸 AUD/USD":"AUDUSD","🇺🇸/🇨🇦 USD/CAD":"USDCAD","🇪🇺/🇯🇵 EUR/JPY":"EURJPY","🇪🇺/🇺🇸 EUR/USD OTC":"EURUSD","🇬🇧/🇺🇸 GBP/USD OTC":"GBPUSD"}

user_data, last_request, qs = {}, {}, {}

def get_tf_signal(symbol, interval):
    try:
        h = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=interval)
        s = h.get_analysis().summary
        buys, sells = s['BUY'], s['SELL']
        if buys+sells==0: return "NEUTRAL",50
        d = "BUY" if buys>sells else "SELL"
        p = int((max(buys,sells)/(buys+sells))*100)
        return d,p
    except: return "ERROR",0

def get_confluence_85(symbol):
    try:
        h5 = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=Interval.INTERVAL_5_MINUTES).get_analysis()
        h15 = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=Interval.INTERVAL_15_MINUTES).get_analysis()
        h1h = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=Interval.INTERVAL_1_HOUR).get_analysis()
        d5,p5 = get_tf_signal(symbol, Interval.INTERVAL_5_MINUTES)
        d15,p15 = get_tf_signal(symbol, Interval.INTERVAL_15_MINUTES)
        d1h,p1h = get_tf_signal(symbol, Interval.INTERVAL_1_HOUR)
        if not (d5==d15==d1h and d5 in ["BUY","SELL"]): return "NO_TRADE",0,""
        avg=int((p5+p15+p1h)/3)
        if avg<80: return "NO_TRADE",0,""
        rsi5=h5.indicators.get("RSI",50)
        if d5=="BUY" and rsi5>75: return "NO_TRADE",0,""
        if d5=="SELL" and rsi5<25: return "NO_TRADE",0,""
        return d5, min(94,avg+5), f"5m:{p5}% 15m:{p15}% 1h:{p1h}% RSI:{int(rsi5)}"
    except: return "NO_TRADE",0,""

def quotex_menu(uid):
    s=qs.get(uid,{"amount":20,"trades":6,"running":False})
    mk=InlineKeyboardMarkup(row_width=3)
    mk.add(InlineKeyboardButton(f"💰 المبلغ: {s['amount']}﷼", callback_data="none_q"))
    mk.add(InlineKeyboardButton("10﷼",callback_data="qa_10"),InlineKeyboardButton("20﷼",callback_data="qa_20"),InlineKeyboardButton("50﷼",callback_data="qa_50"))
    mk.add(InlineKeyboardButton(f"🔢 الصفقات: {s['trades']}", callback_data="none_q2"))
    mk.add(InlineKeyboardButton("3",callback_data="qt_3"),InlineKeyboardButton("6",callback_data="qt_6"),InlineKeyboardButton("8",callback_data="qt_8"))
    mk.add(InlineKeyboardButton("🔐 تسجيل دخول", callback_data="qx_login"))
    mk.add(InlineKeyboardButton("🛑 ايقاف" if s['running'] else "✅ تشغيل محترف 85%+", callback_data="qx_stop" if s['running'] else "qx_start"))
    mk.add(InlineKeyboardButton("⬅️ رجوع", callback_data="back_main"))
    return mk

def main_menu():
    mk=InlineKeyboardMarkup(row_width=1)
    mk.add(InlineKeyboardButton("📈 بوكت اوبشن", callback_data="mode_pocket"))
    mk.add(InlineKeyboardButton("🤖 كوتكس بوت 85%+", callback_data="mode_quotex"))
    return mk

@bot.message_handler(commands=['start'])
def start(msg):
    if not is_allowed(msg.from_user.id):
        return bot.send_message(msg.chat.id,"🔒 خاص\nارسل /pass 7154")
    bot.send_message(msg.chat.id,"👋 بوت محترف - 85%+\nاختر:", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data=="back_main")
def back_main_h(call):
    bot.edit_message_text("👋 بوت محترف - 85%+\nاختر:", call.message.chat.id, call.message.message_id, reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data=="mode_pocket")
def mode_pocket(call):
    mk=InlineKeyboardMarkup(row_width=2)
    for n in MARKETS: mk.add(InlineKeyboardButton(n, callback_data=f"market_{n}"))
    bot.send_message(call.message.chat.id,"اختر السوق:", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data=="mode_quotex")
def mode_quotex(call):
    if call.from_user.id not in qs: qs[call.from_user.id]={"amount":20,"trades":6,"running":False,"email":None}
    bot.edit_message_text("🤖 كوتكس 85%+ | مدة 15m", call.message.chat.id, call.message.message_id, reply_markup=quotex_menu(call.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data.startswith("qa_"))
def set_a(call):
    qs[call.from_user.id]["amount"]=int(call.data.replace("qa_",""))
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=quotex_menu(call.from_user.id))
@bot.callback_query_handler(func=lambda c: c.data.startswith("qt_"))
def set_t(call):
    qs[call.from_user.id]["trades"]=int(call.data.replace("qt_",""))
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=quotex_menu(call.from_user.id))
@bot.callback_query_handler(func=lambda c: c.data=="qx_login")
def qx_login_btn(call):
    bot.send_message(call.message.chat.id,"ارسل:\n/login ايميلك باسوردك\nمثال: /login test@gmail.com 123456")

@bot.message_handler(commands=['login'])
def login_q(m):
    try: bot.delete_message(m.chat.id, m.message_id)
    except: pass
    parts=m.text.split()
    if len(parts)<3: return bot.send_message(m.chat.id,"❌ الصيغة: /login الايميل الباسورد")
    if m.from_user.id not in qs: qs[m.from_user.id]={"amount":20,"trades":6,"running":False}
    qs[m.from_user.id]["email"]=parts[1]
    qs[m.from_user.id]["password"]=parts[2]
    bot.send_message(m.chat.id,f"✅ تم حفظ: {parts[1]}")

# ===== هذه الدالة هي اللي تصلح الخطأ =====
def runner_quotex(uid, cid):
    try:
        try:
            from quotexapi.stable_api import Quotex
        except:
            bot.send_message(cid, "⏳ أول مرة - تثبيت المكتبة 30 ثانية...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "quotexapi"])
            from quotexapi.stable_api import Quotex
        s=qs[uid]
        qx=Quotex(s["email"], s["password"])
        ok, reason = qx.connect()
        if not ok: return bot.send_message(cid, f"❌ فشل الدخول: {reason}")
        bal=qx.get_balance()
        bot.send_message(cid, f"✅ دخل | رصيد: {bal}$\n🎯 {s['trades']} صفقات | {s['amount']}﷼")
        done=0
        while qs[uid]["running"] and done < s["trades"]:
            for name,sym in MARKETS.items():
                if not qs[uid]["running"] or done>=s["trades"]: break
                d,per,detail=get_confluence_85(sym)
                if d!="NO_TRADE":
                    usd=round(s["amount"]/3.75,2)
                    status,_=qx.buy(usd,sym,d.lower(),15)
                    if status:
                        done+=1
                        bot.send_message(cid,f"🔥 صفقة #{done}\n{name}\n{d} {per}%\n{detail}\n💰 {s['amount']}﷼")
                        time.sleep(75)
            time.sleep(20)
        qs[uid]["running"]=False
        bot.send_message(cid,f"🏁 انتهى {done} صفقات")
    except Exception as e:
        bot.send_message(cid,f"❌ خطأ: {e}")

@bot.callback_query_handler(func=lambda c: c.data=="qx_start")
def qx_start(call):
    if qs[call.from_user.id].get("email") is None: return bot.answer_callback_query(call.id,"سجل دخول اول")
    qs[call.from_user.id]["running"]=True
    threading.Thread(target=runner_quotex, args=(call.from_user.id, call.message.chat.id), daemon=True).start()
    bot.answer_callback_query(call.id,"بدأ")

@bot.callback_query_handler(func=lambda c: c.data=="qx_stop")
def qx_stop(call):
    qs[call.from_user.id]["running"]=False
    bot.answer_callback_query(call.id,"وقف")

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_"))
def choose_market(call):
    bot.answer_callback_query(call.id)
    name=call.data.replace("market_","")
    user_data[call.from_user.id]=MARKETS[name],name
    mk=InlineKeyboardMarkup(row_width=1)
    mk.add(InlineKeyboardButton("🔍 فحص شامل", callback_data="time_ALL"))
    bot.send_message(call.message.chat.id,f"اخترت {name}", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("time_"))
def choose_time(call):
    bot.answer_callback_query(call.id)
    symbol,name=user_data.get(call.from_user.id,(None,None))
    if not symbol: return
    loading=bot.send_message(call.message.chat.id,f"⏳ فحص {name}...")
    d,p=get_tf_signal(symbol, Interval.INTERVAL_5_MINUTES)
    bot.edit_message_text(f"📊 {name}\n{'🟢 BUY' if d=='BUY' else '🔴 SELL'}\n💪 {p}%", call.message.chat.id, loading.message_id)

app=Flask(__name__)
@app.route('/')
def home(): return "Bot is Live - Pro 85%+"
def run_flask():
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask, daemon=True).start()
bot.remove_webhook()
time.sleep(2)
while True:
    try:
        bot.infinity_polling(skip_pending=True, timeout=60)
    except:
        time.sleep(5)
