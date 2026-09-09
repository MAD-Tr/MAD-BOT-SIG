import os, time, threading
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval

TOKEN = os.environ.get("TOKEN") or "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
PASSWORD = os.environ.get("PASSWORD") or "7154"
bot = telebot.TeleBot(TOKEN, threaded=False)

MARKETS = {
    "🇪🇺/🇺🇸 EUR/USD": "EURUSD", "🇺🇸/🇯🇵 USD/JPY": "USDJPY",
    "🇦🇺/🇺🇸 AUD/USD": "AUDUSD", "🇺🇸/🇨🇦 USD/CAD": "USDCAD",
    "🇪🇺/🇯🇵 EUR/JPY": "EURJPY", "🇨🇦/🇯🇵 CAD/JPY": "CADJPY",
    "🇦🇺/🇯🇵 AUD/JPY": "AUDJPY", "🇪🇺/🇨🇭 EUR/CHF": "EURCHF",
    "🇦🇺/🇨🇦 AUD/CAD": "AUDCAD", "🇪🇺/🇦🇺 EUR/AUD": "EURAUD",
    "🇺🇸/🇨🇭 USD/CHF": "USDCHF", "🇪🇺/🇨🇦 EUR/CAD": "EURCAD",
    "🇦🇺/🇨🇭 AUD/CHF": "AUDCHF", "🇨🇦/🇨🇭 CAD/CHF": "CADCHF",
    "🥇 GOLD": "GOLD",
}
authorized=set()

def analyze_tf(symbol, interval):
    try:
        exch = "TVC" if symbol=="GOLD" else "OANDA"
        h = TA_Handler(symbol=symbol, screener="cfd" if symbol=="GOLD" else "forex", exchange=exch, interval=interval)
        a = h.get_analysis()
        return a.summary["RECOMMENDATION"], a.indicators.get("ADX",0)
    except:
        return "NEUTRAL", 0

def get_conf(name, symbol):
    try:
        time.sleep(2)
        r5, adx5 = analyze_tf(symbol, Interval.INTERVAL_5_MINUTES)
        time.sleep(1)
        r15, adx15 = analyze_tf(symbol, Interval.INTERVAL_15_MINUTES)
        time.sleep(1)
        r1h, adx1h = analyze_tf(symbol, Interval.INTERVAL_1_HOUR)

        if ("BUY" in r5 and "BUY" in r15 and "BUY" in r1h):
            d="BUY"; adx_avg=(adx5+adx15+adx1h)/3
        elif ("SELL" in r5 and "SELL" in r15 and "SELL" in r1h):
            d="SELL"; adx_avg=(adx5+adx15+adx1h)/3
        else:
            return {"name":name, "dir":"WAIT", "conf":65}

        if adx_avg < 22: return {"name":name, "dir":"WAIT", "conf":70}
        conf = 86 + int(adx_avg/4) + (2 if "STRONG" in r15 else 0)
        conf = min(94, conf)
        return {"name":name, "dir":d, "conf":conf}
    except:
        return {"name":name, "dir":"WAIT", "conf":60}

def main_menu(cid):
    m=InlineKeyboardMarkup(row_width=1)
    m.add(InlineKeyboardButton("🏆 فرص 86%+ 3 فريمات", callback_data="best6"))
    m.add(InlineKeyboardButton("📊 سوق واحد", callback_data="single"))
    m.add(InlineKeyboardButton("📈 كل الاسواق", callback_data="all"))
    bot.send_message(cid,"🏆 MAD-BOT 3 فريمات", reply_markup=m)

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id not in authorized:
        bot.send_message(msg.chat.id,"🔒 كلمة السر:"); return
    main_menu(msg.chat.id)

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def pw(m):
    if m.text.strip()==PASSWORD:
        authorized.add(m.from_user.id); main_menu(m.chat.id)
    else: bot.send_message(m.chat.id,"❌ غلط")

@bot.callback_query_handler(func=lambda c: True)
def cb(call):
    if call.from_user.id not in authorized: return
    if call.data in ["best6","all","single"]:
        if call.data=="single":
            mk=InlineKeyboardMarkup(row_width=2)
            for n in MARKETS: mk.add(InlineKeyboardButton(n, callback_data=f"s_{n}"))
            bot.send_message(call.message.chat.id,"اختر:", reply_markup=mk); return
        bot.answer_callback_query(call.id,"⏳")
        load=bot.send_message(call.message.chat.id,"⏳ افحص 3 فريمات...")
        results=[get_conf(n,s) for n,s in MARKETS.items()]
        results=sorted(results, key=lambda x: x['conf'], reverse=True)
        trusted=[r for r in results if r['dir']!="WAIT"]

        if call.data=="all":
            txt="📊 كل الاسواق:\n\n"
            for i,r in enumerate(results,1):
                if r['dir']=="BUY": txt+=f"{i}. 🟢 {r['name']} - {r['conf']}% شراء\n"
                elif r['dir']=="SELL": txt+=f"{i}. 🔴 {r['name']} - {r['conf']}% بيع\n"
                else: txt+=f"{i}. {r['name']} - {r['conf']}% لا تدخل\n"
        else:
            if not trusted: txt="❌ مافي توافق 3 فريمات الحين"
            else:
                txt="🏆 فرص 86%+:\n\n"
                for i,r in enumerate(trusted[:6],1):
                    e="🟢" if r['dir']=="BUY" else "🔴"
                    t="شراء" if r['dir']=="BUY" else "بيع"
                    txt+=f"{i}. {e} {r['name']} - {r['conf']}% {t}\n"

        mk=InlineKeyboardMarkup(row_width=1)
        mk.add(InlineKeyboardButton("🏆 فرص 3 فريمات", callback_data="best6"))
        mk.add(InlineKeyboardButton("📊 سوق واحد", callback_data="single"))
        mk.add(InlineKeyboardButton("📈 كل الاسواق", callback_data="all"))
        bot.edit_message_text(txt, call.message.chat.id, load.message_id, reply_markup=mk)

    elif call.data.startswith("s_"):
        name=call.data[2:]
        load=bot.send_message(call.message.chat.id,f"⏳ {name}...")
        r=get_conf(name, MARKETS[name])
        if r['dir']=="BUY": txt=f"🟢 {r['name']} - {r['conf']}% شراء"
        elif r['dir']=="SELL": txt=f"🔴 {r['name']} - {r['conf']}% بيع"
        else: txt=f"{r['name']} - {r['conf']}% لا تدخل"
        mk=InlineKeyboardMarkup(row_width=1)
        mk.add(InlineKeyboardButton("🏆 فرص 3 فريمات", callback_data="best6"))
        mk.add(InlineKeyboardButton("📊 سوق واحد", callback_data="single"))
        mk.add(InlineKeyboardButton("📈 كل الاسواق", callback_data="all"))
        bot.edit_message_text(txt, call.message.chat.id, load.message_id, reply_markup=mk)

app=Flask(__name__)
@app.route('/')
def h(): return "MAD 3TF"
def run(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
threading.Thread(target=run, daemon=True).start()
bot.remove_webhook(); time.sleep(2)
while True:
    try: bot.infinity_polling(skip_pending=True, timeout=60)
    except: time.sleep(5)
