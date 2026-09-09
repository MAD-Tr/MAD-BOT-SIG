import os, time, threading
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval
from concurrent.futures import ThreadPoolExecutor, as_completed

TOKEN = os.environ.get("TOKEN") or "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
PASSWORD = os.environ.get("PASSWORD") or "7154"
bot = telebot.TeleBot(TOKEN, threaded=False)

# === اسواقك الحقيقية الـ 14 ===
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

# === V3 المطور - 7 مؤشرات ===
def get_tf_gainz_v3(symbol, interval):
    for exchange in ["FX","FX_IDC","OANDA"]:
        try:
            h = TA_Handler(symbol=symbol, screener="forex", exchange=exchange, interval=interval)
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

            if adx < 20: # اهم فلتر - يلغي التذبذب اللي مضيعك اليوم
                return "SIDE",0,rsi,f"ADX:{int(adx)} ضعيف"

            score_buy=0; score_sell=0
            if close > ema50 > ema200: score_buy+=1
            if close < ema50 < ema200: score_sell+=1
            if 55 < rsi < 75: score_buy+=1
            if 25 < rsi < 45: score_sell+=1
            if macd > macd_sig: score_buy+=1
            else: score_sell+=1
            if adx > 25: score_buy+=1; score_sell+=1
            if stoch_k > 50 and stoch_k < 80: score_buy+=1
            if stoch_k < 50 and stoch_k > 20: score_sell+=1

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
        return "NO_TRADE",0,f"ADX ضعيف - متذبذب\n5m:{t5} 15m:{t15} 1H:{t1h}"

    if d5==d15==d1h and d5 in ["BUY","SELL"]:
        avg = int((p5+p15+p1h)/3)
        if avg >= 78:
            return d5, min(99,avg+4), f"🔥 V3:\nH1:{p1h}% {t1h} RSI:{int(r1h)}\n15m:{p15}% {t15} RSI:{int(r15)}\n5m:{p5}% {t5} RSI:{int(r5)}\n⏱️ دخول 15 دقيقة - ثقة {avg}%"
    return "NO_TRADE",0,f"H1:{d1h} {p1h}% | 15m:{d15} {p15}% | 5m:{d5} {p5}% - متضارب"

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
                return d5, min(99,avg+5), f"💎 V3 H1:{p1h}% | 15m:{p15}% | 5m:{p5}% ADX قوي - ثقة {avg}%"
    return "NO_TRADE",0,""

def main_menu(chat_id):
    m=InlineKeyboardMarkup(row_width=1)
    m.add(InlineKeyboardButton("💎 Gainz V3 الذهبية 90%+ (نادر)", callback_data="golden_diamond"))
    m.add(InlineKeyboardButton("🔥 Gainz V3 فحص شامل 78%+ (14 سوق)", callback_data="golden"))
    m.add(InlineKeyboardButton("📊 فحص سوق واحد V3", callback_data="single"))
    bot.send_message(chat_id,"🏆 MAD-BOT V3\n14 سوق حقيقية + ADX فلتر + 7 مؤشرات",reply_markup=m)

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id not in authorized:
        bot.send_message(msg.chat.id,"🔒 ارسل كلمة السر:"); return
    main_menu(msg.chat.id)

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def pw(m):
    if m.text.strip()==PASSWORD:
        authorized.add(m.from_user.id)
        bot.send_message(m.chat.id,"✅ V3 مفعل - 14 سوق"); main_menu(m.chat.id)
    else: bot.send_message(m.chat.id,"❌ غلط")

@bot.callback_query_handler(func=lambda c: True)
def calls(call):
    if call.from_user.id not in authorized: return
    if call.data=="golden":
        bot.answer_callback_query(call.id,"⏳ V3 يفحص...")
        load=bot.send_message(call.message.chat.id,"⏳ V3 يفحص 14 سوق حقيقية (5 ثواني)...")
        ok=[]
        with ThreadPoolExecutor(max_workers=14) as ex:
            futs={ex.submit(get_signal, sym): name for name,sym in MARKETS.items()}
            for f in as_completed(futs):
                name=futs[f]
                try:
                    d,p,det=f.result()
                    if d!="NO_TRADE" and p>=78:
                        emoji="🟢 BUY" if d=="BUY" else "🔴 SELL"
                        ok.append(f"{emoji} {name} - {p}%\n{det}")
                except: continue
        txt="\n\n".join(ok) if ok else "❌ لا يوجد 78%+ حاليا - ADX ضعيف (السوق متذبذب وهذا يحميك)"
        m=InlineKeyboardMarkup(row_width=1); m.add(InlineKeyboardButton("🔄 تحديث V3",callback_data="golden"))
        bot.edit_message_text(txt, call.message.chat.id, load.message_id, reply_markup=m)

    elif call.data=="golden_diamond":
        bot.answer_callback_query(call.id,"💎 V3 ذهبي...")
        load=bot.send_message(call.message.chat.id,"💎 فحص الذهبية 90%+...")
        ok=[]
        with ThreadPoolExecutor(max_workers=14) as ex:
            futs={ex.submit(get_golden_diamond_signal, sym): name for name,sym in MARKETS.items()}
            for f in as_completed(futs):
                name=futs[f]
                try:
                    d,p,det=f.result()
                    if d!="NO_TRADE":
                        emoji="💎🟢 BUY" if d=="BUY" else "💎🔴 SELL"
                        ok.append(f"{emoji} {name} - {p}%\n{det}")
                except: continue
        txt=f"💎 وجدت {len(ok)} فرص ذهبية V3:\n\n" + "\n\n".join(ok) if ok else "💎 لا يوجد 90%+ حاليا"
        m=InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("💎 تحديث الذهبي",callback_data="golden_diamond"))
        m.add(InlineKeyboardButton("🔥 فحص V3 عادي",callback_data="golden"))
        bot.edit_message_text(txt, call.message.chat.id, load.message_id, reply_markup=m)

    elif call.data=="single":
        m=InlineKeyboardMarkup(row_width=2)
        for name in MARKETS: m.add(InlineKeyboardButton(name, callback_data=f"s_{name}"))
        bot.send_message(call.message.chat.id,"اختر سوق من 14 سوق حقيقية:",reply_markup=m)
    elif call.data.startswith("s_"):
        name=call.data[2:]; sym=MARKETS[name]
        load=bot.send_message(call.message.chat.id,f"⏳ V3 يفحص {name}...")
        d,p,det=get_signal(sym)
        bot.edit_message_text(f"📊 {name}\n{det}" if d=="NO_TRADE" else f"📊 {name}\n{'🟢 BUY' if d=='BUY' else '🔴 SELL'} {p}%\n{det}", call.message.chat.id, load.message_id)

app=Flask(__name__)
@app.route('/')
def h(): return "Live V3 14 Markets"
def run(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
threading.Thread(target=run,daemon=True).start()
bot.remove_webhook(); time.sleep(2)
while True:
    try: bot.infinity_polling(skip_pending=True)
    except: time.sleep(5)
