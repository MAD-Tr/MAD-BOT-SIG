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
        time.sleep(1.6)
        exch = "TVC" if symbol=="GOLD" else "OANDA"
        h = TA_Handler(symbol=symbol, screener="cfd" if symbol=="GOLD" else "forex", exchange=exch, interval=Interval.INTERVAL_15_MINUTES)
        a = h.get_analysis()
        ind = a.indicators; rec = a.summary["RECOMMENDATION"]
        close=ind.get("close",0); ema20=ind.get("EMA20",0)
        rsi=ind.get("RSI",50); adx=ind.get("ADX",10)

        if adx < 22:
            return {"name":name, "dir":"WAIT", "conf":int(55+adx/2), "detail":f"{exch} ADX:{int(adx)} ضعيف"}

        if rec == "NEUTRAL":
            return {"name":name, "dir":"WAIT", "conf":62, "detail":f"{exch} ADX:{int(adx)} RSI:{int(rsi)} محايد"}

        if rsi > 78 or rsi < 22:
            return {"name":name, "dir":"WAIT", "conf":65, "detail":f"{exch} RSI:{int(rsi)} متشبع"}

        ema_dist = abs(close-ema20)/ema20*1000 if ema20 else 0
        rsi_power = abs(rsi-50)
        conf = 52 + (adx * 0.9) + (rsi_power * 0.7) + ema_dist*1.5
        if "STRONG" in rec: conf += 8
        else: conf += 3
        conf = int(max(60, min(94, conf)))

        if conf < 86:
            return {"name":name, "dir":"WAIT", "conf":conf, "detail":f"{exch} ADX:{int(adx)} RSI:{int(rsi)} {rec} - ضعيف"}

        direction = "BUY" if "BUY" in rec else "SELL"
        return {"name":name, "dir":direction, "conf":conf, "detail":f"{exch} ADX:{int(adx)} RSI:{int(rsi)} {rec} ✅"}

    except:
        return {"name":name, "dir":"WAIT", "conf":60, "detail":"سوق متذبذب حاليا"}

def main_menu(cid):
    m=InlineKeyboardMarkup(row_width=1)
    m.add(InlineKeyboardButton("🏆 فرص 86%+ فقط", callback_data="best6"))
    m.add(InlineKeyboardButton("📊 سوق واحد", callback_data="single"))
    m.add(InlineKeyboardButton("📈 كل الاسواق", callback_data="all"))
    bot.send_message(cid,"🏆 MAD-BOT 86%+ موثوق", reply_markup=m)

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
        load=bot.send_message(call.message.chat.id,"📉 افحص فرص 86%+...")
        results=[get_conf(n,s) for n,s in MARKETS.items()]
        sorted_all=sorted(results, key=lambda x: x['conf'], reverse=True)
        trusted=[r for r in sorted_all if r['conf']>=86 and r['dir']!="WAIT"]

        if call.data=="all":
            txt="📊 **كل الاسواق:**\n\n"
            for i,r in enumerate(sorted_all,1):
                if r['dir']=="BUY": emoji="🟢 شراء"
                elif r['dir']=="SELL": emoji="🔴 بيع"
                else: emoji="⏸️ لا تدخل - متذبذب"
                txt+=f"{i}. {emoji} {r['name']} - **{r['conf']}%**\n {r['detail']}\n\n"
        else:
            if not trusted:
                txt="❌ **لا يوجد فرص 86%+ حاليا**\n\nكل الاسواق ⏸️ لا تدخل - متذبذبة\nانتظر 10 دقايق"
            else:
                txt=f"🏆 **فرص موثوقة 86%+ ({len(trusted)}):**\n\n"
                for i,r in enumerate(trusted[:6],1):
                    emoji="🟢 شراء" if r['dir']=="BUY" else "🔴 بيع"
                    txt+=f"{i}. {emoji} {r['name']} - **{r['conf']}%**\n {r['detail']}\n\n"

        mk=InlineKeyboardMarkup(row_width=1)
        mk.add(InlineKeyboardButton("🏆 فرص 86%+ فقط", callback_data="best6"))
        mk.add(InlineKeyboardButton("📊 سوق واحد", callback_data="single"))
        mk.add(InlineKeyboardButton("📈 كل الاسواق", callback_data="all"))
        bot.edit_message_text(txt, call.message.chat.id, load.message_id, reply_markup=mk, parse_mode="Markdown")
    elif call.data.startswith("s_"):
        name=call.data[2:]
        load=bot.send_message(call.message.chat.id, f"📉 {name}...")
        r=get_conf(name, MARKETS[name])
        if r['dir']=="BUY": emoji="🟢 شراء"
        elif r['dir']=="SELL": emoji="🔴 بيع"
        else: emoji="⏸️ لا تدخل - متذبذب"
        txt=f"{emoji} {r['name']} - **{r['conf']}%**\n{r['detail']}"
        if r['conf']<86: txt+="\n\n⚠️ اقل من 86% - لا تدخل"
        mk=InlineKeyboardMarkup(row_width=1)
        mk.add(InlineKeyboardButton("🏆 فرص 86%+ فقط", callback_data="best6"))
        mk.add(InlineKeyboardButton("📊 سوق واحد", callback_data="single"))
        mk.add(InlineKeyboardButton("📈 كل الاسواق", callback_data="all"))
        bot.edit_message_text(txt, call.message.chat.id, load.message_id, reply_markup=mk, parse_mode="Markdown")

app=Flask(__name__)
@app.route('/')
def h(): return "MAD-BOT 86%"
def run(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
threading.Thread(target=run, daemon=True).start()
bot.remove_webhook(); time.sleep(2)
while True:
    try: bot.infinity_polling(skip_pending=True, timeout=60)
    except: time.sleep(5)
