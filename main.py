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
}

authorized=set()

def get_tf_fixed(symbol, interval):
    for exchange in ["FX", "FX_IDC", "OANDA"]:
        try:
            h = TA_Handler(symbol=symbol, screener="forex", exchange=exchange, interval=interval)
            a = h.get_analysis()
            s = a.summary
            rsi = a.indicators.get("RSI", 50)
            buys, sells = s['BUY'], s['SELL']
            if buys+sells==0: continue
            d="BUY" if buys>sells else "SELL"
            p=int((max(buys,sells)/(buys+sells))*100)
            return d,p,rsi
        except:
            time.sleep(0.3)
            continue
    return "ERROR",0,50

def get_signal(symbol):
    d5,p5,rsi5 = get_tf_fixed(symbol, Interval.INTERVAL_5_MINUTES)
    time.sleep(0.5)
    d15,p15,rsi15 = get_tf_fixed(symbol, Interval.INTERVAL_15_MINUTES)
    time.sleep(0.5)
    d1h,p1h,rsi1h = get_tf_fixed(symbol, Interval.INTERVAL_1_HOUR)

    if "ERROR" in [d5,d15,d1h]:
        return "NO_TRADE",0,f"⚠️ TradingView معلق جرب بعد دقيقة"

    if d5==d15==d1h:
        avg=int((p5+p15+p1h)/3)
        final=min(96, avg+5)
        avg_rsi=(rsi5+rsi15+rsi1h)/3
        if d5=="BUY" and avg_rsi>=75: return "NO_TRADE",0,f"⚠️ متشبع شراء RSI:{int(avg_rsi)}"
        if d5=="SELL" and avg_rsi<=25: return "NO_TRADE",0,f"⚠️ متشبع بيع RSI:{int(avg_rsi)}"
        if min(p5,p15,p1h) < 75: return "NO_TRADE",0,f"ضعيف"
        return d5,final,f"H1:{p1h}% RSI:{int(rsi1h)} | 15m:{p15}% RSI:{int(rsi15)} | 5m:{p5}% RSI:{int(rsi5)}\n⏱️ دخول 15 دقيقة - ثقة {final}%"
    return "NO_TRADE",0,f"H1:{p1h}% {d1h} | 15m:{p15}% {d15} | 5m:{p5}% {d5} - متضارب"

def main_menu(chat_id):
    m=InlineKeyboardMarkup(row_width=1)
    m.add(InlineKeyboardButton("🔥 فحص شامل 85%+ (14 سوق)", callback_data="golden"))
    m.add(InlineKeyboardButton("📊 فحص سوق واحد", callback_data="single"))
    bot.send_message(chat_id,"🏆 البوت الاسطوري V3",reply_markup=m)

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

@bot.callback_query_handler(func=lambda c: True)
def calls(call):
    if call.from_user.id not in authorized: return
    if call.data=="golden":
        bot.answer_callback_query(call.id,"⏳ افحص...")
        load=bot.send_message(call.message.chat.id,"⏳ افحص 14 سوق (30 ثانية)...")
        ok=[]
        for name,sym in MARKETS.items():
            try:
                d,p,det=get_signal(sym)
                if d!="NO_TRADE" and p>=85:
                    emoji="🟢 BUY" if d=="BUY" else "🔴 SELL"
                    ok.append(f"{emoji} {name} - {p}%\n{det}")
                time.sleep(1)
            except: continue
        txt="\n\n".join(ok) if ok else "❌ لا يوجد 85%+ حاليا"
        m=InlineKeyboardMarkup(row_width=1); m.add(InlineKeyboardButton("🔄 تحديث",callback_data="golden"))
        bot.edit_message_text(txt, call.message.chat.id, load.message_id, reply_markup=m)
    elif call.data=="single":
        m=InlineKeyboardMarkup(row_width=2)
        for name in MARKETS: m.add(InlineKeyboardButton(name, callback_data=f"s_{name}"))
        bot.send_message(call.message.chat.id,"اختر:",reply_markup=m)
    elif call.data.startswith("s_"):
        name=call.data[2:]; sym=MARKETS[name]
        load=bot.send_message(call.message.chat.id,f"⏳ {name}...")
        d,p,det=get_signal(sym)
        bot.edit_message_text(f"📊 {name}\n{det}" if d=="NO_TRADE" else f"📊 {name}\n{'🟢 BUY' if d=='BUY' else '🔴 SELL'} {p}%\n{det}", call.message.chat.id, load.message_id)

app=Flask(__name__)
@app.route('/')
def h(): return "Live V3 Fixed"
def run(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
threading.Thread(target=run,daemon=True).start()
bot.remove_webhook(); time.sleep(2)
while True:
    try: bot.infinity_polling(skip_pending=True)
    except: time.sleep(5)
