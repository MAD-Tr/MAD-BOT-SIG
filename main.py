import telebot
from telebot import types
import threading
from flask import Flask
from tradingview_ta import TA_Handler, Interval
import time
import os

TOKEN = os.environ.get("TOKEN") or "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
PASSWORD = os.environ.get("PASSWORD") or "7154"
bot = telebot.TeleBot(TOKEN)

MARKETS = {
    "🇪🇺/🇺🇸 EUR/USD": "EURUSD",
    "🇬🇧/🇺🇸 GBP/USD": "GBPUSD",
    "🇺🇸/🇯🇵 USD/JPY": "USDJPY",
    "🇦🇺/🇺🇸 AUD/USD": "AUDUSD",
    "🇺🇸/🇨🇦 USD/CAD": "USDCAD",
    "🇪🇺/🇯🇵 EUR/JPY": "EURJPY",
    "🇬🇧/🇯🇵 GBP/JPY": "GBPJPY",
    "🇺🇸/🇨🇭 USD/CHF": "USDCHF",
    "🇪🇺/🇬🇧 EUR/GBP": "EURGBP",
    "🇦🇺/🇯🇵 AUD/JPY": "AUDJPY",
    "🇪🇺/🇦🇺 EUR/AUD": "EURAUD",
    "🇬🇧/🇦🇺 GBP/AUD": "GBPAUD",
    "🇺🇸/🇿🇦 USD/ZAR": "USDZAR",
    "🇪🇺/🇨🇦 EUR/CAD": "EURCAD",
    "🇬🇧/🇨🇦 GBP/CAD": "GBPCAD",
    "🇳🇿/🇺🇸 NZD/USD": "NZDUSD",
    "🇪🇺/🇳🇿 EUR/NZD": "EURNZD",
}

authorized = set()

def get_ta(symbol, interval):
    try:
        handler = TA_Handler(symbol=f"{symbol}", exchange="FX", screener="forex", interval=interval)
        analysis = handler.get_analysis()
        rec = analysis.summary["RECOMMENDATION"]
        buy = analysis.summary["BUY"]
        sell = analysis.summary["SELL"]
        rsi = analysis.indicators.get("RSI", 50)
        total = buy + sell
        perc = int((buy / total * 100)) if rec == "BUY" else int((sell / total * 100)) if rec == "SELL" else 50
        return rec, perc, rsi
    except:
        return "NEUTRAL", 50, 50

def get_confluence_signal(symbol):
    rec_h1, p_h1, rsi_h1 = get_ta(symbol, Interval.INTERVAL_1_HOUR)
    rec_15, p_15, rsi_15 = get_ta(symbol, Interval.INTERVAL_15_MINUTES)
    rec_5, p_5, rsi_5 = get_ta(symbol, Interval.INTERVAL_5_MINUTES)
    rsi = rsi_5
    if rec_h1 == rec_15 == rec_5 and rec_h1 in ["BUY", "SELL"]:
        avg_p = int((p_h1 + p_15 + p_5) / 3)
        if avg_p >= 75:
            if 30 < rsi < 70:
                decision = f"🔥🔥 ذهبي قوي - RSI {round(rsi,1)} ممتاز - ادخل 2%"
            else:
                decision = f"⚠️ قوي بس RSI {round(rsi,1)} متشبع - ادخل 1% فقط"
        else:
            decision = "متوسط"
        det = f"H1:{p_h1}% {rec_h1} | 15m:{p_15}% {rec_15} | 5m:{p_5}% {rec_5}\nRSI: {round(rsi,1)}"
        return rec_h1, avg_p, det, decision
    else:
        det = f"H1:{p_h1}% {rec_h1} | 15m:{p_15}% {rec_15} | 5m:{p_5}% {rec_5}"
        return "NEUTRAL", 0, det, "❌ غير متطابق"

@bot.message_handler(commands=['start'])
def start(m):
    if m.from_user.id in authorized:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔥 البحث عن الفرصة الذهبية", callback_data="golden"))
        markup.add(types.InlineKeyboardButton("📊 فحص سوق واحد", callback_data="single"))
        bot.send_message(m.chat.id, "اهلا - اختر:", reply_markup=markup)
    else:
        bot.send_message(m.chat.id, "🔒 ارسل كلمة السر للدخول:")

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def check_pass(m):
    if m.text.strip() == PASSWORD:
        authorized.add(m.from_user.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔥 البحث عن الفرصة الذهبية", callback_data="golden"))
        markup.add(types.InlineKeyboardButton("📊 فحص سوق واحد", callback_data="single"))
        bot.send_message(m.chat.id, "✅ تم فتح البوت - حياك", reply_markup=markup)
    else:
        bot.send_message(m.chat.id, "❌ كلمة سر غلط")

@bot.callback_query_handler(func=lambda c: c.data=="single")
def single(call):
    if call.from_user.id not in authorized: return
    markup = types.InlineKeyboardMarkup(row_width=2)
    for name in MARKETS.keys():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"s_{MARKETS[name]}"))
    bot.send_message(call.message.chat.id, "اختر السوق:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("s_"))
def check_single(call):
    if call.from_user.id not in authorized: return
    sym = call.data[2:]
    bot.answer_callback_query(call.id, f"افحص {sym}...")
    d, p, det, dec = get_confluence_signal(sym)
    emoji = "🟢 BUY" if d=="BUY" else "🔴 SELL" if d=="SELL" else "⚪"
    bot.send_message(call.message.chat.id, f"{emoji} {sym} - {p}%\n{det}\n{dec}")

@bot.callback_query_handler(func=lambda c: c.data=="golden")
def golden(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id, "⏳ افحص 17 سوق...")
    loading = bot.send_message(call.message.chat.id, f"⏳ افحص {len(MARKETS)} سوق (30 ثانية)...")
    goldens = []
    start_t = time.time()
    for name, sym in MARKETS.items():
        try:
            d, p, det, dec = get_confluence_signal(sym)
            if "ذهبي" in dec:
                emoji = "🟢 BUY" if d=="BUY" else "🔴 SELL"
                goldens.append(f"{emoji} {name} - {p}%\n{det}\n{dec}\n")
        except: continue
    elapsed = round(time.time() - start_t, 1)
    if not goldens:
        bot.edit_message_text(f"❌ فحصت {len(MARKETS)} سوق في {elapsed}ث - لا يوجد ذهبي نظيف\nجرب بعد 5 دقايق", call.message.chat.id, loading.message_id)
    else:
        text = f"🔥🔥 {len(goldens)} فرص من {len(MARKETS)} سوق في {elapsed}ث 🔥🔥\n\n" + "\n".join(goldens)
        bot.edit_message_text(text, call.message.chat.id, loading.message_id)

app = Flask(__name__)
@app.route('/')
def home(): return "Bot Running"
def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
threading.Thread(target=run_flask, daemon=True).start()
bot.infinity_polling(timeout=60, long_polling_timeout=60)
