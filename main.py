import os, time, threading
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval
from concurrent.futures import ThreadPoolExecutor, as_completed

TOKEN = os.environ.get("TOKEN") or "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
PASSWORD = os.environ.get("PASSWORD") or "7154"
bot = telebot.TeleBot(TOKEN, threaded=False)

# === 14 سوق حقيقية + GOLD OTC ===
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

def get_tf_gainz_v3(symbol, interval):
    # GOLD OTC يفحص من TVC
    if symbol == "GOLD":
        screener = "cfd"
        exchanges = ["TVC", "OANDA", "FX"]
    else:
        screener = "forex"
        exchanges = ["FX", "FX_IDC", "OANDA"]

    for exchange in exchanges:
        try:
            h = TA_Handler(symbol=symbol, screener=screener, exchange=exchange, interval=interval)
            a = h.get_analysis()
            ind = a.indicators
            close = ind.get("close",0)
            ema50 = ind.get("EMA50",0)
            ema200 = ind.get("EMA200",0)
            rsi = ind.get("RSI",50)
            macd = ind.get("MACD.macd",0)
            macd_sig = ind.get("MACD.signal",0)
            adx = ind.get("ADX",0)
            stoch_k = ind.get("Stoch.K",50)

            if adx < 20:
                return "SIDE",0,rsi,f"ADX:{int(adx)} ضعيف"

            score_buy=0; score_sell=0
            if close > ema50 > ema200: score_buy+=1
            if close < ema50 < ema200: score_sell+=1
            if 55 < rsi < 75: score_buy+=1
            if 25 < rsi < 45: score_sell+=1
            if macd > macd_sig: score_buy+=1
            else: score_sell+=1
            if adx > 25: score_buy+=1; score_sell+=1
            if 50 < stoch_k < 80: score_buy+=1
            if 20 < stoch_k < 50: score_sell+=1

            if score_buy >= 4:
                conf = min(99, 70 + score_buy*6 + int((adx-20)/2))
                return "BUY", conf, rsi, f"ADX:{int(adx)}"
            if score_sell >= 4:
                conf = min(99, 70 + score_sell*6 + int((adx-20)/2))
                return "SELL", conf, rsi, f"ADX:{int(adx)}"
            return "SIDE",0,rsi,"نقاط قليلة"
        except:
            time.sleep(0.2)
            continue
    return "ERROR",0,50,""

def get_signal(symbol):
    d5,p5,r5,t5 = get_tf_gainz_v3(symbol, Interval.INTERVAL_5_MINUTES)
    time.sleep(0.2)
    d15,p15,r15,t15 = get_tf_gainz_v3(symbol, Interval.INTERVAL_15_MINUTES)
    time.sleep(0.2)
    d1h,p1h,r1h,t1h = get_tf_gainz_v3(symbol, Interval.INTERVAL_1_HOUR)

    if "ERROR" in [d5,d15,d1h]:
        return "NO_TRADE",0,"⚠️ TradingView معلق"
    if "SIDE" in [d5,d15,d1h]:
        return "NO_TRADE",0,f"متذبذب\n5m:{t5} 15m:{t15} 1H:{t1h}"

    if d5==d15==d1h and d5 in ["BUY","SELL"]:
        avg = int((p5+p15+p1h)/3)
        if avg >= 78:
            return d5, min(99,avg+4), f"🔥 V3:\nH1:{p1h}% {t1h} RSI:{int(r1h)}\n15m:{p15}% {t15} RSI:{int(r15)}\n5m:{p5}% {t5} RSI:{int(r5)}\n⏱️ دخول 15 دقيقة"
    return "NO_TRADE",0,f"H1:{d1h} {p1h}% | 15m:{d15} {p15}% | 5m:{d5} {p5}%"

def get_golden_diamond_signal(symbol):
    d5,p5,r5,t5 = get_tf_gainz_v3(symbol, Interval.INTERVAL_5_MINUTES)
    time.sleep(0.2)
    d15,p15,r15,t15 = get_tf_gainz_v3(symbol, Interval.INTERVAL_15_MINUTES)
    time.sleep(0.2)
    d1h,p1h,r1h,t1h = get_tf_gainz_v3(symbol, Interval.INTERVAL_1_HOUR)
    if "SIDE" in [d5,d15,d1h] or "ERROR" in [d5,d15,d1h]:
        return "NO_TRADE",0,""
    if d5==d15==d1h and d5 in ["BUY","SELL"]:
        if min(p5,p15,p1h) >= 85:
            avg = int((p5+p15+p1h)/3)
            if avg >= 90:
                return d5, min(99,avg+5), f"💎 H1:{p1h}% | 15m:{p15}% | 5m:{p5}% - ADX قوي"
    return "NO_TRADE",0,""

def main_menu(chat_id):
    m=InlineKeyboardMarkup(row_width=1)
    m.add(InlineKeyboardButton("💎 Gainz الذهبية 90%+ (15 سوق)", callback_data="golden_diamond"))
    m.add(InlineKeyboardButton("🔥 Gainz شامل 78%+ (15 سوق)", callback_data="golden"))
    m.add(InlineKeyboardButton("📊 فحص سوق واحد", callback_data="single"))
    bot.send_message(chat_id,"🏆 MAD-BOT V3 - 14 سوق + GOLD OTC",reply_markup=m)

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id not in authorized:
        bot.send_message(msg.chat.id,"🔒 ارسل كلمة السر:"); return
    main_menu(msg.chat.id)

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def pw(m):
    if m.text.strip()==PASSWORD:
        authorized.add(m.from_user.id)
        bot.send_message(m.chat.id,"✅ مفعل - 15 سوق"); main_menu(m.chat.id)
    else: bot.send_message(m.chat.id,"❌ غلط")

@bot.callback_query_handler(func=lambda c: True)
def calls(call):
    if call.from_user.id not in authorized: return
    if call.data=="golden":
        bot.answer_callback_query(call.id,"⏳ يفحص...")
        load=bot.send_message(call.message.chat.id,"⏳ يفحص 15 سوق...")
        ok=[]
        with ThreadPoolExecutor(max_workers=15) as ex:
            futs={ex.submit(get_signal, sym): name for name,sym in MARKETS.items()}
            for f in as_completed(futs):
                name=futs[f]
                try:
                    d,p,det=f.result()
                    if d!="NO_TRADE" and p>=78:
                        emoji="🟢 BUY" if d=="BUY" else "🔴 SELL"
                        ok.append(f"{emoji} {name} - {p}%\n{det}")
                except: continue
        txt="\n\n".join(ok) if ok else "❌ لا يوجد 78%+ حاليا - السوق متذبذب (هذا يحميك)"
        m=InlineKeyboardMarkup(row_width=1); m.add(InlineKeyboardButton("🔄 تحديث Gainz 🔄",callback_data="golden"))
        bot.edit_message_text(txt, call.message.chat.id, load.message_id, reply_markup=m)

    elif call.data=="golden_diamond":
        bot.answer_callback_query(call.id,"💎 ذهبي...")
        load=bot.send_message(call.message.chat.id,"💎 فحص الذهبية 90%+...")
        ok=[]
        with ThreadPoolExecutor(max_workers=15) as ex:
            futs={ex.submit(get_golden_diamond_signal, sym): name for name,sym in MARKETS.items()}
            for f in as_completed(futs):
                name=futs[f]
                try:
                    d,p,det=f.result()
                    if d!="NO_TRADE":
                        emoji="💎🟢 BUY" if d=="BUY" else "💎🔴 SELL"
                        ok.append(f"{emoji} {name} - {p}%\n{det}")
                except: continue
        txt=f"💎 وجدت {len(ok)} ذهبية:\n\n" + "\n\n".join(ok) if ok else "💎 لا يوجد 90%+ حاليا"
        m=InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("💎 تحديث الذهبي",callback_data="golden_diamond"))
        m.add(InlineKeyboardButton("🔥 فحص عادي",callback_data="golden"))
        bot.edit_message_text(txt, call.message.chat.id, load.message_id, reply_markup=m)

    elif call.data=="single":
        m=InlineKeyboardMarkup(row_width=2)
        for name in MARKETS: m.add(InlineKeyboardButton(name, callback_data=f"s_{name}"))
        bot.send_message(call.message.chat.id,"اختر سوق:",reply_markup=m)
    elif call.data.startswith("s_"):
        name=call.data[2:]; sym=MARKETS[name]
        load=bot.send_message(call.message.chat.id,f"⏳ يفحص {name}...")
        d,p,det=get_signal(sym)
        bot.edit_message_text(f"📊 {name}\n{det}" if d=="NO_TRADE" else f"📊 {name}\n{'🟢 BUY' if d=='BUY' else '🔴 SELL'} {p}%\n{det}", call.message.chat.id, load.message_id)

app=Flask(__name__)
@app.route('/')
def h(): return "Live V3 15 Markets"
def run(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
threading.Thread(target=run,daemon=True).start()
bot.remove_webhook(); time.sleep(2)
while True:
    try: bot.infinity_polling(skip_pending=True)
    except: time.sleep(5)
