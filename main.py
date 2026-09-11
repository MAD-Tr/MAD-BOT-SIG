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
allowed = {}; alert_real = {}; loss_streak = {}; blocked = {}; history = {}

MARKETS_REAL = {"🇪🇺/🇺🇸 EUR/USD":"EURUSD","🇬🇧/🇺🇸 GBP/USD":"GBPUSD","🇺🇸/🇯🇵 USD/JPY":"USDJPY","🇪🇺/🇯🇵 EUR/JPY":"EURJPY"}
TEACHER_PATTERNS = {
    "EURUSD": {"best_hours": [8,9,13,14,15,20,21], "avoid_adx_below": 25, "best_rsi": (48,62)},
    "GBPUSD": {"best_hours": [8,9,10,14,15,20], "avoid_adx_below": 27, "best_rsi": (45,60)},
    "USDJPY": {"best_hours": [2,3,8,9,20,21,22], "avoid_adx_below": 23, "best_rsi": (50,65)},
    "EURJPY": {"best_hours": [8,9,13,14,20,21], "avoid_adx_below": 25, "best_rsi": (46,61)}
}

def is_open():
    n=datetime.now()
    return not (n.weekday()>=5 or (n.weekday()==4 and n.hour>=23))

def jeddah_time():
    now = datetime.now(ZoneInfo("Asia/Riyadh"))
    nxt = now + timedelta(minutes=1)
    h12 = nxt.hour % 12
    if h12==0: h12=12
    am_pm = "ص" if nxt.hour < 12 else "م"
    return f"{h12}:{nxt.minute:02d} {am_pm}", nxt.hour

def strong_ai(symbol):
    try:
        teacher = TEACHER_PATTERNS.get(symbol)
        time_str, hour_now = jeddah_time()
        if hour_now not in teacher["best_hours"]:
            return 0,"WAIT","مو ساعة ذهبية"
        h5 = TA_Handler(symbol=symbol, screener="forex", exchange="OANDA", interval=Interval.INTERVAL_5_MINUTES)
        h15 = TA_Handler(symbol=symbol, screener="forex", exchange="OANDA", interval=Interval.INTERVAL_15_MINUTES)
        a5 = h5.get_analysis().indicators
        s5 = h5.get_analysis().summary
        s15 = h15.get_analysis().summary
        rsi = a5.get("RSI",50); adx = a5.get("ADX",20)
        ema20 = a5.get("EMA20",0); ema50 = a5.get("EMA50",0); ema200 = a5.get("EMA200",0)
        close = a5.get("close",0); open_ = a5.get("open",0)
        macd = a5.get("MACD.macd",0); macd_sig = a5.get("MACD.signal",0)
        stoch_k = a5.get("Stoch.K",50); stoch_d = a5.get("Stoch.D",50)
        bb_upper = a5.get("BB.upper",0); bb_lower = a5.get("BB.lower",0)
        if adx < teacher["avoid_adx_below"]: return 0,"WAIT","ADX ضعيف"
        rsi_low, rsi_high = teacher["best_rsi"]
        if not (rsi_low <= rsi <= rsi_high): return 0,"WAIT","RSI"
        if close > ema20 > ema50 > ema200: bias="BUY"; score=75
        elif close < ema20 < ema50 < ema200: bias="SELL"; score=25
        else: return 0,"WAIT","متوسطات"
        if bias=="BUY" and (macd-macd_sig) < 0.0002: return 0,"WAIT","MACD"
        if bias=="SELL" and (macd-macd_sig) > -0.0002: return 0,"WAIT","MACD"
        if bias=="BUY": score+=8
        else: score-=8
        if bias=="BUY" and not (stoch_k < 35 and stoch_k > stoch_d): return 0,"WAIT","ستوكاستك"
        if bias=="SELL" and not (stoch_k > 65 and stoch_k < stoch_d): return 0,"WAIT","ستوكاستك"
        if bias=="BUY" and close >= bb_upper*0.998: return 0,"WAIT","بولنجر"
        if bias=="SELL" and close <= bb_lower*1.002: return 0,"WAIT","بولنجر"
        rec5 = s5["RECOMMENDATION"]; rec15 = s15["RECOMMENDATION"]
        if bias=="BUY" and "BUY" in rec5 and "BUY" in rec15 and "STRONG_BUY" in rec5: score+=15
        elif bias=="SELL" and "SELL" in rec5 and "SELL" in rec15 and "STRONG_SELL" in rec5: score-=15
        else: return 0,"WAIT","مو STRONG"
        if abs(close-open_)*10000 < 3: return 0,"WAIT","شمعة ضعيفة"
        if score>=88: return 94,"BUY","وحش 90%"
        elif score<=12: return 94,"SELL","وحش 90%"
        else: return 0,"WAIT",""
    except: return 0,"WAIT","خطأ"

def scanner():
    while True:
        try:
            for cid,on in list(alert_real.items()):
                if not on: continue
                if cid in blocked and datetime.now()<blocked[cid]: continue
                if cid in blocked and datetime.now()>=blocked[cid]:
                    del blocked[cid]; loss_streak[cid]=0
                    bot.send_message(cid,"✅ انتهى الحظر 30د - رجع الوحش")
                    alert_real[cid]=False; continue
                if not is_open(): bot.send_message(cid,"⏸️ السوق مقفل"); alert_real[cid]=False; continue
                for name,sym in MARKETS_REAL.items():
                    c,d,p = strong_ai(sym)
                    if c>=90 and d!="WAIT":
                        e="🟢 صعود" if d=="BUY" else "🔴 هبوط"
                        t,_ = jeddah_time()
                        mk=InlineKeyboardMarkup(row_width=2)
                        mk.add(InlineKeyboardButton("✅ ربح", callback_data=f"win_{cid}"), InlineKeyboardButton("❌ خسارة", callback_data=f"lose_{cid}"))
                        bot.send_message(cid,f"💪🏻 الوحش 90%+\n🔔 {name}\n{e} {c}%\n📊 {p}\n⏱️ 15 دقيقة\n{t} ⏰", reply_markup=mk)
                        time.sleep(600); break
                    time.sleep(1.5)
            time.sleep(60)
        except: time.sleep(10)

def kb_start():
    mk=InlineKeyboardMarkup(row_width=1)
    mk.add(InlineKeyboardButton("💪🏻 بوت الوحش 90%", callback_data="mode_real"))
    return mk

def kb_real(cid):
    mk=InlineKeyboardMarkup(row_width=1)
    if cid in blocked and datetime.now()<blocked[cid]:
        r=int((blocked[cid]-datetime.now()).total_seconds()//60)
        mk.add(InlineKeyboardButton(f"🛑 محظور {r} د", callback_data="blocked"))
    else:
        txt="⏸️ اطفاء" if alert_real.get(cid,False) else "▶️ تشغيل الوحش 24س"
        mk.add(InlineKeyboardButton(txt, callback_data="toggle_real"))
    mk.add(InlineKeyboardButton("💎 فرصة وحش", callback_data="gold_real"))
    mk.add(InlineKeyboardButton("⬅️ رجوع", callback_data="back_start"))
    return mk

@bot.message_handler(commands=['start'])
def start(m):
    cid=m.chat.id
    if cid in allowed and allowed[cid]:
        bot.send_message(cid,"💪🏻 جاهز - وقف 30د", reply_markup=kb_start())
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
    if d=="mode_real": bot.send_message(cid,"💪🏻 الوحش - 90% - وقف 30د", reply_markup=kb_real(cid))
    elif d=="back_start": bot.send_message(cid,"اختر:", reply_markup=kb_start())
    elif d=="blocked":
        r=int((blocked[cid]-datetime.now()).total_seconds()//60)
        bot.send_message(cid,f"🛑 باقي {r} د", reply_markup=kb_real(cid))
    elif d=="toggle_real":
        if cid in blocked and datetime.now()<blocked[cid]: return
        alert_real[cid]=not alert_real.get(cid,False)
        bot.send_message(cid,"✅ شغال" if alert_real[cid] else "⏸️ وقف", reply_markup=kb_real(cid))
    elif d.startswith("win_"):
        loss_streak[cid]=0
        history[cid]=history.get(cid,[])+[1]
        bot.send_message(cid,f"💪🏻 {sum(history[cid])}/{len(history[cid])}", reply_markup=kb_real(cid))
    elif d.startswith("lose_"):
        loss_streak[cid]=loss_streak.get(cid,0)+1
        history[cid]=history.get(cid,[])+[0]
        if loss_streak[cid]>=2:
            blocked[cid]=datetime.now()+timedelta(minutes=30)
            alert_real[cid]=False
            bot.send_message(cid,"🛑 وقف 30 د", reply_markup=kb_real(cid))
        else:
            bot.send_message(cid,f"⚠️ {loss_streak[cid]}/2", reply_markup=kb_real(cid))
    elif d=="gold_real":
        bot.send_message(cid,"💪🏻 يفحص...")
        best=None
        for n,s in MARKETS_REAL.items():
            c,di,p = strong_ai(s)
            if not best or c>best[0]: best=(c,di,n,p)
        if best and best[0]>=90:
            e="🟢 صعود" if best[1]=="BUY" else "🔴 هبوط"
            t,_ = jeddah_time()
            bot.send_message(cid,f"💪🏻 {best[2]}\n{e} {best[0]}%\n📊 {best[3]}\n⏱️ 15 دقيقة\n{t} ⏰", reply_markup=kb_real(cid))
        else: bot.send_message(cid,"⚪ ينتظر ساعة ذهبية", reply_markup=kb_real(cid))

app=Flask(__name__)
@app.route('/')
def h(): return "OK MONSTER 30MIN"
threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000))), daemon=True).start()
threading.Thread(target=scanner, daemon=True).start()
bot.remove_webhook(); time.sleep(1)
while True:
    try: bot.infinity_polling(skip_pending=True)
    except: time.sleep(3)
