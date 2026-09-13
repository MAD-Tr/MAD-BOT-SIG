import os, time, threading, traceback
from datetime import datetime
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from tradingview_ta import TA_Handler, Interval

TOKEN = "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
PASSWORD = "7154"

bot = telebot.TeleBot(TOKEN, threaded=False)

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

authorized = set()
last_signal = {}
scan_lock = threading.Lock()
user_timeframes = {}

def main_menu_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🔎 فحص سوق واحد", callback_data="single"))
    kb.add(InlineKeyboardButton("🔥 أفضل فرصة", callback_data="best"))
    kb.add(InlineKeyboardButton("🌐 فحص جميع الأسواق", callback_data="all"))
    return kb

def market_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    for i, name in enumerate(MARKETS.keys()):
        kb.add(InlineKeyboardButton(name, callback_data=f"market:{i}"))
    kb.add(InlineKeyboardButton("🔙 رجوع", callback_data="home"))
    return kb

def get_market_by_index(index):
    names = list(MARKETS.keys())
    if 0 <= index < len(names):
        n = names[index]
        return n, MARKETS[n]
    return None, None

def get_tv_analysis(symbol, timeframe):
    cfg = TIMEFRAMES[timeframe]
    h = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=cfg["tv_interval"], timeout=10)
    return h.get_analysis()

def calculate_signal(symbol, timeframe):
    try:
        a = get_tv_analysis(symbol, timeframe)
        s = a.summary
        ind = a.indicators
        buy_v = 0; sell_v = 0; r_buy = []; r_sell = []
        if s.get("BUY",0)+s.get("SELL",0)+s.get("NEUTRAL",0)==0:
            return None
        ema9 = ind.get("EMA9"); ema21 = ind.get("EMA21"); ema50 = ind.get("EMA50"); ema200 = ind.get("EMA200"); close = ind.get("close")
        rsi = ind.get("RSI"); macd = ind.get("MACD.macd"); macd_sig = ind.get("MACD.signal"); adx = ind.get("ADX")
        stoch_k = ind.get("Stoch.K"); stoch_d = ind.get("Stoch.D")
        if ema9 and ema21:
            if ema9 > ema21: buy_v+=2; r_buy.append("EMA9 > EMA21")
            elif ema9 < ema21: sell_v+=2; r_sell.append("EMA9 < EMA21")
        if ema50 and ema200:
            if ema50 > ema200: buy_v+=2; r_buy.append("Trend bullish")
            elif ema50 < ema200: sell_v+=2; r_sell.append("Trend bearish")
        if close and ema50:
            if close > ema50: buy_v+=1; r_buy.append("السعر فوق EMA50")
            elif close < ema50: sell_v+=1; r_sell.append("السعر تحت EMA50")
        if rsi is not None:
            if 52 <= rsi <= 68: buy_v+=2; r_buy.append(f"RSI مناسب للشراء ({rsi:.1f})")
            elif 32 <= rsi <= 48: sell_v+=2; r_sell.append(f"RSI مناسب للبيع ({rsi:.1f})")
        if macd is not None and macd_sig is not None:
            if macd > macd_sig: buy_v+=2; r_buy.append("MACD bullish")
            elif macd < macd_sig: sell_v+=2; r_sell.append("MACD bearish")
        if adx is not None and adx >= 25:
            if buy_v > sell_v: buy_v+=2; r_buy.append(f"ADX قوي ({adx:.1f})")
            elif sell_v > buy_v: sell_v+=2; r_sell.append(f"ADX قوي ({adx:.1f})")
        if stoch_k is not None and stoch_d is not None:
            if stoch_k > stoch_d and stoch_k < 80: buy_v+=1; r_buy.append("Stochastic bullish")
            elif stoch_k < stoch_d and stoch_k > 20: sell_v+=1; r_sell.append("Stochastic bearish")
        total = buy_v + sell_v
        if total < 7:
            return {"direction":"NO TRADE","score":0,"reasons":["أدلة غير كافية"],"rsi":rsi,"adx":adx}
        if buy_v > sell_v:
            score = int(55 + (buy_v/total)*45)
            if score < 78: return {"direction":"NO TRADE","score":score,"reasons":[f"القوة {score}/100 أقل من الحد"],"rsi":rsi,"adx":adx}
            return {"direction":"BUY","score":min(score,99),"reasons":r_buy[:5],"rsi":rsi,"adx":adx}
        elif sell_v > buy_v:
            score = int(55 + (sell_v/total)*45)
            if score < 78: return {"direction":"NO TRADE","score":score,"reasons":[f"القوة {score}/100 أقل من الحد"],"rsi":rsi,"adx":adx}
            return {"direction":"SELL","score":min(score,99),"reasons":r_sell[:5],"rsi":rsi,"adx":adx}
        else:
            return {"direction":"NO TRADE","score":0,"reasons":["المؤشرات متعادلة"],"rsi":rsi,"adx":adx}
    except Exception:
        print(traceback.format_exc())
        return None

def format_signal(name, symbol, timeframe, result):
    d = result["direction"]; sc = result["score"]; mins = TIMEFRAMES[timeframe]["trade_minutes"]
    if d == "NO TRADE":
        return f"{name}\n\n⚪ NO TRADE\n🎯 القوة: {sc}/100"
    sig = "🟢 BUY ⬆️" if d=="BUY" else "🔴 SELL ⬇️"
    t = f"🔥 <b>MAD TRADER</b>\n\n<b>{name}</b>\n\n{sig}\n\n🎯 <b>Confidence:</b> {sc}/100\n⏱️ <b>الفريم:</b> {timeframe}M\n⌛ <b>الصفقة:</b> {mins} دقيقة\n\n🧠 <b>أسباب:</b>\n"
    for r in result["reasons"]: t+=f"✓ {r}\n"
    if result["rsi"] is not None: t+=f"\n📊 RSI: {result['rsi']:.1f}"
    if result["adx"] is not None: t+=f"\n📈 ADX: {result['adx']:.1f}"
    return t

def show_main_menu(chat_id):
    bot.send_message(chat_id, f"🔥 <b>MAD TRADER</b>\n\n🔐 الرقم السري: {PASSWORD}\n\n3 أزرار أساسية مع كل الأعلام:", reply_markup=main_menu_kb(), parse_mode="HTML")

@bot.message_handler(commands=['start'])
def start(m):
    if m.from_user.id not in authorized:
        bot.send_message(m.chat.id, "🔐 <b>أدخل الرقم السري:</b>\n\nالرقم هو: 7154", parse_mode="HTML")
        return
    bot.send_message(m.chat.id, "🔥 <b>MAD TRADER</b>\n\n3 أزرار أساسية + كل الأعلام:", reply_markup=main_menu_kb(), parse_mode="HTML")

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def check_pass(m):
    if not m.text: return
    if m.text.strip() == PASSWORD:
        authorized.add(m.from_user.id)
        bot.send_message(m.chat.id, "✅ تم فتح البوت", parse_mode="HTML")
        show_main_menu(m.chat.id)
    else:
        bot.send_message(m.chat.id, f"❌ غلط - الرقم الصحيح هو {PASSWORD}")

@bot.callback_query_handler(func=lambda c: c.data=="single")
def single_market(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    bot.edit_message_text("📊 <b>اختر السوق مع العلم:</b>", call.message.chat.id, call.message.message_id, reply_markup=market_menu(), parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("market:"))
def market_signal(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    idx = int(call.data.split(":")[1])
    name, sym = get_market_by_index(idx)
    if not name: return
    tf = user_timeframes.get(call.from_user.id, DEFAULT_TIMEFRAME)
    loading = bot.send_message(call.message.chat.id, f"🔎 <b>{name}</b>\n⏱️ {tf}M\n🧠 يفحص...", parse_mode="HTML")
    res = calculate_signal(sym, tf)
    if not res:
        bot.edit_message_text(f"{name}\n\n⚠️ لا توجد بيانات", call.message.chat.id, loading.message_id)
        return
    bot.edit_message_text(format_signal(name, sym, tf, res), call.message.chat.id, loading.message_id, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data=="best")
def best(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    tf = user_timeframes.get(call.from_user.id, DEFAULT_TIMEFRAME)
    loading = bot.send_message(call.message.chat.id, f"🔥 <b>MAD SCANNER</b>\n⏱️ {tf}M\n🔎 يفحص 22 سوق...", parse_mode="HTML")
    opps = []
    with scan_lock:
        for n,s in MARKETS.items():
            r = calculate_signal(s, tf)
            if r and r["direction"] in ("BUY","SELL"):
                opps.append((r["score"], n, s, r))
            time.sleep(0.1)
    opps.sort(key=lambda x: x[0], reverse=True)
    if not opps:
        bot.edit_message_text("⚪ لا توجد فرصة قوية حاليًا", call.message.chat.id, loading.message_id, parse_mode="HTML")
        return
    sc,n,s,r = opps[0]
    bot.edit_message_text(f"🏆 <b>أفضل فرصة</b>\n\n{format_signal(n,s,tf,r)}", call.message.chat.id, loading.message_id, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data=="all")
def all_markets(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    tf = user_timeframes.get(call.from_user.id, DEFAULT_TIMEFRAME)
    loading = bot.send_message(call.message.chat.id, f"🌐 <b>يفحص كل الأسواق مع الأعلام</b>\n⏱️ {tf}M", parse_mode="HTML")
    results = []
    with scan_lock:
        for n,s in MARKETS.items():
            r = calculate_signal(s, tf)
            if r:
                results.append((r["score"], n, r["direction"]))
            time.sleep(0.08)
    results.sort(key=lambda x: x[0], reverse=True)
    txt = f"🌐 <b>ALL MARKETS مع الأعلام</b> ⏱️ {tf}M\n\n"
    for sc,n,d in results:
        if d=="BUY": txt+=f"🟢 {n} BUY {sc}%\n\n"
        elif d=="SELL": txt+=f"🔴 {n} SELL {sc}%\n\n"
        else: txt+=f"⚪ {n} NO TRADE\n\n"
    if len(txt)>3900:
        bot.edit_message_text(txt[:3900], call.message.chat.id, loading.message_id, parse_mode="HTML")
        bot.send_message(call.message.chat.id, txt[3900:], parse_mode="HTML")
    else:
        bot.edit_message_text(txt, call.message.chat.id, loading.message_id, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data=="home")
def home(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    bot.edit_message_text(f"🔥 <b>MAD TRADER</b>\n\n3 أزرار فقط + كل الأعلام\n\n🔐 الرقم السري: {PASSWORD}", call.message.chat.id, call.message.message_id, reply_markup=main_menu_kb(), parse_mode="HTML")

app = Flask(__name__)
@app.route('/')
def root(): return f"MAD BOT - TOKEN OK - PASSWORD {PASSWORD} - 3 Buttons"
@app.route('/health')
def health(): return "OK"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))

threading.Thread(target=run_flask, daemon=True).start()
bot.remove_webhook()
time.sleep(2)

print(f"🔥 MAD TRADER STARTING - PASSWORD {PASSWORD} - 3 Buttons + Flags")

while True:
    try:
        bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)
