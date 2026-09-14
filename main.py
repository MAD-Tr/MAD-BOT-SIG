import os, time, threading, requests
from datetime import datetime
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# حاول استيراد tradingview - لو فشل لا يطيح البوت
try:
    from tradingview_ta import TA_Handler, Interval
    TV_AVAILABLE = True
    print("TradingView available")
except Exception as e:
    print(f"TradingView not available: {e}")
    TV_AVAILABLE = False
    TA_Handler = None
    Interval = None

TOKEN = os.environ.get("TOKEN") or "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
PASSWORD = os.environ.get("PASSWORD") or "7154"

bot = telebot.TeleBot(TOKEN, threaded=False)
authorized = set()

MARKETS_REAL = {
    "EURUSD": "EUR/USD", "GBPUSD": "GBP/USD", "USDJPY": "USD/JPY",
    "AUDUSD": "AUD/USD", "USDCAD": "USD/CAD", "EURJPY": "EUR/JPY",
    "CADJPY": "CAD/JPY", "EURGBP": "EUR/GBP", "AUDJPY": "AUD/JPY",
    "NZDUSD": "NZD/USD", "EURCHF": "EUR/CHF", "GBPJPY": "GBP/JPY",
    "AUDCAD": "AUD/CAD", "EURAUD": "EUR/AUD", "GBPCHF": "GBP/CHF",
    "USDCHF": "USD/CHF", "EURCAD": "EUR/CAD", "AUDCHF": "AUD/CHF",
    "GBPAUD": "GBP/AUD",
}
MARKETS_OTC = {
    "EURUSD_OTC": "EUR/USD OTC", "GBPUSD_OTC": "GBP/USD OTC", "GBPJPY_OTC": "GBP/JPY OTC",
    "EURJPY_OTC": "EUR/JPY OTC", "AUDUSD_OTC": "AUD/USD OTC", "USDJPY_OTC": "USD/JPY OTC",
    "EURGBP_OTC": "EUR/GBP OTC", "USDCHF_OTC": "USD/CHF OTC", "AUDJPY_OTC": "AUD/JPY OTC",
    "NZDUSD_OTC": "NZD/USD OTC", "EURAUD_OTC": "EUR/AUD OTC", "GBPAUD_OTC": "GBP/AUD OTC",
    "GBPCHF_OTC": "GBP/CHF OTC", "USDCAD_OTC": "USD/CAD OTC", "EURCAD_OTC": "EUR/CAD OTC",
    "AUDCAD_OTC": "AUD/CAD OTC", "AUDCHF_OTC": "AUD/CHF OTC", "EURCHF_OTC": "EUR/CHF OTC",
}

BINANCE_MAP = {
    "EUR/USD": "EURUSDT", "GBP/USD": "GBPUSDT", "GBP/JPY": "BTCUSDT", "EUR/JPY": "ETHUSDT",
    "AUD/USD": "AUDUSDT", "USD/JPY": "BTCUSDT", "EUR/GBP": "EURUSDT", "USD/CHF": "BNBUSDT",
    "AUD/JPY": "BTCUSDT", "NZD/USD": "BTCUSDT", "EUR/AUD": "ETHUSDT", "GBP/AUD": "BTCUSDT",
    "GBP/CHF": "BNBUSDT", "USD/CAD": "BTCUSDT", "EUR/CAD": "EURUSDT", "AUD/CAD": "BTCUSDT",
    "AUD/CHF": "ETHUSDT", "EUR/CHF": "EURUSDT",
    "EUR/USD OTC": "EURUSDT", "GBP/USD OTC": "GBPUSDT", "GBP/JPY OTC": "BTCUSDT",
    "EUR/JPY OTC": "ETHUSDT", "AUD/USD OTC": "AUDUSDT", "USD/JPY OTC": "BTCUSDT",
    "EUR/GBP OTC": "EURUSDT", "USD/CHF OTC": "BNBUSDT", "AUD/JPY OTC": "BTCUSDT",
    "NZD/USD OTC": "BTCUSDT", "EUR/AUD OTC": "ETHUSDT", "GBP/AUD OTC": "BTCUSDT",
    "GBP/CHF OTC": "BNBUSDT", "USD/CAD OTC": "BTCUSDT", "EUR/CAD OTC": "EURUSDT",
    "AUD/CAD OTC": "BTCUSDT", "AUD/CHF OTC": "ETHUSDT", "EUR/CHF OTC": "EURUSDT",
}

BINANCE_CACHE = {}
TV_CACHE = {}
LAST_TV = 0

if TV_AVAILABLE:
    TV_INTERVALS = {
        "M1": Interval.INTERVAL_1_MINUTE, "M3": Interval.INTERVAL_3_MINUTES,
        "M5": Interval.INTERVAL_5_MINUTES, "M15": Interval.INTERVAL_15_MINUTES,
        "M30": Interval.INTERVAL_30_MINUTES, "H1": Interval.INTERVAL_1_HOUR, "H4": Interval.INTERVAL_4_HOURS,
    }
else:
    TV_INTERVALS = {}

BINANCE_INTERVALS = {
    "S3": "1s", "S15": "1s", "S30": "1s",
    "M1": "1m", "M3": "3m", "M5": "5m", "M15": "15m", "M30": "30m", "H1": "1h", "H4": "4h",
}

def is_real_open():
    now = datetime.utcnow()
    wd = now.weekday()
    h = now.hour
    if wd == 5: return False
    if wd == 6 and h < 21: return False
    if wd == 4 and h >= 21: return False
    return True

def get_status():
    return "REAL Open 🔓" if is_real_open() else "REAL Close 🔒"

def get_binance_closes(sym, interval):
    for url in [
        f"https://data-api.binance.vision/api/v3/klines?symbol={sym}&interval={interval}&limit=100",
        f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={interval}&limit=100",
    ]:
        try:
            r = requests.get(url, timeout=5, headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code == 200:
                d = r.json()
                if d and len(d) >= 30:
                    return [float(c[4]) for c in d]
        except: continue
    return None

def calc_rsi(prices, period=14):
    if len(prices) < period+1: return 50
    deltas = [prices[i+1]-prices[i] for i in range(len(prices)-1)]
    gains = [max(0,d) for d in deltas[-period:]]
    losses = [max(0,-d) for d in deltas[-period:]]
    ag = sum(gains)/period if gains else 0
    al = sum(losses)/period if losses else 0.00001
    if al == 0: return 70 if ag>0 else 50
    rs = ag/al
    return 100 - (100/(1+rs))

def calc_ema(prices, p):
    if len(prices) < p: return prices[-1]
    k = 2/(p+1)
    ema = prices[0]
    for x in prices[1:]: ema = x*k + ema*(1-k)
    return ema

def get_binance_signal_real(symbol_display, timeframe):
    bsym = BINANCE_MAP.get(symbol_display, "BTCUSDT")
    bin_interval = BINANCE_INTERVALS.get(timeframe, "1m")
    key = f"{bsym}_{bin_interval}"
    now = time.time()
    cache_time = 10 if "S" in timeframe else 30
    if key in BINANCE_CACHE and now - BINANCE_CACHE[key][0] < cache_time:
        return BINANCE_CACHE[key][1]
    closes = get_binance_closes(bsym, bin_interval)
    if not closes: return None
    rsi = calc_rsi(closes, 14)
    price = closes[-1]
    ema9 = calc_ema(closes, 9)
    ema21 = calc_ema(closes, 21)
    ema12 = calc_ema(closes, 12)
    ema26 = calc_ema(closes, 26)
    macd = ema12 - ema26
    buy=0; sell=0
    if price > ema9: buy+=30
    else: sell+=30
    if ema9 > ema21: buy+=20
    else: sell+=20
    if rsi > 50: buy+=25
    else: sell+=25
    if macd > 0: buy+=25
    else: sell+=25
    total = buy+sell
    if buy > sell:
        strength = int((buy/total)*100)
        if rsi > 70: strength -= 12
        result = ("BUY", max(0,strength), rsi, price, ema9, ema21, macd)
    elif sell > buy:
        strength = int((sell/total)*100)
        if rsi < 30: strength -= 12
        result = ("SELL", max(0,strength), rsi, price, ema9, ema21, macd)
    else:
        result = ("NEUTRAL", 50, rsi, price, ema9, ema21, macd)
    BINANCE_CACHE[key]=(now,result)
    return result

def get_tv_signal_real(symbol_display, timeframe):
    if not TV_AVAILABLE:
        # لو TradingView مو متاح استخدم Binance بداله
        res = get_binance_signal_real(symbol_display, timeframe)
        if not res: return "NO_TRADE", 0, f"{symbol_display} {timeframe} يحمل..."
        d,p,rsi,price,ema9,ema21,macd = res
        if d=="NEUTRAL": return "NO_TRADE", p, f"{symbol_display} {timeframe} محايد {p}%"
        return d,p,f"Binance Fallback {timeframe} = {p}% RSI:{rsi:.1f} (TV غير متاح)"
    
    global LAST_TV
    if not is_real_open():
        return "CLOSED", 0, "REAL Close 🔒 مقفل"
    sym_code = symbol_display.replace("/","")
    tv_interval = TV_INTERVALS.get(timeframe, Interval.INTERVAL_1_MINUTE)
    key = f"TV_{sym_code}_{timeframe}"
    now = time.time()
    if key in TV_CACHE and now - TV_CACHE[key][0] < 60:
        return TV_CACHE[key][1]
    if now - LAST_TV < 2:
        time.sleep(2 - (now - LAST_TV))
    try:
        LAST_TV = time.time()
        h = TA_Handler(symbol=sym_code, screener="forex", exchange="FX", interval=tv_interval)
        a = h.get_analysis()
        s = a.summary
        ind = a.indicators
        buys = s['BUY']; sells = s['SELL']
        total = buys + sells
        if total == 0:
            res = ("NO_TRADE", 0, f"{symbol_display} {timeframe} محايد")
            TV_CACHE[key]=(now,res)
            return res
        d = "BUY" if buys > sells else "SELL"
        p = int((max(buys,sells)/total)*100)
        rsi = ind.get('RSI', 50)
        if d=="BUY" and rsi>72: p-=15
        if d=="SELL" and rsi<28: p-=15
        p = max(0,p)
        if p < 70:
            res = ("NO_TRADE", p, f"{symbol_display} {timeframe} ضعيف {p}% RSI:{rsi:.0f}")
            TV_CACHE[key]=(now,res)
            return res
        det = f"TradingView REAL {timeframe} BUY:{buys} SELL:{sells} = {p}% RSI:{rsi:.1f}"
        res = (d,p,det)
        TV_CACHE[key]=(now,res)
        return res
    except Exception as e:
        if "429" in str(e):
            if key in TV_CACHE: return TV_CACHE[key][1]
            return "NO_TRADE", 0, "ضغط سيرفر انتظر 30ث"
        return "NO_TRADE", 0, f"{symbol_display} يحمل... {e}"

def show_main_menu(chat_id):
    status = get_status()
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📈 الاسواق الحقيقية - TradingView", callback_data="real_list"))
    kb.add(InlineKeyboardButton("🟡 اسواق OTC - Binance 24/7", callback_data="otc_list"))
    bot.send_message(chat_id, f"{status}\n\nاختر نوع السوق:", reply_markup=kb)

def show_timeframe_otc(code):
    kb = InlineKeyboardMarkup(row_width=4)
    kb.add(InlineKeyboardButton("S3", callback_data=f"tf_o_{code}_S3"), InlineKeyboardButton("S15", callback_data=f"tf_o_{code}_S15"), InlineKeyboardButton("S30", callback_data=f"tf_o_{code}_S30"), InlineKeyboardButton("M1", callback_data=f"tf_o_{code}_M1"))
    kb.add(InlineKeyboardButton("M3", callback_data=f"tf_o_{code}_M3"), InlineKeyboardButton("M5", callback_data=f"tf_o_{code}_M5"), InlineKeyboardButton("M30", callback_data=f"tf_o_{code}_M30"), InlineKeyboardButton("H1", callback_data=f"tf_o_{code}_H1"))
    kb.add(InlineKeyboardButton("H4", callback_data=f"tf_o_{code}_H4"))
    kb.add(InlineKeyboardButton("⬅️ رجوع", callback_data="otc_list"))
    return kb

def show_timeframe_real(code):
    kb = InlineKeyboardMarkup(row_width=4)
    kb.add(InlineKeyboardButton("M1", callback_data=f"tf_r_{code}_M1"), InlineKeyboardButton("M3", callback_data=f"tf_r_{code}_M3"), InlineKeyboardButton("M5", callback_data=f"tf_r_{code}_M5"), InlineKeyboardButton("M15", callback_data=f"tf_r_{code}_M15"))
    kb.add(InlineKeyboardButton("M30", callback_data=f"tf_r_{code}_M30"), InlineKeyboardButton("H1", callback_data=f"tf_r_{code}_H1"), InlineKeyboardButton("H4", callback_data=f"tf_r_{code}_H4"))
    kb.add(InlineKeyboardButton("⬅️ رجوع", callback_data="real_list"))
    return kb

@bot.message_handler(commands=['start'])
def start_handler(message):
    if message.from_user.id not in authorized:
        bot.send_message(message.chat.id, "🔒 ارسل الرقم السري:")
        return
    bot.send_message(message.chat.id, "✅ تم فتح البوت")
    show_main_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def check_password(message):
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass
    if message.text.strip() == PASSWORD:
        authorized.add(message.from_user.id)
        bot.send_message(message.chat.id, "✅ تم فتح البوت")
        show_main_menu(message.chat.id)
    else:
        bot.send_message(message.chat.id, "❌ رقم سري خطأ")

@bot.callback_query_handler(func=lambda c: True)
def callback_handler(call):
    if call.from_user.id not in authorized: return
    data = call.data
    status = get_status()
    if data == "main":
        show_main_menu(call.message.chat.id)
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        bot.answer_callback_query(call.id)
        return
    if data == "real_list":
        if not is_real_open():
            bot.answer_callback_query(call.id, "REAL Close 🔒", show_alert=True)
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🟡 OTC فاتح 24/7", callback_data="otc_list"))
            bot.send_message(call.message.chat.id, f"❌ {status} مقفل\n🟡 OTC فاتح", reply_markup=kb)
            return
        kb = InlineKeyboardMarkup(row_width=2)
        for code, display in MARKETS_REAL.items():
            kb.add(InlineKeyboardButton(display, callback_data=f"sel_r_{code}"))
        kb.add(InlineKeyboardButton("⬅️ رجوع", callback_data="main"))
        try: bot.edit_message_text(f"{status}\n📈 الاسواق الحقيقية - TradingView\nاختر السوق:", call.message.chat.id, call.message.message_id, reply_markup=kb)
        except: bot.send_message(call.message.chat.id, f"{status}\n📈 الاسواق الحقيقية - TradingView\nاختر السوق:", reply_markup=kb)
        bot.answer_callback_query(call.id)
        return
    if data == "otc_list":
        kb = InlineKeyboardMarkup(row_width=2)
        for code, display in MARKETS_OTC.items():
            kb.add(InlineKeyboardButton(display, callback_data=f"sel_o_{code}"))
        kb.add(InlineKeyboardButton("⬅️ رجوع", callback_data="main"))
        try: bot.edit_message_text(f"🟡 OTC Binance 24/7 فاتح\n{status}\nاختر السوق:", call.message.chat.id, call.message.message_id, reply_markup=kb)
        except: bot.send_message(call.message.chat.id, f"🟡 OTC Binance 24/7 فاتح\n{status}\nاختر السوق:", reply_markup=kb)
        bot.answer_callback_query(call.id)
        return
    if data.startswith("sel_r_"):
        code = data.replace("sel_r_","")
        display = MARKETS_REAL.get(code, code)
        kb = show_timeframe_real(code)
        try: bot.edit_message_text(f"📊 {display}\n{status}\n\nاختر مدة الصفقة:\n(اشارات حقيقية TradingView)", call.message.chat.id, call.message.message_id, reply_markup=kb)
        except: bot.send_message(call.message.chat.id, f"📊 {display}\n{status}\n\nاختر مدة الصفقة:", reply_markup=kb)
        bot.answer_callback_query(call.id)
        return
    if data.startswith("sel_o_"):
        code = data.replace("sel_o_","")
        display = MARKETS_OTC.get(code, code)
        kb = show_timeframe_otc(code)
        try: bot.edit_message_text(f"📊 {display}\n{status}\n\nاختر مدة الصفقة:\n(اشارات حقيقية Binance)", call.message.chat.id, call.message.message_id, reply_markup=kb)
        except: bot.send_message(call.message.chat.id, f"📊 {display}\n{status}\n\nاختر مدة الصفقة:", reply_markup=kb)
        bot.answer_callback_query(call.id)
        return
    if data.startswith("tf_r_"):
        tmp = data.replace("tf_r_","")
        idx = tmp.rfind("_")
        code = tmp[:idx]
        tf = tmp[idx+1:]
        display = MARKETS_REAL.get(code, code)
        bot.answer_callback_query(call.id, f"يحلل {display} {tf}...")
        loading = bot.send_message(call.message.chat.id, f"⏳ يحلل {display} {tf}...\n{status}\nTradingView REAL")
        d,p,det = get_tv_signal_real(display, tf)
        if d in ["NO_TRADE","CLOSED"]:
            bot.edit_message_text(f"📊 {display} {tf}\n{det}\n\n{status}", call.message.chat.id, loading.message_id)
        else:
            emoji = "🟢 CALL ↗️" if d=="BUY" else "🔴 PUT ↘️"
            bot.edit_message_text(f"{status}\n📈 TradingView REAL\n\n📊 {display}\n⏱ {tf}\n{emoji} {p}%\n\n{det}", call.message.chat.id, loading.message_id)
        return
    if data.startswith("tf_o_"):
        tmp = data.replace("tf_o_","")
        idx = tmp.rfind("_")
        code = tmp[:idx]
        tf = tmp[idx+1:]
        display = MARKETS_OTC.get(code, code)
        bot.answer_callback_query(call.id, f"يحلل {display} {tf}...")
        loading = bot.send_message(call.message.chat.id, f"⏳ يحلل {display} {tf}...\n{status}\nBinance REAL")
        res = get_binance_signal_real(display, tf)
        if not res:
            bot.edit_message_text(f"📊 {display} {tf}\n⏳ يحمل...\n{status}", call.message.chat.id, loading.message_id)
            return
        d,p,rsi,price,ema9,ema21,macd = res
        if d=="NEUTRAL" or p < 70:
            bot.edit_message_text(f"📊 {display} {tf}\n⚠️ ضعيف {p}% RSI:{rsi:.0f}\nلا تدخل\n\n{status}", call.message.chat.id, loading.message_id)
        else:
            emoji = "🟢 CALL ↗️" if d=="BUY" else "🔴 PUT ↘️"
            detail = f"Binance REAL {tf} | {BINANCE_MAP.get(display)} | حقيقي\nRSI:{rsi:.1f} EMA9:{ema9:.5f} EMA21:{ema21:.5f}\nMACD:{macd:.5f} Price:{price:.5f}"
            bot.edit_message_text(f"🟡 OTC 24/7 - {status}\n📈 Binance REAL\n\n📊 {display}\n⏱ مدة: {tf}\n{emoji} قوة: {p}%\n\n{detail}", call.message.chat.id, loading.message_id)
        return

app = Flask(__name__)
@app.route('/')
def home(): return "MAD BOT FIXED - NO CRASH"
@app.route('/health')
def health(): return "OK"

def run_flask():
    try:
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    except Exception as e:
        print(f"Flask error: {e}")

threading.Thread(target=run_flask, daemon=True).start()

try:
    bot.remove_webhook()
    time.sleep(1)
    try:
        requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook?drop_pending_updates=True", timeout=5)
    except: pass
except Exception as e:
    print(f"webhook remove failed: {e}")

print("BOT STARTED - ANTI CRASH VERSION")
while True:
    try:
        bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
    except Exception as e:
        err = str(e)
        print(f"polling error: {err}")
        if "409" in err or "Conflict" in err:
            try:
                requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook?drop_pending_updates=True", timeout=5)
            except: pass
            time.sleep(10)
        else:
            time.sleep(5)
