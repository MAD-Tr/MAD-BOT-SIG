import os, time, threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval

TOKEN = os.environ.get("TOKEN") or "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
bot = telebot.TeleBot(TOKEN, threaded=False)

PASSWORD = "7154"
allowed = {}
alert_real, alert_otc = {}, {}
loss_streak = {}
blocked = {}

MARKETS_REAL = {
    "🇪🇺/🇺🇸 EUR/USD":"EURUSD","🇬🇧/🇺🇸 GBP/USD":"GBPUSD","🇺🇸/🇯🇵 USD/JPY":"USDJPY",
    "🇦🇺/🇺🇸 AUD/USD":"AUDUSD","🇺🇸/🇨🇦 USD/CAD":"USDCAD","🇪🇺/🇯🇵 EUR/JPY":"EURJPY",
    "🇬🇧/🇯🇵 GBP/JPY":"GBPJPY","🇪🇺/🇬🇧 EUR/GBP":"EURGBP"
}
MARKETS_OTC = {
    "🇪🇺/🇺🇸 EUR/USD OTC":"EURUSD","🇬🇧/🇺🇸 GBP/USD OTC":"GBPUSD","🇺🇸/🇯🇵 USD/JPY OTC":"USDJPY",
    "🇦🇺/🇺🇸 AUD/USD OTC":"AUDUSD","🇪🇺/🇯🇵 EUR/JPY OTC":"EURJPY","🇬🇧/🇯🇵 GBP/JPY OTC":"GBPJPY"
}

def is_open():
    n=datetime.now()
    return not (n.weekday()>=5 or (n.weekday()==4 and n.hour>=23))

def pro_check(sym, ex):
    try:
        h=TA_Handler(symbol=sym, screener="forex", exchange=ex, interval=Interval.INTERVAL_5_MINUTES)
        a=h.get_analysis()
        ind=a.indicators
        rec=a.summary["RECOMMENDATION"]
        adx=ind.get("ADX",0)
        rsi=ind.get("RSI",50)
        ema20=ind.get("EMA20",0)
        ema50=ind.get("EMA50",0)
        macd=ind.get("MACD.macd",0)
        macd_sig=ind.get("MACD.signal",0)
        bb_up=ind.get("BB.upper",0)
        bb_low=ind.get("BB.lower",0)
        close=ind.get("close",0)
        if adx < 25: return 0,"WAIT"
        if rsi > 75 or rsi < 25: return 0,"WAIT"
        if close > bb_up*0.999 or close < bb_low*1.001: return 0,"WAIT"
        up = ema20 > ema50 and close > ema20 and macd > macd_sig
        down = ema20 < ema50 and close < ema20 and macd < macd_sig
        if up and "BUY" in rec and 30<rsi<70:
            conf = min(95, 82 + int((adx-25)//2))
            return conf,"BUY"
        if down and "SELL" in rec and 30<rsi<70:
            conf = min(95, 82 + int((adx-25)//2))
            return conf,"SELL"
    except: pass
    return 0,"WAIT"

def multi_pro(sym):
    res=[]
    for ex in ["OANDA","FXCM","FOREXCOM"]:
        c,d=pro_check(sym,ex)
        res.append((c,d))
        time.sleep(0.35)
    buys=sum(1 for _,d in res if d=="BUY")
    sells=sum(1 for _,d in res if d=="SELL")
    avg=sum(c for c,_ in res)//3 if res else 0
    if buys==3 and avg>=88: return avg,"BUY"
    if sells==3 and avg>=88: return avg,"SELL"
    if buys>=2 and avg>=85: return avg,"BUY"
    if sells>=2 and avg>=85: return avg,"SELL"
    for c,d in res:
        if c>=90 and d!="WAIT": return c,d
    return 0,"WAIT"

def jeddah_time():
    now = datetime.now(ZoneInfo("Asia/Riyadh"))
    nxt = now + timedelta(minutes=1)
    return nxt.strftime("%I:%M").lstrip("0") + (" ص" if nxt.hour < 12 else " م")

def scanner():
    while True:
        try:
            for cid,on in list(alert_real.items()):
                if not on: continue
                if cid in blocked and datetime.now()<blocked[cid]: continue
                if cid in blocked and datetime.now()>=blocked[cid]:
                    del blocked[cid]; loss_streak[cid]=0
                    bot.send_message(cid,"✅ انتهى الحظر")
                    alert_real[cid]=False; continue
                if not is_open():
                    bot.send_message(cid,"⏸️ السوق مقفل")
                    alert_real[cid]=False; continue
                for name,sym in MARKETS_REAL.items():
                    c,d=multi_pro(sym)
                    if c>=85 and d!="WAIT":
                        e="🟢 صعود" if d=="BUY" else "🔴 هبوط"
                        t=jeddah_time()
                        mk=InlineKeyboardMarkup(row_width=2)
                        mk.add(InlineKeyboardButton("✅ ربح", callback_data=f"win_{cid}"),
                               InlineKeyboardButton("❌ خسارة", callback_data=f"lose_{cid}"))
                        bot.send_message(cid,f"🔔 {name}\n{e} {c}%\n{t} ⏰", reply_markup=mk)
                        time.sleep(300); break
                    time.sleep(0.8)
            for cid,on in list(alert_otc.items()):
                if not on: continue
                if cid in blocked and datetime.now()<blocked[cid]: continue
                for name,sym in MARKETS_OTC.items():
                    c,d=multi_pro(sym)
                    if c>=85 and d!="WAIT":
                        e="🟢 صعود" if d=="BUY" else "🔴 هبوط"
                        t=jeddah_time()
                        mk=InlineKeyboardMarkup(row_width=2)
                        mk.add(InlineKeyboardButton("✅ ربح", callback_data=f"win_{cid}"),
                               InlineKeyboardButton("❌ خسارة", callback_data=f"lose_{cid}"))
                        bot.send_message(cid,f"🔔 {name}\n{e} {c}%\n{t} ⏰", reply_markup=mk)
                        time.sleep(300); break
                    time.sleep(0.8)
            time.sleep(40)
        except:
            time.sleep(10)

def kb_start():
    mk=InlineKeyboardMarkup(row_width=1)
    mk.add(InlineKeyboardButton("🏦 PRO REAL", callback_data="mode_real"))
    mk.add(InlineKeyboardButton("📟 PRO OTC", callback_data="mode_otc"))
    mk.add(InlineKeyboardButton("🔍 فحص سوق واحد", callback_data="single_main"))
    return mk

def kb_real(cid):
    mk=InlineKeyboardMarkup(row_width=1)
    if cid in blocked and datetime.now()<blocked[cid]:
        r=int((blocked[cid]-datetime.now()).total_seconds()//60)
        mk.add(InlineKeyboardButton(f"🛑 محظور {r} د", callback_data="blocked"))
    else:
        txt="⏸️ اطفاء" if alert_real.get(cid,False) else "▶️ تشغيل 24 ساعة"
        mk.add(InlineKeyboardButton(txt, callback_data="toggle_real"))
    mk.add(InlineKeyboardButton("💎 فرصة PRO", callback_data="gold_real"))
    mk.add(InlineKeyboardButton("🔍 فحص سوق واحد", callback_data="single_real"))
    mk.add(InlineKeyboardButton("⬅️ رجوع", callback_data="back_start"))
    return mk

def kb_otc(cid):
    mk=InlineKeyboardMarkup(row_width=1)
    if cid in blocked and datetime.now()<blocked[cid]:
        r=int((blocked[cid]-datetime.now()).total_seconds()//60)
        mk.add(InlineKeyboardButton(f"🛑 محظور {r} د", callback_data="blocked"))
    else:
        txt="⏸️ اطفاء" if alert_otc.get(cid,False) else "▶️ تشغيل 24 ساعة"
        mk.add(InlineKeyboardButton(txt, callback_data="toggle_otc"))
    mk.add(InlineKeyboardButton("💎 فرصة PRO", callback_data="gold_otc"))
    mk.add(InlineKeyboardButton("🔍 فحص سوق واحد", callback_data="single_otc"))
    mk.add(InlineKeyboardButton("⬅️ رجوع", callback_data="back_start"))
    return mk

@bot.message_handler(commands=['start'])
def start(m):
    cid=m.chat.id
    if cid in allowed and allowed[cid]:
        bot.send_message(cid,"اختر:", reply_markup=kb_start())
    else:
        msg=bot.send_message(cid,"🔒 الرقم السري:")
        bot.register_next_step_handler(msg, lambda x: check_pass(x))

def check_pass(m):
    cid=m.chat.id
    if m.text==PASSWORD:
        allowed[cid]=True
        bot.send_message(cid,"✅ حياك", reply_markup=kb_start())
    else:
        msg=bot.send_message(cid,"❌ غلط:")
        bot.register_next_step_handler(msg, lambda x: check_pass(x))

@bot.callback_query_handler(func=lambda c: True)
def cb(call):
    cid=call.message.chat.id; d=call.data
    if cid not in allowed or not allowed[cid]: return
    if d=="mode_real": bot.send_message(cid,"🏦 الحقيقي", reply_markup=kb_real(cid))
    elif d=="mode_otc": bot.send_message(cid,"📟 OTC", reply_markup=kb_otc(cid))
    elif d=="back_start": bot.send_message(cid,"اختر:", reply_markup=kb_start())
    elif d=="single_main":
        mk=InlineKeyboardMarkup(row_width=2)
        for n in MARKETS_REAL.keys(): mk.add(InlineKeyboardButton(n, callback_data=f"chkR_{n}"))
        for n in MARKETS_OTC.keys(): mk.add(InlineKeyboardButton(n, callback_data=f"chkO_{n}"))
        mk.add(InlineKeyboardButton("⬅️ رجوع", callback_data="back_start"))
        bot.send_message(cid,"الاسواق:", reply_markup=mk)
    elif d=="blocked":
        r=int((blocked[cid]-datetime.now()).total_seconds()//60)
        bot.send_message(cid,f"🛑 باقي {r} د", reply_markup=kb_real(cid))
    elif d=="toggle_real":
        if cid in blocked and datetime.now()<blocked[cid]: return
        alert_real[cid]=not alert_real.get(cid,False)
        bot.send_message(cid,"✅ شغال 24 ساعة" if alert_real[cid] else "⏸️ وقف", reply_markup=kb_real(cid))
    elif d=="toggle_otc":
        if cid in blocked and datetime.now()<blocked[cid]: return
        alert_otc[cid]=not alert_otc.get(cid,False)
        bot.send_message(cid,"✅ شغال 24 ساعة" if alert_otc[cid] else "⏸️ وقف", reply_markup=kb_otc(cid))
    elif d.startswith("win_"):
        loss_streak[cid]=0
        bot.send_message(cid,"✅", reply_markup=kb_real(cid))
    elif d.startswith("lose_"):
        loss_streak[cid]=loss_streak.get(cid,0)+1
        if loss_streak[cid]>=2:
            blocked[cid]=datetime.now()+timedelta(minutes=50)
            alert_real[cid]=False; alert_otc[cid]=False
            bot.send_message(cid,"🛑 وقفتك 50 د", reply_markup=kb_real(cid))
        else:
            bot.send_message(cid,f"⚠️ {loss_streak[cid]}/2", reply_markup=kb_real(cid))
    elif d=="gold_real":
        bot.send_message(cid,"⏳ جاري الفحص...")
        best=None
        for n,s in MARKETS_REAL.items():
            c,di=multi_pro(s)
            if not best or c>best[0]: best=(c,di,n)
        if best and best[0]>=85:
            e="🟢 صعود" if best[1]=="BUY" else "🔴 هبوط"
            t=jeddah_time()
            bot.send_message(cid,f"{best[2]}\n{e} {best[0]}%\n{t} ⏰", reply_markup=kb_real(cid))
        else: bot.send_message(cid,"⚪ انتظار - السوق متذبذب", reply_markup=kb_real(cid))
    elif d=="gold_otc":
        bot.send_message(cid,"⏳ جاري الفحص...")
        best=None
        for n,s in MARKETS_OTC.items():
            c,di=multi_pro(s)
            if not best or c>best[0]: best=(c,di,n)
        if best and best[0]>=85:
            e="🟢 صعود" if best[1]=="BUY" else "🔴 هبوط"
            t=jeddah_time()
            bot.send_message(cid,f"{best[2]}\n{e} {best[0]}%\n{t} ⏰", reply_markup=kb_otc(cid))
        else: bot.send_message(cid,"⚪ انتظار", reply_markup=kb_otc(cid))
    elif d=="single_real":
        mk=InlineKeyboardMarkup(row_width=2)
        for n in MARKETS_REAL.keys(): mk.add(InlineKeyboardButton(n, callback_data=f"chkR_{n}"))
        mk.add(InlineKeyboardButton("⬅️ رجوع", callback_data="mode_real"))
        bot.send_message(cid,"الاسواق:", reply_markup=mk)
    elif d=="single_otc":
        mk=InlineKeyboardMarkup(row_width=2)
        for n in MARKETS_OTC.keys(): mk.add(InlineKeyboardButton(n, callback_data=f"chkO_{n}"))
        mk.add(InlineKeyboardButton("⬅️ رجوع", callback_data="mode_otc"))
        bot.send_message(cid,"الاسواق:", reply_markup=mk)
    elif d.startswith("chkR_"):
        name=d.replace("chkR_","")
        c,di=multi_pro(MARKETS_REAL[name])
        e="🟢 صعود" if di=="BUY" else "🔴 هبوط" if di=="SELL" else "⚪ انتظار"
        t=jeddah_time()
        bot.send_message(cid,f"{name}\n{e} {c}%\n{t} ⏰" if c>=85 else f"{name}\n{e} - متذبذب", reply_markup=kb_real(cid))
    elif d.startswith("chkO_"):
        name=d.replace("chkO_","")
        c,di=multi_pro(MARKETS_OTC[name])
        e="🟢 صعود" if di=="BUY" else "🔴 هبوط" if di=="SELL" else "⚪ انتظار"
        t=jeddah_time()
        bot.send_message(cid,f"{name}\n{e} {c}%\n{t} ⏰" if c>=85 else f"{name}\n{e}", reply_markup=kb_otc(cid))

app=Flask(__name__)
@app.route('/')
def h(): return "OK"
threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000))), daemon=True).start()
threading.Thread(target=scanner, daemon=True).start()
bot.remove_webhook(); time.sleep(1)
while True:
    try: bot.infinity_polling(skip_pending=True)
    except: time.sleep(3)
