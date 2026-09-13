import os
import json
import time
import threading
import traceback
from datetime import datetime

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from tradingview_ta import TA_Handler, Interval

# =========================================================
# MAD TRADER - EDITED
# 5M -> 5M | 15M -> 15M
# 3 Buttons Only + All Flags
# =========================================================

TOKEN = os.environ.get("8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes")
PASSWORD = os.environ.get("7154")

if not TOKEN:
    raise RuntimeError("TOKEN is missing")
if not PASSWORD:
    raise RuntimeError("PASSWORD is missing")

bot = telebot.TeleBot(TOKEN, threaded=True)

USERS_FILE = "authorized_users.json"
STATS_FILE = "signal_stats.json"

# =========================================================
# MARKETS - مع كل الأعلام
# =========================================================
MARKETS = {
    "🇪🇺/🇺🇸 EUR/USD": "EURUSD",
    "🇬🇧/🇺🇸 GBP/USD": "GBPUSD",
    "🇺🇸/🇯🇵 USD/JPY": "USDJPY",
    "🇦🇺/🇺🇸 AUD/USD": "AUDUSD",
    "🇺🇸/🇨🇦 USD/CAD": "USDCAD",
    "🇪🇺/🇯🇵 EUR/JPY": "EURJPY",
    "🇨🇦/🇯🇵 CAD/JPY": "CADJPY",
    "🇪🇺/🇬🇧 EUR/GBP": "EURGBP",
    "🇦🇺/🇯🇵 AUD/JPY": "AUDJPY",
    "🇳🇿/🇺🇸 NZD/USD": "NZDUSD",
    "🇪🇺/🇨🇭 EUR/CHF": "EURCHF",
    "🇬🇧/🇯🇵 GBP/JPY": "GBPJPY",
    "🇦🇺/🇨🇦 AUD/CAD": "AUDCAD",
    "🇪🇺/🇦🇺 EUR/AUD": "EURAUD",
    "🇬🇧/🇨🇭 GBP/CHF": "GBPCHF",
    "🇺🇸/🇨🇭 USD/CHF": "USDCHF",
    "🇪🇺/🇨🇦 EUR/CAD": "EURCAD",
    "🇦🇺/🇨🇭 AUD/CHF": "AUDCHF",
    "🇬🇧/🇦🇺 GBP/AUD": "GBPAUD",
    "🇨🇦/🇨🇭 CAD/CHF": "CADCHF",
    "🇪🇺/🇳🇿 EUR/NZD": "EURNZD",
    "🇬🇧/🇳🇿 GBP/NZD": "GBPNZD",
}

TIMEFRAMES = {
    "5": {"tv_interval": Interval.INTERVAL_5_MINUTES, "trade_minutes": 5, "minimum_score": 78},
    "15": {"tv_interval": Interval.INTERVAL_15_MINUTES, "trade_minutes": 15, "minimum_score": 78}
}
DEFAULT_TIMEFRAME = "5"

last_signal = {}
scan_lock = threading.Lock()
user_timeframes = {}

# =========================================================
# FILE STORAGE
# =========================================================
def load_json(filename, default):
    try:
        if not os.path.exists(filename):
            return default
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(filename, data):
    temp = filename + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp, filename)

authorized = set(int(x) for x in load_json(USERS_FILE, []))
stats = load_json(STATS_FILE, {"signals": 0, "buy": 0, "sell": 0, "no_trade": 0})

# =========================================================
# UI - 3 أزرار أساسية فقط
# =========================================================
def main_menu():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🔎 فحص سوق واحد", callback_data="single"))
    kb.add(InlineKeyboardButton("🔥 أفضل فرصة", callback_data="best"))
    kb.add(InlineKeyboardButton("🌐 فحص جميع الأسواق", callback_data="all"))
    return kb

def market_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    for index, name in enumerate(MARKETS.keys()):
        kb.add(InlineKeyboardButton(name, callback_data=f"market:{index}"))
    kb.add(InlineKeyboardButton("🔙 رجوع", callback_data="home"))
    return kb

def get_market_by_index(index):
    names = list(MARKETS.keys())
    if index < 0 or index >= len(names):
        return None, None
    name = names[index]
    return name, MARKETS[name]

# =========================================================
# TRADINGVIEW ENGINE
# =========================================================
def get_tv_analysis(symbol, timeframe):
    config = TIMEFRAMES[timeframe]
    handler = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=config["tv_interval"], timeout=10)
    return handler.get_analysis()

# =========================================================
# SIGNAL ENGINE - نفس محركك الأصلي (قوي)
# =========================================================
def calculate_signal(symbol, timeframe):
    try:
        analysis = get_tv_analysis(symbol, timeframe)
        summary = analysis.summary
        indicators = analysis.indicators

        buy_votes = 0
        sell_votes = 0
        reasons_buy = []
        reasons_sell = []
        reasons_neutral = []

        buy = summary.get("BUY", 0)
        sell = summary.get("SELL", 0)
        neutral = summary.get("NEUTRAL", 0)
        total_summary = buy + sell + neutral
        if total_summary == 0:
            return None

        ema9 = indicators.get("EMA9")
        ema21 = indicators.get("EMA21")
        ema50 = indicators.get("EMA50")
        ema200 = indicators.get("EMA200")
        close = indicators.get("close")

        if ema9 is not None and ema21 is not None:
            if ema9 > ema21:
                buy_votes += 2
                reasons_buy.append("EMA9 > EMA21")
            elif ema9 < ema21:
                sell_votes += 2
                reasons_sell.append("EMA9 < EMA21")
            else:
                reasons_neutral.append("EMA9/EMA21 متقارب")

        if ema50 is not None and ema200 is not None:
            if ema50 > ema200:
                buy_votes += 2
                reasons_buy.append("Trend bullish")
            elif ema50 < ema200:
                sell_votes += 2
                reasons_sell.append("Trend bearish")

        if close is not None and ema50 is not None:
            if close > ema50:
                buy_votes += 1
                reasons_buy.append("السعر فوق EMA50")
            elif close < ema50:
                sell_votes += 1
                reasons_sell.append("السعر تحت EMA50")

        rsi = indicators.get("RSI")
        if rsi is not None:
            if 52 <= rsi <= 68:
                buy_votes += 2
                reasons_buy.append(f"RSI مناسب للشراء ({rsi:.1f})")
            elif 32 <= rsi <= 48:
                sell_votes += 2
                reasons_sell.append(f"RSI مناسب للبيع ({rsi:.1f})")
            elif rsi > 72:
                reasons_neutral.append(f"RSI مرتفع جدًا ({rsi:.1f})")
            elif rsi < 28:
                reasons_neutral.append(f"RSI منخفض جدًا ({rsi:.1f})")

        macd = indicators.get("MACD.macd")
        macd_signal = indicators.get("MACD.signal")
        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                buy_votes += 2
                reasons_buy.append("MACD bullish")
            elif macd < macd_signal:
                sell_votes += 2
                reasons_sell.append("MACD bearish")

        adx = indicators.get("ADX")
        if adx is not None:
            if adx >= 25:
                if buy_votes > sell_votes:
                    buy_votes += 2
                    reasons_buy.append(f"ADX قوي ({adx:.1f})")
                elif sell_votes > buy_votes:
                    sell_votes += 2
                    reasons_sell.append(f"ADX قوي ({adx:.1f})")
            else:
                reasons_neutral.append(f"الاتجاه ضعيف ADX={adx:.1f}")

        stoch_k = indicators.get("Stoch.K")
        stoch_d = indicators.get("Stoch.D")
        if stoch_k is not None and stoch_d is not None:
            if stoch_k > stoch_d and stoch_k < 80:
                buy_votes += 1
                reasons_buy.append("Stochastic bullish")
            elif stoch_k < stoch_d and stoch_k > 20:
                sell_votes += 1
                reasons_sell.append("Stochastic bearish")

        total_votes = buy_votes + sell_votes
        if total_votes < 7:
            return {"direction": "NO TRADE", "score": 0, "reasons": ["أدلة غير كافية"], "rsi": rsi, "adx": adx}

        if buy_votes > sell_votes:
            direction = "BUY"
            dominance = buy_votes / total_votes
            score = int(55 + (dominance * 45))
            reasons = reasons_buy
        elif sell_votes > buy_votes:
            direction = "SELL"
            dominance = sell_votes / total_votes
            score = int(55 + (dominance * 45))
            reasons = reasons_sell
        else:
            return {"direction": "NO TRADE", "score": 0, "reasons": ["المؤشرات متعادلة"], "rsi": rsi, "adx": adx}

        minimum = TIMEFRAMES[timeframe]["minimum_score"]
        if score < minimum:
            stats["no_trade"] += 1
            return {"direction": "NO TRADE", "score": score, "reasons": [f"القوة {score}/100 أقل من الحد {minimum}"], "rsi": rsi, "adx": adx}

        return {"direction": direction, "score": min(score, 99), "reasons": reasons[:5], "rsi": rsi, "adx": adx}

    except Exception as e:
        print("SIGNAL ERROR:", symbol, timeframe)
        print(traceback.format_exc())
        return None

def can_send_signal(symbol, timeframe, direction):
    key = f"{symbol}:{timeframe}"
    now = time.time()
    previous = last_signal.get(key)
    if previous:
        if previous["direction"] == direction and now - previous["time"] < 900:
            return False
    last_signal[key] = {"direction": direction, "time": now}
    return True

def format_signal(name, symbol, timeframe, result):
    direction = result["direction"]
    score = result["score"]
    minutes = TIMEFRAMES[timeframe]["trade_minutes"]

    if direction == "BUY":
        signal = "🟢 BUY ⬆️"
    elif direction == "SELL":
        signal = "🔴 SELL ⬇️"
    else:
        return f"{name}\n\n⚪ NO TRADE\n\n🎯 القوة: {score}/100\n⚠️ لا يوجد توافق كافٍ."

    text = f"🔥 <b>MAD TRADER</b>\n\n<b>{name}</b>\n\n{signal}\n\n🎯 <b>Confidence:</b> {score}/100\n⏱️ <b>الفريم:</b> {timeframe}M\n⌛ <b>مدة الصفقة:</b> {minutes} دقيقة\n\n🧠 <b>أسباب:</b>\n"
    for reason in result["reasons"]:
        text += f"✓ {reason}\n"
    if result["rsi"] is not None:
        text += f"\n📊 RSI: {result['rsi']:.1f}"
    if result["adx"] is not None:
        text += f"\n📈 ADX: {result['adx']:.1f}"
    text += "\n\n⚠️ تحليلية وليست ضمان ربح."
    return text

# =========================================================
# HANDLERS
# =========================================================
@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    if user_id not in authorized:
        bot.send_message(message.chat.id, "🔐 <b>MAD TRADER</b>\n\nأدخل رمز الدخول:", parse_mode="HTML")
        return
    tf = user_timeframes.get(user_id, DEFAULT_TIMEFRAME)
    bot.send_message(message.chat.id, f"🔥 <b>MAD TRADER</b>\n\nمحرك إشارات متعدد المؤشرات\n\n⏱️ الفريم الحالي: {tf}M → صفقة {tf} دقائق\n\n3 أزرار أساسية:", reply_markup=main_menu(), parse_mode="HTML")

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def password_check(message):
    if not message.text:
        return
    if message.text.strip() == PASSWORD:
        authorized.add(message.from_user.id)
        save_json(USERS_FILE, list(authorized))
        bot.send_message(message.chat.id, "✅ تم التحقق.\n\n🔥 أهلاً بك في MAD TRADER", reply_markup=main_menu())
    else:
        bot.send_message(message.chat.id, "❌ رمز غير صحيح.")

@bot.callback_query_handler(func=lambda c: c.data == "single")
def single_market(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text("📊 <b>اختر السوق:</b>", call.message.chat.id, call.message.message_id, reply_markup=market_menu(), parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("market:"))
def market_signal(call):
    try:
        bot.answer_callback_query(call.id)
        index = int(call.data.split(":")[1])
        name, symbol = get_market_by_index(index)
        if not name:
            return
        tf = user_timeframes.get(call.from_user.id, DEFAULT_TIMEFRAME)
        loading = bot.send_message(call.message.chat.id, f"🔎 <b>تحليل {name}</b>\n\n⏱️ الفريم: {tf}M\n🧠 جاري فحص المؤشرات...", parse_mode="HTML")
        result = calculate_signal(symbol, tf)
        if result is None:
            bot.edit_message_text(f"{name}\n\n⚠️ تعذر الحصول على بيانات موثوقة.\n❌ لا توجد إشارة.", call.message.chat.id, loading.message_id)
            return
        text = format_signal(name, symbol, tf, result)
        if result["direction"] in ("BUY", "SELL"):
            if can_send_signal(symbol, tf, result["direction"]):
                stats["signals"] += 1
                if result["direction"] == "BUY":
                    stats["buy"] += 1
                else:
                    stats["sell"] += 1
                save_json(STATS_FILE, stats)
        bot.edit_message_text(text, call.message.chat.id, loading.message_id, parse_mode="HTML")
    except Exception:
        print(traceback.format_exc())

@bot.callback_query_handler(func=lambda c: c.data == "best")
def best_opportunity(call):
    bot.answer_callback_query(call.id)
    tf = user_timeframes.get(call.from_user.id, DEFAULT_TIMEFRAME)
    loading = bot.send_message(call.message.chat.id, f"🔥 <b>MAD SCANNER</b>\n\n⏱️ الفريم: {tf}M\n🔎 يفحص 22 سوق مع الأعلام...", parse_mode="HTML")
    opportunities = []
    with scan_lock:
        for name, symbol in MARKETS.items():
            result = calculate_signal(symbol, tf)
            if result is None:
                continue
            if result["direction"] in ("BUY", "SELL"):
                opportunities.append((result["score"], name, symbol, result))
            time.sleep(0.1)
    opportunities.sort(key=lambda x: x[0], reverse=True)
    if not opportunities:
        bot.edit_message_text("🔥 <b>MAD SCANNER</b>\n\n⚪ لا توجد فرصة قوية حاليًا.\n\nالأفضل الانتظار.", call.message.chat.id, loading.message_id, parse_mode="HTML")
        return
    score, name, symbol, result = opportunities[0]
    text = f"🏆 <b>أفضل فرصة حاليًا</b>\n\n{format_signal(name, symbol, tf, result)}"
    bot.edit_message_text(text, call.message.chat.id, loading.message_id, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "all")
def all_markets(call):
    bot.answer_callback_query(call.id)
    tf = user_timeframes.get(call.from_user.id, DEFAULT_TIMEFRAME)
    loading = bot.send_message(call.message.chat.id, f"🌐 <b>MAD SCANNER</b>\n\n⏱️ {tf}M\n🔎 يفحص جميع الأسواق مع الأعلام...", parse_mode="HTML")
    results = []
    with scan_lock:
        for name, symbol in MARKETS.items():
            result = calculate_signal(symbol, tf)
            if result is not None:
                results.append((result["score"], name, result["direction"]))
            time.sleep(0.08)
    results.sort(key=lambda x: x[0], reverse=True)
    text = f"🌐 <b>MAD TRADER — ALL MARKETS مع الأعلام</b>\n\n⏱️ الفريم: {tf}M\n\n"
    for score, name, direction in results:
        if direction == "BUY":
            text += f"🟢 {name}\nBUY — {score}/100\n\n"
        elif direction == "SELL":
            text += f"🔴 {name}\nSELL — {score}/100\n\n"
        else:
            text += f"⚪ {name}\nNO TRADE\n\n"
    if len(text) > 3900:
        bot.edit_message_text(text[:3900], call.message.chat.id, loading.message_id, parse_mode="HTML")
        bot.send_message(call.message.chat.id, text[3900:], parse_mode="HTML")
    else:
        bot.edit_message_text(text, call.message.chat.id, loading.message_id, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "home")
def home(call):
    bot.answer_callback_query(call.id)
    tf = user_timeframes.get(call.from_user.id, DEFAULT_TIMEFRAME)
    bot.edit_message_text(f"🔥 <b>MAD TRADER</b>\n\n🧠 Multi-Indicator\n\n⏱️ النظام: {tf}M → صفقة {TIMEFRAMES[tf]['trade_minutes']} دقائق\n\n3 أزرار أساسية فقط:", call.message.chat.id, call.message.message_id, reply_markup=main_menu(), parse_mode="HTML")

# =========================================================
# FLASK
# =========================================================
app = Flask(__name__)

@app.route("/")
def root():
    return "MAD TRADER ONLINE - 3 Buttons + Flags"

@app.route("/health")
def health():
    return {"status": "online", "bot": "MAD TRADER", "time": datetime.utcnow().isoformat()}

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True)

threading.Thread(target=run_flask, daemon=True).start()

print("🔥 MAD TRADER STARTING - 3 Buttons + All Flags...")

while True:
    try:
        bot.remove_webhook()
        bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)
    except Exception as e:
        print("BOT ERROR:", e)
        traceback.print_exc()
        time.sleep(5)
