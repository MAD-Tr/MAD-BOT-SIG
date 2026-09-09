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
    "🥇 GOLD OTC": "GOLD",
}
authorized=set()

def get_conf(name, symbol):
    try:
        time.sleep(1.2)
        if symbol=="GOLD":
            h = TA_Handler(symbol="GOLD", screener="cfd", exchange="TVC", interval=Interval.INTERVAL_15_MINUTES)
        else:
            h = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=Interval.INTERVAL_15_MINUTES)
        a = h.get_analysis()
        ind = a.indicators
        rec = a.summary["RECOMMENDATION"]

        close=ind.get("close",0); ema20=ind.get("EMA20",0); ema50=ind.get("EMA50",0)
        rsi=ind.get("RSI",50); macd=ind.get("MACD.macd",0); macd_sig=ind.get("MACD.signal",0)
        adx=ind.get("ADX",0); cci=ind.get("CCI20",0); stoch_k=ind.get("Stoch.K",50)

        score=0
        if close>ema20>ema50: score+=25
        elif close<ema20<ema50: score+=25
        elif close>ema50: score+=10
        elif close<ema50: score+=10
        if 60<=rsi<=78: score+=20
        elif 22<=rsi<=40: score+=20
        elif 50<=rsi<=60 or 40<=rsi<=50: score+=10
        if macd>macd_sig: score+=20
        else: score+=20
        if adx>=25: score+=25
        elif adx>=20: score+=15
        elif adx>=15: score+=5
        if (cci>0 and stoch_k>50) or (cci<0 and stoch_k<50): score+=10

        conf = min(96, 50 + score)
        if rec=="STRONG_BUY": conf=min(98,conf+8); direction="BUY"
        elif rec=="BUY": direction="BUY"
        elif rec=="STRONG_SELL": conf=min(98,conf+8); direction="SELL"
        elif rec=="SELL": direction="SELL"
        else: direction="SIDE"; conf=int(conf*0.6)

        if conf<55: direction="SIDE"
        if adx<15: conf=int(conf*0.7)

        detail=f"{'TVC' if symbol=='GOLD' else 'FX'} ADX:{int(adx)} RSI:{int(rsi)} {rec}"
        return {"name":name, "dir":direction, "conf":conf, "rsi":int(rsi), "detail":detail}
    except Exception as e:
        return {"name":name, "dir":"SIDE", "conf":58, "rsi":50, "detail":f"TV بطيء"}

def main_menu(cid):
    m=InlineKeyboardMarkup(row_width=1)
    m.add(InlineKeyboardButton("🏆 البحث عن فرص ذهبية", callback_data="best6"))
    m.add(InlineKeyboardButton("📊 البحث بسوق واحد", callback_data="single"))
    m.add(InlineKeyboardButton("📈 البحث بكل الاسواق", callback_data="all"))
    bot.send_message(cid,"🏆 MAD-BOT V3 - 14", reply_markup=m)

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id not in authorized:
        bot.send_message(msg.chat.id,"🔒 ارسل كلمة السر:"); return
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
            bot.send_message(call.message.chat.id,"اختر السوق:", reply_markup=mk)
            return

        bot.answer_callback_query(call.id, "⏳")
        load=bot.send_message(call.message.chat.id, "📉 جاري تحليل 15 سوق...")

        results=[]
        for name, sym in MARKETS.items():
            results.append(get_conf(name, sym))

        sorted_all = sorted(results, key=lambda x: x['conf'], reverse=True)
        filtered = [r for r in sorted_all if r['dir']!="SIDE"]

        if call.data=="all":
            txt="📊 **كل الاسواق:**\n\n"
            for i,r in enumerate(sorted_all,1):
                emoji="🟢 BUY" if r['dir']=="BUY" else "🔴 SELL" if r['dir']=="SELL" else "⚪ SIDE"
                txt+=f"{i}. {emoji} {r['name']} - **{r['conf']}%**\n {r['detail']}\n\n"
        else:
            if not filtered:
                txt="❌ لا يوجد فرص ذهبية حاليا"
            else:
                top6 = filtered[:6]
                txt=f"🏆 **فرص ذهبية ({len(top6)}):**\n\n"
                for i,r in enumerate(top6,1):
                    emoji="🟢 BUY" if r['dir']=="BUY" else "🔴 SELL"
                    txt+=f"{i}. {emoji} {r['name']} - **{r['conf']}%**\n {r['detail']}\n ⏱️ 15 دقيقة\n\n"
                txt+=f"🏆 **الافضل:** {top6[0]['name']} {top6[0]['conf']}% {top6[0]['dir']}"

        mk=InlineKeyboardMarkup(row_width=1)
        mk.add(InlineKeyboardButton("🏆 البحث عن فرص ذهبية", callback_data="best6"))
        mk.add(InlineKeyboardButton("📊 البحث بسوق واحد", callback_data="single"))
        mk.add(InlineKeyboardButton("📈 البحث بكل الاسواق", callback_data="all"))
        bot.edit_message_text(txt, call.message.chat.id, load.message_id, reply_markup=mk, parse_mode="Markdown")

    elif call.data.startswith("s_"):
        name=call.data[2:]
        load=bot.send_message(call.message.chat.id, f"📉 جاري تحليل {name}...")
        r=get_conf(name, MARKETS[name])
        emoji="🟢 BUY" if r['dir']=="BUY" else "🔴 SELL" if r['dir']=="SELL" else "⚪ SIDE"
        txt=f"{emoji} {r['name']} - **{r['conf']}%**\n{r['detail']}"
        mk=InlineKeyboardMarkup(row_width=1)
        mk.add(InlineKeyboardButton("🏆 البحث عن فرص ذهبية", callback_data="best6"))
        mk.add(InlineKeyboardButton("📊 البحث بسوق واحد", callback_data="single"))
        mk.add(InlineKeyboardButton("📈 البحث بكل الاسواق", callback_data="all"))
        bot.edit_message_text(txt, call.message.chat.id, load.message_id, reply_markup=mk, parse_mode="Markdown")

app=Flask(__name__)
@app.route('/')
def h(): return "MAD-BOT V3-14"
def run(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
threading.Thread(target=run, daemon=True).start()
bot.remove_webhook(); time.sleep(2)
while True:
    try: bot.infinity_polling(skip_pending=True, timeout=60)
    except: time.sleep(5)
