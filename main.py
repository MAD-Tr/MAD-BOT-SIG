import os, time, threading
from datetime import datetime, timedelta
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval

TOKEN = os.environ.get("TOKEN") or "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
bot = telebot.TeleBot(TOKEN, threaded=False)

PASSWORD = "7154" # غيره
allowed_users = {}

MARKETS_REAL = {
    "EUR/USD":"EURUSD","GBP/USD":"GBPUSD","USD/JPY":"USDJPY",
    "AUD/USD":"AUDUSD","USD/CAD":"USDCAD","EUR/JPY":"EURJPY",
    "GBP/JPY":"GBPJPY","EUR/GBP":"EURGBP"
}
MARKETS_OTC = {
    "EUR/USD OTC":"EURUSD","GBP/USD OTC":"GBPUSD","USD/JPY OTC":"USDJPY",
    "AUD/USD OTC":"AUDUSD","EUR/JPY OTC":"EURJPY","GBP/JPY OTC":"GBPJPY"
}

alert_real, alert_otc = {}, {}
loss_count = {}
blocked_until = {}

def is_open():
    now=datetime.now()
    return not (now.weekday()>=5 or (now.weekday()==4 and now.hour>=23))

def check_one_strong(symbol, exchange):
    try:
        h=TA_Handler(symbol=symbol, screener="forex", exchange=exchange, interval=Interval.INTERVAL_5_MINUTES)
        a=h.get_analysis()
        rec=a.summary["RECOMMENDATION"]
        adx=a.indicators.get("ADX", 0)
        rsi=a.indicators.get("RSI", 50)
        ema20=a.indicators.get("EMA20", 0)
        ema50=a.indicators.get("EMA50", 0)
        close=a.indicators.get("close", 0)
        if adx < 25: return 0,"WAIT"
        if rsi > 75 or rsi < 25: return 0,"WAIT"
        is_up = ema20 > ema50 and close > ema20
        is_down = ema20 < ema50 and close < ema20
        if "STRONG_BUY" in rec and is_up and 30 < rsi < 68: return 90,"BUY"
        if "STRONG_SELL" in rec and is_down and 32 < rsi < 70: return 90,"SELL"
        if "BUY" in rec and is_up and adx > 28 and 35 < rsi < 65: return 86,"BUY"
        if "SELL" in rec and is_down and adx > 28 and 35 < rsi < 65: return 86,"SELL"
    except: pass
    return 0,"WAIT"

def check_multi_strong(sym):
    res=[]
    for ex in ["OANDA","FXCM","FOREXCOM"]:
        c,d=check_one_strong(sym,ex)
        res.append((c,d))
        time.sleep(0.4)
    buys=sum(1 for _,d in res if d=="BUY")
    sells=sum(1 for _,d in res if d=="SELL")
    avg=sum(c for c,_ in res)//3 if res else 0
    if buys==3 and avg>=85: return avg,"BUY"
    if sells==3 and avg>=85: return avg,"SELL"
    return 0,"WAIT"

def scanner():
    while True:
        for cid,on in list(alert_real.items()):
            if not on: continue
            if cid in blocked_until and datetime.now() < blocked_until[cid]: continue
            if cid in blocked_until and datetime.now() >= blocked_until[cid]:
                del blocked_until[cid]; loss_count[cid]=0
                bot.send_message(cid,"✅ فك الحظر")
                alert_real[cid]=False; continue
            if not is_open():
                bot.send_message(cid,"⏸️ الحقيقي مقفل"); alert_real[cid]=False; continue
            for name,sym in MARKETS_REAL.items():
                c,d=check_multi_strong(sym)
                if c>=85 and d!="WAIT":
                    now=datetime.now(); nxt=(now+timedelta(minutes=1)).replace(second=2,microsecond=0)
                    wait=max(5,int((nxt-now).total_seconds()))
                    e="🟢 صعود" if d=="BUY" else "🔴 هبوط"
                    mk=InlineKeyboardMarkup(row_width=2)
                    mk.add(InlineKeyboardButton("✅ فزت", callback_data=f"win_{cid}"),
                           InlineKeyboardButton("❌ خسرت", callback_data=f"lose_{cid}"))
                    bot.send_message(cid,f"🔔 {name}\n{e} {c}%\n⏰ بعد {wait} ث", reply_markup=mk)
                    time.sleep(300); break
                time.sleep(1)
        for cid,on in list(alert_otc.items()):
            if not on: continue
            if cid in blocked_until and datetime.now() < blocked_until[cid]: continue
            for name,sym in MARKETS_OTC.items():
                c,d=check_multi_strong(sym)
                if c>=85 and d!="WAIT":
                    e="🟢 صعود" if d=="BUY" else "🔴 هبوط"
                    mk=InlineKeyboardMarkup(row_width=2)
                    mk.add(InlineKeyboardButton("✅ فزت", callback_data=f"win_{cid}"),
                           InlineKeyboardButton("❌ خسرت", callback_data=f"lose_{cid}"))
                    bot.send_message(cid,f"📟 {name}\n{e} {c}%", reply_markup=mk)
                    time.sleep(300); break
                time.sleep(1)
        time.sleep(60)

def kb_start():
    mk=InlineKeyboardMarkup(row_width=1)
    mk.add(InlineKeyboardButton("🏦 الحقيقي", callback_data="mode_real"))
    mk.add(InlineKeyboardButton("📟 OTC", callback_data="mode_otc"))
    return mk

def kb_real(cid):
    mk=InlineKeyboardMarkup(row_width=1)
    if cid in blocked_until and datetime.now() < blocked_until[cid]:
        r=int((blocked_until[cid]-datetime.now()).total_seconds()//60)
        mk.add(InlineKeyboardButton(f"🛑 محظور {r} د", callback_data="blocked"))
    else:
        txt="⏸️ اطفاء" if alert_real.get(cid,False) else "▶️ تشغيل"
        mk.add(InlineKeyboardButton(txt, callback_data="toggle_real"))
    mk.add(InlineKeyboardButton("✨ ذهبية", callback_data="gold_real"))
    mk.add(InlineKeyboardButton("🔍 فحص", callback_data="single_real"))
    mk.add(InlineKeyboardButton("⬅️ رجوع", callback_data="back_start"))
    return mk

def kb_otc(cid):
    mk=InlineKeyboardMarkup(row_width=1)
    if cid in blocked_until and datetime.now() < blocked_until[cid]:
        r=int((blocked_until[cid]-datetime.now()).total_seconds()//60)
        mk.add(InlineKeyboardButton(f"🛑 محظور {r} د", callback_data="blocked"))
    else:
        txt="⏸️ اطفاء" if alert_otc.get(cid,False) else "▶️ تشغيل"
        mk.add(InlineKeyboardButton(txt, callback_data="toggle_otc"))
    mk.add(InlineKeyboardButton("✨ ذهبية", callback_data="gold_otc"))
    mk.add(InlineKeyboardButton("🔍 فحص", callback_data="single_otc"))
    mk.add(InlineKeyboardButton("⬅️ رجوع", callback_data="back_start"))
    return mk

@bot.message_handler(commands=['start'])
def start(m):
    cid=m.chat.id
    if cid in allowed_users and allowed_users[cid]:
        bot.send_message(cid,"اختر:", reply_markup=kb_start())
    else:
        msg=bot.send_message(cid,"🔒 الرقم السري:")
        bot.register_next_step_handler(msg, check_pass)

def check_pass(m):
    cid=m.chat.id
    if m.text == PASSWORD:
        allowed_users[cid]=True
        bot.send_message(cid,"✅ حياك - اقوى نسخة 3/3", reply_markup=kb_start())
    else:
        msg=bot.send_message(cid,"❌ غلط:")
        bot.register_next_step_handler(msg, check_pass)

@bot.callback_query_handler(func=lambda c: True)
def cb(call):
    cid=call.message.chat.id; d=call.data
    if cid not in allowed_users or not allowed_users[cid]: return
    if d=="mode_real": bot.send_message(cid,"🏦 3/3 لازم يتفقون", reply_markup=kb_real(cid))
    elif d=="mode_otc": bot.send_message(cid,"📟 OTC قوي 3/3", reply_markup=kb_otc(cid))
    elif d=="back_start": bot.send_message(cid,"اختر:", reply_markup=kb_start())
    elif d=="blocked":
        r=int((blocked_until[cid]-datetime.now()).total_seconds()//60)
        bot.send_message(cid,f"🛑 باقي {r} د", reply_markup=kb_real(cid))
    elif d=="toggle_real":
        if cid in blocked_until and datetime.now() < blocked_until[cid]:
            r=int((blocked_until[cid]-datetime.now()).total_seconds()//60)
            bot.send_message(cid,f"🛑 محظور {r} د", reply_markup=kb_real(cid)); return
        alert_real[cid]=not alert_real.get(cid,False)
        bot.send_message(cid,"✅ شغال" if alert_real[cid] else "⏸️ وقف", reply_markup=kb_real(cid))
    elif d=="toggle_otc":
        if cid in blocked_until and datetime.now() < blocked_until[cid]:
            r=int((blocked_until[cid]-datetime.now()).total_seconds()//60)
            bot.send_message(cid,f"🛑 محظور {r} د", reply_markup=kb_otc(cid)); return
        alert_otc[cid]=not alert_otc.get(cid,False)
        bot.send_message(cid,"✅ شغال" if alert_otc[cid] else "⏸️ وقف", reply_markup=kb_otc(cid))
    elif d.startswith("win_"):
        loss_count[cid]=0; bot.send_message(cid,"✅", reply_markup=kb_real(cid))
    elif d.startswith("lose_"):
        loss_count[cid]=loss_count.get(cid,0)+1
        if loss_count[cid]>=2:
            blocked_until[cid]=datetime.now()+timedelta(minutes=50)
            alert_real[cid]=False; alert_otc[cid]=False
            bot.send_message(cid,"🛑 مرتين خسارة - وقفتك 50 د", reply_markup=kb_real(cid))
        else:
            bot.send_message(cid,f"⚠️ {loss_count[cid]}/2", reply_markup=kb_real(cid))
    elif d=="gold_real":
        bot.send_message(cid,"⏳ افحص 3 سيرفرات...")
        best=None
        for n,s in MARKETS_REAL.items():
            c,di=check_multi_strong(s)
            if not best or c>best[0]: best=(c,di,n)
        if best and best[0]>=85:
            e="🟢 صعود" if best[1]=="BUY" else "🔴 هبوط"
            bot.send_message(cid,f"{best[2]}\n{e} {best[0]}%", reply_markup=kb_real(cid))
        else: bot.send_message(cid,"⚪ ما فيه اتفاق 3/3", reply_markup=kb_real(cid))
    elif d=="gold_otc":
        bot.send_message(cid,"⏳ افحص OTC قوي...")
        best=None
        for n,s in MARKETS_OTC.items():
            c,di=check_multi_strong(s)
            if not best or c>best[0]: best=(c,di,n)
        if best and best[0]>=85:
            e="🟢 صعود" if best[1]=="BUY" else "🔴 هبوط"
            bot.send_message(cid,f"{best[2]}\n{e} {best[0]}%", reply_markup=kb_otc(cid))
        else: bot.send_message(cid,"⚪ ما فيه اتفاق 3/3", reply_markup=kb_otc(cid))
    elif d=="single_real":
        mk=InlineKeyboardMarkup(row_width=2)
        for n in MARKETS_REAL.keys(): mk.add(InlineKeyboardButton(n, callback_data=f"chkR_{n}"))
        mk.add(InlineKeyboardButton("⬅️ رجوع", callback_data="mode_real"))
        bot.send_message(cid,"اختر:", reply_markup=mk)
    elif d=="single_otc":
        mk=InlineKeyboardMarkup(row_width=2)
        for n in MARKETS_OTC.keys(): mk.add(InlineKeyboardButton(n, callback_data=f"chkO_{n}"))
        mk.add(InlineKeyboardButton("⬅️ رجوع", callback_data="mode_otc"))
        bot.send_message(cid,"اختر:", reply_markup=mk)
    elif d.startswith("chkR_"):
        name=d.replace("chkR_",""); c,di=check_multi_strong(MARKETS_REAL[name])
        e="🟢 صعود" if di=="BUY" else "🔴 هبوط" if di=="SELL" else "⚪ انتظار"
        bot.send_message(cid,f"{name}\n{e} {c}%", reply_markup=kb_real(cid))
    elif d.startswith("chkO_"):
        name=d.replace("chkO_",""); c,di=check_multi_strong(MARKETS_OTC[name])
        e="🟢 صعود" if di=="BUY" else "🔴 هبوط" if di=="SELL" else "⚪ انتظار"
        bot.send_message(cid,f"{name}\n{e} {c}%", reply_markup=kb_otc(cid))

app=Flask(__name__)
@app.route('/')
def h(): return "OK"
threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000))), daemon=True).start()
threading.Thread(target=scanner, daemon=True).start()
bot.remove_webhook(); time.sleep(1)
while True:
    try: bot.infinity_polling(skip_pending=True)
    except: time.sleep(3)
