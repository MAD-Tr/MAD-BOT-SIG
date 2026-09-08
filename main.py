import os, time, threading
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval
from concurrent.futures import ThreadPoolExecutor, as_completed

TOKEN = os.environ.get("TOKEN") or "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
PASSWORD = os.environ.get("PASSWORD") or "7154"
bot = telebot.TeleBot(TOKEN, threaded=True)

MARKETS = {
    "🇪🇺/🇺🇸 EUR/USD": "EURUSD", "🇺🇸/🇯🇵 USD/JPY": "USDJPY",
    "🇦🇺/🇺🇸 AUD/USD": "AUDUSD", "🇺🇸/🇨🇦 USD/CAD": "USDCAD",
    "🇪🇺/🇯🇵 EUR/JPY": "EURJPY", "🇨🇦/🇯🇵 CAD/JPY": "CADJPY",
    "🇦🇺/🇯🇵 AUD/JPY": "AUDJPY", "🇪🇺/🇨🇭 EUR/CHF": "EURCHF",
    "🇦🇺/🇨🇦 AUD/CAD": "AUDCAD", "🇪🇺/🇦🇺 EUR/AUD": "EURAUD",
    "🇺🇸/🇨🇭 USD/CHF": "USDCHF", "🇪🇺/🇨🇦 EUR/CAD": "EURCAD",
    "🇦🇺/🇨🇭 AUD/CHF": "AUDCHF", "🇨🇦/🇨🇭 CAD/CHF": "CADCHF",
}

authorized=set()

def get_tf_fast(symbol, interval):
    try:
        h = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=interval)
        a = h.get_analysis()
        s = a.summary
        rsi = a.indicators.get("RSI", 50)
        buys, sells = s['BUY'], s['SELL']
        if buys+sells==0: return "ERROR",0,50
        d="BUY" if buys>sells else "SELL"
        p=int((max(buys,sells)/(buys+sells))*100)
        return d,p,rsi
    except:
        return "ERROR",0,50

def get_signal(symbol):
    d5,p5,rsi5 = get_tf_fast(symbol, Interval.INTERVAL_5_MINUTES)
    d15,p15,rsi15 = get_tf_fast(symbol, Interval.INTERVAL_15_MINUTES)
    d1h,p1h,rsi1h = get_tf_fast(symbol, Interval.INTERVAL_1_HOUR)
    if "ERROR" in [d5,d15,d1h]:
        return "NO_TRADE",0,f"⚠️ معلق"
    if d5==d15==d1h:
        avg=int((p5+p15+p1h)/3)
        final=min(96, avg+5)
        avg_rsi=(rsi5+rsi15+rsi1h)/3
        if d5=="BUY" and avg_rsi>=75: return "NO_TRADE",0,f"متشبع"
        if d5=="SELL" and avg_rsi<=25: return "NO_TRADE",0,f"متشبع"
        if min(p5,p15,p1h) < 75: return "NO_TRADE",0,f"ضعيف"
        return d5,final,f"H1:{p1h}% | 15m:{p15}% | 5m:{p5}% RSI:{int(avg_rsi)} - ثقة {final}%"
    return "NO_TRADE",0,f"متضارب"

def get_golden_diamond_signal(symbol):
    d5,p5,rsi5 = get_tf_fast(symbol, Interval.INTERVAL_5_MINUTES)
    d15,p15,rsi15 = get_tf_fast(symbol, Interval.INTERVAL_15_MINUTES)
    d1h,p1h,rsi1h = get_tf_fast(symbol, Interval.INTERVAL_1_HOUR)
    if "ERROR" in [d5,d15,d1h]:
        return "NO_TRADE",0,"ERROR"
    if d5==d15==d1h:
        if min(p5,p15,p1h) >= 90:
            avg=int((p5+p15+p1h)/3)
            final=min(99, avg+7)
            avg_rsi=(rsi5+rsi15+rsi1h)/3
            if 30 < avg_rsi < 70:
                return d5,final,f"💎 H1:{p1h}% | 15m:{p15}% | 5m:{p5}% RSI:{int(avg_rsi)}"
    return "NO_TRADE",0,""

# === الخط الصغير الفخم + إضافات ===
def make_bar(p):
    total = 10 # صغير وناعم
    filled = int(p / 100 * total)
    bar = "━" * filled + "─" * (total - filled)
    return f"{bar} {p}%"

def get_status(p):
    if p < 20: return "⏳ نجهز البيانات..."
    elif p < 45: return "📊 نحلل الشموع..."
    elif p < 70: return "🧠 الذكاء يفلتر..."
    elif p < 90: return "💎 نبحث عن الذهب..."
    else: return "🔥 قربنا..."

def main_menu(chat_id):
    m=InlineKeyboardMarkup(row_width=1)
    m.add(InlineKeyboardButton("💎 السوق الذهبي 99% (نادر)", callback_data="golden_diamond"))
    m.add(InlineKeyboardButton("🔥 فحص شامل 85%+ (14 سوق)", callback_data="golden"))
    m.add(InlineKeyboardButton("📊 فحص سوق واحد", callback_data="single"))
    bot.send_message(chat_id,"🏆 البوت الاسطوري V3 💸",reply_markup=m)

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id not in authorized:
        bot.send_message(msg.chat.id,"🔒 ارسل كلمة السر:"); return
    main_menu(msg.chat.id)

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def pw(m):
    if m.text.strip()==PASSWORD:
        authorized.add(m.from_user.id)
        bot.send_message(m.chat.id,"✅ تم"); main_menu(m.chat.id)
    else: bot.send_message(m.chat.id,"❌ غلط")

def do_golden_scan(chat_id, load_id):
    ok = []
    progress = {'done': 0}
    def scan_task():
        with ThreadPoolExecutor(max_workers=14) as ex:
            futs={ex.submit(get_signal, sym): name for name,sym in MARKETS.items()}
            for f in as_completed(futs):
                progress['done'] += 1
                name=futs[f]
                try:
                    d,p,det=f.result()
                    if d!="NO_TRADE" and p>=85:
                        emoji="🟢 BUY" if d=="BUY" else "🔴 SELL"
                        ok.append(f"{emoji} {name} - {p}%\n{det}")
                except: continue
    t = threading.Thread(target=scan_task, daemon=True)
    t.start()
    for i in range(1, 101):
        try:
            status = get_status(i)
            left = int((100-i)*0.15)
            txt = f"🔥 جاري الفحص شامل\n{make_bar(i)}\n{status}\nتم {progress['done']}/14 • باقي {left}ث"
            bot.edit_message_text(txt, chat_id, load_id)
        except: pass
        time.sleep(0.15)
    t.join()
    txt="\n\n".join(ok) if ok else "❌ لا يوجد 85%+ حاليا - جرب 3:30 العصر"
    m=InlineKeyboardMarkup(row_width=1); m.add(InlineKeyboardButton("🔄 تحديث",callback_data="golden"))
    try: bot.edit_message_text(txt, chat_id, load_id, reply_markup=m)
    except: bot.send_message(chat_id, txt, reply_markup=m)

def do_diamond_scan(chat_id, load_id):
    ok = []
    progress = {'done': 0}
    def scan_task():
        with ThreadPoolExecutor(max_workers=14) as ex:
            futs={ex.submit(get_golden_diamond_signal, sym): name for name,sym in MARKETS.items()}
            for f in as_completed(futs):
                progress['done'] += 1
                name=futs[f]
                try:
                    d,p,det=f.result()
                    if d!="NO_TRADE" and p>=95:
                        emoji="💎🟢 BUY" if d=="BUY" else "💎🔴 SELL"
                        ok.append(f"{emoji} {name} - {p}%\n{det}")
                except: continue
    t = threading.Thread(target=scan_task, daemon=True)
    t.start()
    for i in range(1, 101):
        try:
            status = get_status(i)
            left = int((100-i)*0.15)
            txt = f"💎 جاري الفحص\n{make_bar(i)}\n{status}\nتم {progress['done']}/14 • باقي {left}ث"
            bot.edit_message_text(txt, chat_id, load_id)
        except: pass
        time.sleep(0.15)
    t.join()
    txt=f"💎💎 وجدت {len(ok)} فرص 99%:\n\n" + "\n\n".join(ok) if ok else "💎 لا يوجد 99% حاليا - وقت الذهب 3:30-6:30 م"
    m=InlineKeyboardMarkup(row_width=1)
    m.add(InlineKeyboardButton("💎 تحديث الذهبي",callback_data="golden_diamond"))
    m.add(InlineKeyboardButton("🔥 فحص عادي 85%+",callback_data="golden"))
    try: bot.edit_message_text(txt, chat_id, load_id, reply_markup=m)
    except: bot.send_message(chat_id, txt, reply_markup=m)

def do_single_scan(chat_id, load_id, name, sym):
    result = {}
    def scan_task():
        d,p,det=get_signal(sym)
        result['d']=d; result['p']=p; result['det']=det
    t = threading.Thread(target=scan_task, daemon=True)
    t.start()
    for i in range(1, 101):
        try:
            status = get_status(i)
            left = int((100-i)*0.15)
            txt = f"📊 جاري فحص {name}\n{make_bar(i)}\n{status} • باقي {left}ث"
            bot.edit_message_text(txt, chat_id, load_id)
        except: pass
        time.sleep(0.15)
    t.join()
    d=result.get('d','NO_TRADE'); p=result.get('p',0); det=result.get('det','')
    txt=f"📊 {name}\n{det}" if d=="NO_TRADE" else f"📊 {name}\n{'🟢 BUY' if d=='BUY' else '🔴 SELL'} {p}%\n{det}"
    try: bot.edit_message_text(txt, chat_id, load_id)
    except: bot.send_message(chat_id, txt)

@bot.callback_query_handler(func=lambda c: True)
def calls(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    if call.data=="golden":
        load=bot.send_message(call.message.chat.id,f"🔥 جاري الفحص شامل\n{make_bar(1)}\n⏳ نجهز...")
        threading.Thread(target=do_golden_scan, args=(call.message.chat.id, load.message_id), daemon=True).start()
    elif call.data=="golden_diamond":
        load=bot.send_message(call.message.chat.id,f"💎 جاري الفحص\n{make_bar(1)}\n⏳ نجهز...")
        threading.Thread(target=do_diamond_scan, args=(call.message.chat.id, load.message_id), daemon=True).start()
    elif call.data=="single":
        m=InlineKeyboardMarkup(row_width=2)
        for n in MARKETS: m.add(InlineKeyboardButton(n, callback_data=f"s_{n}"))
        bot.send_message(call.message.chat.id,"اختر:",reply_markup=m)
    elif call.data.startswith("s_"):
        name=call.data[2:]; sym=MARKETS[name]
        load=bot.send_message(call.message.chat.id,f"📊 جاري فحص {name}\n{make_bar(1)}")
        threading.Thread(target=do_single_scan, args=(call.message.chat.id, load.message_id, name, sym), daemon=True).start()

app=Flask(__name__)
@app.route('/')
def h(): return "Live V4 Turbo"
def run(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
threading.Thread(target=run,daemon=True).start()
bot.remove_webhook(); time.sleep(1)
while True:
    try: bot.infinity_polling(skip_pending=True, timeout=60)
    except: time.sleep(3)
