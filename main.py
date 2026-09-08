import os, time, threading
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval
from concurrent.futures import ThreadPoolExecutor, as_completed

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

# ========== منطق GainzAlgo V2 Alpha ==========
def get_tf_gainz(symbol, interval):
    for exchange in ["FX", "FX_IDC", "OANDA"]:
        try:
            h = TA_Handler(symbol=symbol, screener="forex", exchange=exchange, interval=interval)
            a = h.get_analysis()
            ind = a.indicators
            s = a.summary

            close = ind.get("close", 0)
            ema50 = ind.get("EMA50", 0)
            ema200 = ind.get("EMA200", 0)
            rsi = ind.get("RSI", 50)
            macd = ind.get("MACD.macd", 0)
            macd_sig = ind.get("MACD.signal", 0)

            buys, sells = s['BUY'], s['SELL']
            if buys+sells==0: continue

            # قوة الاشارة الاساسية
            base_power = int((max(buys,sells)/(buys+sells))*100)

            # === منطق GainzAlgo ===
            # BUY: السعر فوق EMA50 فوق EMA200 + RSI صاعد + MACD صاعد
            if close > ema50 > ema200 and rsi > 55 and rsi < 78 and macd > macd_sig:
                # كلما RSI اقرب لـ 60-70 القوة تزيد
                bonus = 10 if 60 <= rsi <= 70 else 5
                return "BUY", min(98, base_power + bonus), rsi, f"EMA صاعد"

            # SELL: السعر تحت EMA50 تحت EMA200 + RSI نازل + MACD نازل
            if close < ema50 < ema200 and rsi < 45 and rsi > 22 and macd < macd_sig:
                bonus = 10 if 30 <= rsi <= 40 else 5
                return "SELL", min(98, base_power + bonus), rsi, f"EMA هابط"

            # اذا ما في ترتيب EMA واضح = متذبذب
            return "SIDE", base_power, rsi, "تذبذب"

        except:
            time.sleep(0.3)
            continue
    return "ERROR",0,50,""

def get_signal(symbol):
    d5,p5,rsi5,txt5 = get_tf_gainz(symbol, Interval.INTERVAL_5_MINUTES)
    time.sleep(0.3)
    d15,p15,rsi15,txt15 = get_tf_gainz(symbol, Interval.INTERVAL_15_MINUTES)
    time.sleep(0.3)
    d1h,p1h,rsi1h,txt1h = get_tf_gainz(symbol, Interval.INTERVAL_1_HOUR)

    if "ERROR" in [d5,d15,d1h]:
        return "NO_TRADE",0,"⚠️ TradingView معلق"

    # لازم الثلاثة فريمات نفس الاتجاه مثل GainzAlgo
    if d5==d15==d1h and d5 in ["BUY","SELL"]:
        avg = int((p5+p15+p1h)/3)
        final = min(98, avg+3) # +3 مكافأة توافق الفريمات
        avg_rsi = int((rsi5+rsi15+rsi1h)/3)

        if final < 75:
            return "NO_TRADE",0,f"ضعيف {final}%"

        return d5, final, f"💎 GainzAlgo تأكيد:\nH1:{p1h}% {txt1h} RSI:{int(rsi1h)}\n15m:{p15}% {txt15} RSI:{int(rsi15)}\n5m:{p5}% {txt5} RSI:{int(rsi5)}\n⏱️ دخول 15 دقيقة - ثقة {final}%"

    return "NO_TRADE",0,f"H1:{d1h} {p1h}% | 15m:{d15} {p15}% | 5m:{d5} {p5}% - متضارب"

def get_golden_diamond_signal(symbol):
    d5,p5,rsi5,txt5 = get_tf_gainz(symbol, Interval.INTERVAL_5_MINUTES)
    time.sleep(0.3)
    d15,p15,rsi15,txt15 = get_tf_gainz(symbol, Interval.INTERVAL_15_MINUTES)
    time.sleep(0.3)
    d1h,p1h,rsi1h,txt1h = get_tf_gainz(symbol, Interval.INTERVAL_1_HOUR)

    if "ERROR" in [d5,d15,d1h]: return "NO_TRADE",0,""

    if d5==d15==d1h and d5 in ["BUY","SELL"]:
        if min(p5,p15,p1h) >= 88 and 35 < ((rsi5+rsi15+rsi1h)/3) < 65: # RSI مثالي للذهبي
            avg = int((p5+p15+p1h)/3)
            final = min(99, avg+6)
            if final >= 92:
                return d5, final, f"💎 H1:{p1h}% | 15m:{p15}% | 5m:{p5}% RSI:{int((rsi5+rsi15+rsi1h)/3)} - Gainz 99%"
    return "NO_TRADE",0,""

def main_menu(chat_id):
    m=InlineKeyboardMarkup(row_width=1)
    m.add(InlineKeyboardButton("💎 Gainz الذهبية 92%+ (نادر)", callback_data="golden_diamond"))
    m.add(InlineKeyboardButton("🔥 Gainz فحص شامل 80%+ (14 سوق)", callback_data="golden"))
    m.add(InlineKeyboardButton("📊 فحص سوق واحد Gainz", callback_data="single"))
    bot.send_message(chat_id,"🏆 MAD-BOT GainzAlgo V2 Style\nEMA50/200 + RSI + MACD - فحص 3 فريمات",reply_markup=m)

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id not in authorized:
        bot.send_message(msg.chat.id,"🔒 ارسل كلمة السر:"); return
    main_menu(msg.chat.id)

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def pw(m):
    if m.text.strip()==PASSWORD:
        authorized.add(m.from_user.id)
        bot.send_message(m.chat.id,"✅ تم - GainzAlgo مفعل"); main_menu(m.chat.id)
    else: bot.send_message(m.chat.id,"❌ غلط")

@bot.callback_query_handler(func=lambda c: True)
def calls(call):
    if call.from_user.id not in authorized: return
    if call.data=="golden":
        bot.answer_callback_query(call.id,"⏳ Gainz يفحص...")
        load=bot.send_message(call.message.chat.id,"⏳ GainzAlgo يفحص 14 سوق (5 ثواني)...")
        ok=[]
        with ThreadPoolExecutor(max_workers=14) as ex:
            futs={ex.submit(get_signal, sym): name for name,sym in MARKETS.items()}
            for f in as_completed(futs):
                name=futs[f]
                try:
                    d,p,det=f.result()
                    if d!="NO_TRADE" and p>=80:
                        emoji="🟢 BUY" if d=="BUY" else "🔴 SELL"
                        ok.append(f"{emoji} {name} - {p}%\n{det}")
                except: continue
        txt="\n\n".join(ok) if ok else "❌ لا يوجد Gainz 80%+ حاليا - السوق متذبذب (هذا يحميك)"
        m=InlineKeyboardMarkup(row_width=1); m.add(InlineKeyboardButton("🔄 تحديث Gainz",callback_data="golden"))
        bot.edit_message_text(txt, call.message.chat.id, load.message_id, reply_markup=m)

    elif call.data=="golden_diamond":
        bot.answer_callback_query(call.id,"💎 Gainz ذهبي...")
        load=bot.send_message(call.message.chat.id,"💎 فحص Gainz الذهبية 92%+...")
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
        txt=f"💎 وجدت {len(ok)} فرص Gainz ذهبية:\n\n" + "\n\n".join(ok) if ok else "💎 لا يوجد 92%+ حاليا"
        m=InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("💎 تحديث الذهبي",callback_data="golden_diamond"))
        m.add(InlineKeyboardButton("🔥 فحص Gainz عادي",callback_data="golden"))
        bot.edit_message_text(txt, call.message.chat.id, load.message_id, reply_markup=m)

    elif call.data=="single":
        m=InlineKeyboardMarkup(row_width=2)
        for name in MARKETS: m.add(InlineKeyboardButton(name, callback_data=f"s_{name}"))
        bot.send_message(call.message.chat.id,"اختر سوق - فحص Gainz:",reply_markup=m)
    elif call.data.startswith("s_"):
        name=call.data[2:]; sym=MARKETS[name]
        load=bot.send_message(call.message.chat.id,f"⏳ Gainz يفحص {name}...")
        d,p,det=get_signal(sym)
        bot.edit_message_text(f"📊 {name}\n{det}" if d=="NO_TRADE" else f"📊 {name}\n{'🟢 BUY' if d=='BUY' else '🔴 SELL'} {p}%\n{det}", call.message.chat.id, load.message_id)

app=Flask(__name__)
@app.route('/')
def h(): return "Live GainzAlgo V2"
def run(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
threading.Thread(target=run,daemon=True).start()
bot.remove_webhook(); time.sleep(2)
while True:
    try: bot.infinity_polling(skip_pending=True)
    except: time.sleep(5)
