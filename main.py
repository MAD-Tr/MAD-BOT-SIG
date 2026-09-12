import os
import time
import threading
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval
from datetime import datetime
import pytz

TOKEN = os.environ.get("8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes")
if not TOKEN:
    raise ValueError("❌ حط TOKEN في Environment Variables في Render")
PASSWORD = os.environ.get("PASSWORD") or "7154"
bot = telebot.TeleBot(TOKEN, threaded=False)

MARKETS = {
    "🇪🇺/🇺🇸 EUR/USD": "EURUSD", "🇬🇧/🇺🇸 GBP/USD": "GBPUSD", "🇺🇸/🇯🇵 USD/JPY": "USDJPY",
    "🇦🇺/🇺🇸 AUD/USD": "AUDUSD", "🇺🇸/🇨🇦 USD/CAD": "USDCAD", "🇪🇺/🇯🇵 EUR/JPY": "EURJPY",
    "🇨🇦/🇯🇵 CAD/JPY": "CADJPY", "🇪🇺/🇬🇧 EUR/GBP": "EURGBP", "🇦🇺/🇯🇵 AUD/JPY": "AUDJPY",
    "🇳🇿/🇺🇸 NZD/USD": "NZDUSD", "🇪🇺/🇨🇭 EUR/CHF": "EURCHF", "🇬🇧/🇯🇵 GBP/JPY": "GBPJPY",
}
MARKETS_OTC = {
    "🟡 EUR/USD OTC": "EURUSD", "🟡 GBP/USD OTC": "GBPUSD", "🟡 EUR/JPY OTC": "EURJPY",
}
MARKETS_MT5 = {
    "🏆 XAU/USD GOLD": "XAUUSD",
    "🥇 XAG/USD SILVER": "XAGUSD",
    "🇪🇺/🇺🇸 EUR/USD": "EURUSD", "🇬🇧/🇺🇸 GBP/USD": "GBPUSD", "🇺🇸/🇯🇵 USD/JPY": "USDJPY",
}

user_data = {}; last_request = {}; authorized = set()
user_messages_to_clean = {}; daily_trades = []
KSA_TZ = pytz.timezone("Asia/Riyadh")

def clean_old_signals(chat_id):
    if chat_id in user_messages_to_clean:
        for msg_id in user_messages_to_clean[chat_id]:
            try: bot.delete_message(chat_id, msg_id)
            except: pass
        user_messages_to_clean[chat_id] = []

def save_message_for_cleaning(chat_id, msg_id):
    if chat_id not in user_messages_to_clean: user_messages_to_clean[chat_id] = []
    user_messages_to_clean[chat_id].append(msg_id)

def get_tf_signal(symbol, interval):
    try:
        # للذهب نستخدم cfd
        screener = "cfd" if "XAU" in symbol or "XAG" in symbol else "forex"
        exchange = "OANDA" if "XAU" in symbol or "XAG" in symbol else "FX"
        h = TA_Handler(symbol=symbol, screener=screener, exchange=exchange, interval=interval)
        s = h.get_analysis().summary
        buys, sells = s['BUY'], s['SELL']
        if buys+sells == 0: return "NEUTRAL", 50
        direction = "BUY" if buys > sells else "SELL"
        percent = int((max(buys, sells) / (buys + sells)) * 100)
        return direction, percent
    except Exception as e:
        print(f"Error {symbol}: {e}")
        return "ERROR", 0

def get_confluence_signal(symbol):
    d5, p5 = get_tf_signal(symbol, Interval.INTERVAL_5_MINUTES)
    d15, p15 = get_tf_signal(symbol, Interval.INTERVAL_15_MINUTES)
    d1h, p1h = get_tf_signal(symbol, Interval.INTERVAL_1_HOUR)
    if d5 == d15 == d1h and d5!= "ERROR":
        base = int(p5*0.30 + p15*0.35 + p1h*0.35)
        diff = max(p5, p15, p1h) - min(p5, p15, p1h)
        if diff > 20: base -= 8
        elif diff > 12: base -= 4
        if min(p5, p15, p1h) < 65: base -= 8
        if base > 92: base = 92
        if base < 0: base = 0
        final = base
        if final >= 85: decision = "🔥🔥 ممتاز جدا - TOP ادخل 2% 🔥🔥"
        elif final >= 78: decision = "✅ ممتاز - ادخل 1.5%"
        elif final >= 70: decision = "✅ جيد - ادخل 1%"
        else: decision = "⚠️ متوسط - لا تدخل"
        return d5, final, f"H1:{p1h}% | 15m:{p15}% | 5m:{p5}%\n{decision}"
    return "NO_TRADE", 0, f"H1:{p1h}% {d1h} | 15m:{p15}% {d15} | 5m:{p5}% {d5}\n\n❌ متضارب"

def get_confluence_signal_otc_15s(symbol):
    d5, p5 = get_tf_signal(symbol, Interval.INTERVAL_5_MINUTES)
    d15, p15 = get_tf_signal(symbol, Interval.INTERVAL_15_MINUTES)
    d1h, p1h = get_tf_signal(symbol, Interval.INTERVAL_1_HOUR)
    if d5 == d15 == d1h and d5!= "ERROR":
        base = int(p5*0.30 + p15*0.35 + p1h*0.35)
        diff = max(p5, p15, p1h) - min(p5, p15, p1h)
        if diff > 20: base -= 8
        elif diff > 12: base -= 4
        if min(p5, p15, p1h) < 65: base -= 8
        if base > 92: base = 92
        if base < 0: base = 0
        final = base
        if final >= 85: decision = "🔥🔥 TOP جباره 15s ادخل 2% 🔥🔥"
        elif final >= 78: decision = "✅ ممتاز 15s - ادخل 1.5%"
        elif final >= 70: decision = "✅ جيد 15s - ادخل 1%"
        else: decision = "⚠️ متوسط - لا تدخل"
        return d5, final, f"H1:{p1h}% | 15m:{p15}% | 5m:{p5}%\n{decision}\n⏱️ المدة: 15 ثانية"
    return "NO_TRADE", 0, f"H1:{p1h}% {d1h} | 15m:{p15}% {d15} | 5m:{p5}% {d5}\n\n❌ متضارب"

def get_mt5_signal_3targets(symbol):
    d, p, details = get_confluence_signal(symbol)
    if d == "NO_TRADE": return d, p, details, None
    is_gold = "XAU" in symbol or "XAG" in symbol
    try:
        screener = "cfd" if is_gold else "forex"
        exchange = "OANDA" if is_gold else "FX"
        h = TA_Handler(symbol=symbol, screener=screener, exchange=exchange, interval=Interval.INTERVAL_1_HOUR)
        price = h.get_analysis().indicators.get('close', 0)
        if price == 0: price = 4348.0 if is_gold else 1.0850
    except:
        price = 4348.0 if is_gold else 1.0850
    if is_gold:
        if d == "BUY": sl = round(price - 13, 2); tp1 = round(price + 7, 2); tp2 = round(price + 14, 2); tp3 = round(price + 27, 2)
        else: sl = round(price + 13, 2); tp1 = round(price - 7, 2); tp2 = round(price - 14, 2); tp3 = round(price - 27, 2)
    else:
        if d == "BUY": sl = round(price - 0.0020, 5); tp1 = round(price + 0.0010, 5); tp2 = round(price + 0.0020, 5); tp3 = round(price + 0.0040, 5)
        else: sl = round(price + 0.0020, 5); tp1 = round(price - 0.0010, 5); tp2 = round(price - 0.0020, 5); tp3 = round(price - 0.0040, 5)
    levels = {"entry": round(price, 2) if is_gold else round(price, 5), "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3}
    return d, p, details, levels

def main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("💰 MT5 - 3 أهداف", callback_data="mode_mt5"), InlineKeyboardButton("📉 POCKET - فوركس", callback_data="mode_pocket"))
    markup.add(InlineKeyboardButton("🌙 OTC - 15s", callback_data="otc_menu"))
    bot.send_message(chat_id, "💰 اختر نوع التداول:\n\n💰 MT5 = ذهب + 3 أهداف + شات نظيف\n📉 POCKET = فوركس عادي", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id not in authorized:
        bot.send_message(msg.chat.id, "🔒 ارسل كلمة السر:"); return
    clean_old_signals(msg.chat.id); main_menu(msg.chat.id)

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def check_pass(m):
    if m.text.strip() == PASSWORD:
        authorized.add(m.from_user.id); bot.send_message(m.chat.id, "✅ تم فتح البوت"); main_menu(m.chat.id)
    else: bot.send_message(m.chat.id, "❌ كلمة سر غلط")

@bot.callback_query_handler(func=lambda c: c.data=="mode_mt5")
def mode_mt5(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id); clean_old_signals(call.message.chat.id)
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("🔥 فحص الكل - MT5", callback_data="golden_mt5"))
    for name in MARKETS_MT5: markup.add(InlineKeyboardButton(name, callback_data=f"market_mt5_{name}"))
    m = bot.send_message(call.message.chat.id, "💰 MT5 - اختر السوق (الذهب أول واحد):", reply_markup=markup)
    save_message_for_cleaning(call.message.chat.id, m.message_id)

@bot.callback_query_handler(func=lambda c: c.data=="mode_pocket")
def mode_pocket(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id); clean_old_signals(call.message.chat.id)
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("🔥 الفرصة الذهبية", callback_data="golden"))
    for name in MARKETS: markup.add(InlineKeyboardButton(name, callback_data=f"market_{name}"))
    m = bot.send_message(call.message.chat.id, "📉 POCKET - اختر سوق فوركس:", reply_markup=markup)
    save_message_for_cleaning(call.message.chat.id, m.message_id)

@bot.callback_query_handler(func=lambda c: c.data=="golden_mt5")
def golden_mt5(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id); clean_old_signals(call.message.chat.id)
    loading = bot.send_message(call.message.chat.id, f"⏳ افحص {len(MARKETS_MT5)} سوق MT5...")
    save_message_for_cleaning(call.message.chat.id, loading.message_id)
    goldens = []
    for name, sym in MARKETS_MT5.items():
        try:
            d, p, details, levels = get_mt5_signal_3targets(sym)
            if d!= "NO_TRADE" and p >= 70 and levels:
                emoji = "🟢 BUY" if d=="BUY" else "🔴 SELL"
                txt = f"{emoji} {name} - {p}%\nENTRY {levels['entry']} | SL {levels['sl']}\nTP1 {levels['tp1']} | TP2 {levels['tp2']} | TP3 {levels['tp3']}\n{details}\n"
                goldens.append((p, txt))
        except: continue
    goldens.sort(key=lambda x: x[0], reverse=True)
    if not goldens: bot.edit_message_text(f"❌ لا يوجد موثوق MT5 حاليا", call.message.chat.id, loading.message_id)
    else:
        text = f"🏆 أفضل صفقة MT5 {goldens[0][0]}% 🏆\n\n"
        for i, (p, detail) in enumerate(goldens[:5], 1): text += f"{i}. {detail}\n━━━━━━━━━━━━\n"
        bot.edit_message_text(text, call.message.chat.id, loading.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_mt5_"))
def choose_mt5(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    name = call.data.replace("market_mt5_", "")
    if name not in MARKETS_MT5: return
    symbol = MARKETS_MT5[name]
    clean_old_signals(call.message.chat.id)
    loading = bot.send_message(call.message.chat.id, f"⏳ جاري فحص {name} MT5...")
    save_message_for_cleaning(call.message.chat.id, loading.message_id)
    d, p, details, levels = get_mt5_signal_3targets(symbol)
    if d == "NO_TRADE": bot.edit_message_text(f"📊 {name}\n{details}", call.message.chat.id, loading.message_id)
    else:
        emoji = "🟢 BUY" if d=="BUY" else "🔴 SELL"
        text = f"💰 MT5 - {name} - {emoji}\n💪 {p}%\n{details}\n🎯 ENTRY: {levels['entry']}\n❌ SL: {levels['sl']}\n✅ TP1: {levels['tp1']} (50%)\n✅ TP2: {levels['tp2']} (30%)\n✅ TP3: {levels['tp3']} (20%)\n📱 للجوال: 0.01 - SL {levels['sl']} - TP {levels['tp1']}"
        bot.edit_message_text(text, call.message.chat.id, loading.message_id)

@bot.callback_query_handler(func=lambda c: c.data=="golden")
def golden(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id); loading = bot.send_message(call.message.chat.id, f"⏳ افحص {len(MARKETS)} سوق...")
    save_message_for_cleaning(call.message.chat.id, loading.message_id)
    goldens = []; start_t = time.time()
    for name, sym in MARKETS.items():
        try:
            d, p, details = get_confluence_signal(sym)
            if d!= "NO_TRADE" and p >= 70:
                emoji = "🟢 BUY" if d=="BUY" else "🔴 SELL"
                goldens.append((p, f"{emoji} {name} - {p}%\n{details}\n"))
        except: continue
    goldens.sort(key=lambda x: x[0], reverse=True)
    elapsed = round(time.time() - start_t, 1)
    if not goldens: bot.edit_message_text(f"❌ لا يوجد موثوق", call.message.chat.id, loading.message_id)
    else:
        text = f"🏆 أفضل صفقة {goldens[0][0]}% 🏆\n{goldens[0][1]}\n"; bot.edit_message_text(text, call.message.chat.id, loading.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_") and not c.data.startswith("market_mt5_") and not c.data.startswith("market_otc_"))
def choose_market(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    name = call.data.replace("market_", "")
    if name not in MARKETS: return
    user_data[call.from_user.id] = MARKETS[name], name
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔍 فحص شامل H1+15m+5m", callback_data="time_ALL"))
    m = bot.send_message(call.message.chat.id, f"اخترت {name}\nاختر نوع الفحص:", reply_markup=markup)
    save_message_for_cleaning(call.message.chat.id, m.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("time_"))
def choose_time(call):
    if call.from_user.id not in authorized: return
    mode = call.data.replace("time_", ""); symbol, name = user_data.get(call.from_user.id, (None, None))
    if not symbol: return
    loading = bot.send_message(call.message.chat.id, f"⏳ جاري فحص {name}...")
    save_message_for_cleaning(call.message.chat.id, loading.message_id)
    if mode == "ALL":
        direction, percent, details = get_confluence_signal(symbol)
        if direction == "NO_TRADE": bot.edit_message_text(f"📊 {name}\n{details}", call.message.chat.id, loading.message_id); return
        emoji = "🟢 BUY" if direction == "BUY" else "🔴 SELL"
        bot.edit_message_text(f"📊 {name}\n{emoji}\n💪 {percent}%\n\n{details}", call.message.chat.id, loading.message_id)

app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Live!"
def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
threading.Thread(target=run_flask, daemon=True).start()
bot.remove_webhook(); time.sleep(2)
while True:
    try: bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
    except Exception as e: print(f"Error: {e}"); time.sleep(5)
