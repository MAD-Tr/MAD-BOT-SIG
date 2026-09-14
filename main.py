import os, time, threading, requests
from datetime import datetime
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# yfinance للأسواق الحقيقية - يجيب أسعار فوركس حقيقية من ياهو
try:
    import yfinance as yf
    YF_AVAILABLE = True
    print("yfinance available - REAL forex enabled")
except Exception as e:
    print(f"yfinance not available: {e}")
    YF_AVAILABLE = False

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

YF_MAP = {
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "JPY=X",
    "AUD/USD": "AUDUSD=X", "USD/CAD": "CAD=X", "EUR/JPY": "EURJPY=X",
    "CAD/JPY": "CADJPY=X", "EUR/GBP": "EURGBP=X", "AUD/JPY": "AUDJPY=X",
    "NZD/USD": "NZDUSD=X", "EUR/CHF": "EURCHF=X", "GBP/JPY": "GBPJPY=X",
    "AUD/CAD": "AUDCAD=X", "EUR/AUD": "EURAUD=X", "GBP/CHF": "GBPCHF=X",
    "USD/CHF": "CHF=X", "EUR/CAD": "EURCAD=X", "AUD/CHF": "AUDCHF=X",
    "GBP/AUD": "GBPAUD=X",
}

BINANCE_MAP = {
    "EUR/USD": "EURUSDT", "GBP/USD": "GBPUSDT", "USD/JPY": "BTCUSDT",
    "AUD/USD": "AUDUSDT", "USD/CAD": "BTCUSDT", "EUR/JPY": "ETHUSDT",
    "CAD/JPY": "BTCUSDT", "EUR/GBP": "EURUSDT", "AUD/JPY": "BTCUSDT",
    "NZD/USD": "BTCUSDT", "EUR/CHF": "EURUSDT", "GBP/JPY": "BTCUSDT",
    "AUD/CAD": "BTCUSDT", "EUR/AUD": "ETHUSDT", "GBP/CHF": "BNBUSDT",
    "USD/CHF": "BNBUSDT", "EUR/CAD": "EURUSDT", "AUD/CHF": "ETHUSDT",
    "GBP/AUD": "BTCUSDT",
    "EUR/USD OTC": "EURUSDT", "GBP/USD OTC": "GBPUSDT", "GBP/JPY OTC": "BTCUSDT",
    "EUR/JPY OTC": "ETHUSDT", "AUD/USD OTC": "AUDUSDT", "USD/JPY OTC": "BTCUSDT",
    "EUR/GBP OTC": "EURUSDT", "USD/CHF OTC": "BNBUSDT", "AUD/JPY OTC": "BTCUSDT",
    "NZD/USD OTC": "BTCUSDT", "EUR/AUD OTC": "ETHUSDT", "GBP/AUD OTC": "BTCUSDT",
    "GBP/CHF OTC": "BNBUSDT", "USD/CAD OTC": "BTCUSDT", "EUR/CAD OTC": "EURUSDT",
    "AUD/CAD OTC": "BTCUSDT", "AUD/CHF OTC": "ETHUSDT", "EUR/CHF OTC": "EURUSDT",
}

BINANCE_INTERVALS = {
    "S3": "1s", "S15": "1s", "S30": "1s",
    "M1": "1m", "M3": "3m", "M5": "5m", "M15": "15m", "M30": "30m", "H1": "1h", "H4": "4h",
}

YF_INTERVALS = {
    "M1": "1m", "M3": "5m", "M5": "5m", "M15": "15m", "M30": "30m", "H1": "60m", "H4": "240m",
    "S3": "1m", "S15": "1m", "S30": "1m",
}

CACHE = {}

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

def get_yf_closes(yf_symbol, interval):
    if not YF_AVAILABLE:
        return None
    try:
        yf_interval = YF_INTERVALS.get(interval, "1m")
        ticker = yf.Ticker(yf_symbol)
        if "m" in yf_interval or yf_interval == "1m":
            df = ticker.history(period="2d", interval=yf_interval)
        else:
            df = ticker.history(period="5d", interval=yf_interval)
        if df is None or len(df) < 20:
            return None
        closes = df['Close'].tolist()
        return closes
    except Exception as e:
        print(f"yfinance error {yf_symbol} {interval}: {e}")
        return None

def get_real_signal(display_name, timeframe):
    key = f"REAL_{display_name}_{timeframe}"
    now = time.time()
    if key in CACHE and now - CACHE[key][0] < 60:
        return CACHE[key][1]

    closes = None
    source = ""

    if YF_AVAILABLE and display_name in YF_MAP:
        yf_sym = YF_MAP[display_name]
        closes = get_yf_closes(yf_sym, timeframe)
        if closes:
            source = f"Yahoo {yf_sym} {timeframe} حقيقي"

    if not closes:
        bsym = BINANCE_MAP.get(display_name, "EURUSDT")
        bin_interval = BINANCE_INTERVALS.get(timeframe, "1m")
        closes = get_binance_closes(bsym, bin_interval)
        source = f"Binance {bsym} {bin_interval} حقيقي"

    if not closes or len(closes) < 20:
        return None

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
        if rsi > 70: strength -= 10
        result = ("BUY", max(0,strength), rsi, price, ema9, ema21, macd, source, closes)
    elif sell > buy:
        strength = int((sell/total)*100)
        if rsi < 30: strength -= 10
        result = ("SELL", max(0,strength), rsi, price, ema9, ema21, macd, source, closes)
    else:
        result = ("NEUTRAL", 50, rsi, price, ema9, ema21, macd, source, closes)

    CACHE[key]=(now,result)
    return result

def show_main(chat_id):
    status = get_status()
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"📈 الاسواق الحقيقية - {status}", callback_data="real_list"))
    kb.add(InlineKeyboardButton("🟡 اسواق OTC - Binance 24/7", callback_data="otc_list"))
    bot.send_message(chat_id, f"{status}\n\nاختر نوع السوق:\nكل الاشارات حقيقية من Yahoo + Binance", reply_markup=kb)

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
def start_handler(m):
    if m.from_user.id not in authorized:
        bot.send_message(m.chat.id, "🔒 ارسل الرقم السري:")
        return
    bot.send_message(m.chat.id, "✅ تم فتح البوت")
    show_main(m.chat.id)

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def pwd(m):
    try: bot.delete_message(m.chat.id, m.message_id)
    except: pass
    if m.text.strip() == PASSWORD:
        authorized.add(m.from_user.id)
        bot.send_message(m.chat.id, "✅ تم فتح البوت")
        show_main(m.chat.id)
    else:
        bot.send_message(m.chat.id, "❌ رقم سري خطأ")

@bot.callback_query_handler(func=lambda c: True)
def cb(call):
    if call.from_user.id not in authorized: return
    data = call.data
    status = get_status()

    if data == "main":
        show_main(call.message.chat.id)
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
        try: bot.edit_message_text(f"{status}\n📈 الاسواق الحقيقية - Yahoo REAL\nاختر السوق:", call.message.chat.id, call.message.message_id, reply_markup=kb)
        except: bot.send_message(call.message.chat.id, f"{status}\n📈 الاسواق الحقيقية\nاختر:", reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data == "otc_list":
        kb = InlineKeyboardMarkup(row_width=2)
        for code, display in MARKETS_OTC.items():
            kb.add(InlineKeyboardButton(display, callback_data=f"sel_o_{code}"))
        kb.add(InlineKeyboardButton("⬅️ رجوع", callback_data="main"))
        try: bot.edit_message_text(f"🟡 OTC Binance 24/7 فاتح\n{status}\nاختر السوق:", call.message.chat.id, call.message.message_id, reply_markup=kb)
        except: bot.send_message(call.message.chat.id, f"🟡 OTC فاتح\n{status}\nاختر:", reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("sel_r_"):
        code = data.replace("sel_r_","")
        display = MARKETS_REAL.get(code, code)
        kb = show_timeframe_real(code)
        try: bot.edit_message_text(f"📊 {display}\n{status}\n\nاختر مدة الصفقة:\nاشارات حقيقية من Yahoo Finance", call.message.chat.id, call.message.message_id, reply_markup=kb)
        except: bot.send_message(call.message.chat.id, f"📊 {display}\n{status}\nاختر المدة:", reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("sel_o_"):
        code = data.replace("sel_o_","")
        display = MARKETS_OTC.get(code, code)
        kb = show_timeframe_otc(code)
        try: bot.edit_message_text(f"📊 {display}\n{status}\n\nاختر مدة الصفقة:\nاشارات حقيقية من Binance", call.message.chat.id, call.message.message_id, reply_markup=kb)
        except: bot.send_message(call.message.chat.id, f"📊 {display}\nاختر المدة:", reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("tf_r_"):
        tmp = data.replace("tf_r_","")
        idx = tmp.rfind("_")
        code = tmp[:idx]
        tf = tmp[idx+1:]
        display = MARKETS_REAL.get(code, code)
        bot.answer_callback_query(call.id, f"يحلل {display} {tf}...")
        loading = bot.send_message(call.message.chat.id, f"⏳ يحلل {display} {tf}...\n{status}\nYahoo Finance REAL")
        res = get_real_signal(display, tf)
        if not res:
            bot.edit_message_text(f"📊 {display} {tf}\n⏳ يحمل... جرب مرة ثانية\n{status}", call.message.chat.id, loading.message_id)
            return
        d,p,rsi,price,ema9,ema21,macd,source,closes = res
        if d=="NEUTRAL" or p < 70:
            bot.edit_message_text(f"📊 {display} {tf}\n⚠️ ضعيف {p}% RSI:{rsi:.0f}\nلا تدخل\n\n{source}\nPrice:{price:.5f}\n{status}", call.message.chat.id, loading.message_id)
        else:
            emoji = "🟢 CALL ↗️" if d=="BUY" else "🔴 PUT ↘️"
            txt = f"{status}\n📈 REAL - Yahoo Finance\n\n📊 {display}\n⏱ {tf}\n{emoji} قوة: {p}%\n\n{source}\nRSI:{rsi:.1f} EMA9:{ema9:.5f} EMA21:{ema21:.5f}\nMACD:{macd:.5f}\nPrice:{price:.5f}"
            bot.edit_message_text(txt, call.message.chat.id, loading.message_id)
        return

    if data.startswith("tf_o_"):
        tmp = data.replace("tf_o_","")
        idx = tmp.rfind("_")
        code = tmp[:idx]
        tf = tmp[idx+1:]
        display = MARKETS_OTC.get(code, code)
        bot.answer_callback_query(call.id, f"يحلل {display} {tf}...")
        loading = bot.send_message(call.message.chat.id, f"⏳ يحلل {display} {tf}...\n{status}\nBinance REAL")
        bsym = BINANCE_MAP.get(display, "EURUSDT")
        bin_interval = BINANCE_INTERVALS.get(tf, "1m")
        closes = get_binance_closes(bsym, bin_interval)
        if not closes:
            bot.edit_message_text(f"📊 {display} {tf}\n⏳ يحمل...\n{status}", call.message.chat.id, loading.message_id)
            return
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
            d="BUY"; p=int((buy/total)*100)
            if rsi>70: p-=10
        else:
            d="SELL"; p=int((sell/total)*100)
            if rsi<30: p-=10
        p=max(0,p)
        if p < 70:
            bot.edit_message_text(f"📊 {display} {tf}\n⚠️ ضعيف {p}% RSI:{rsi:.0f}\nلا تدخل\n{status}", call.message.chat.id, loading.message_id)
        else:
            emoji = "🟢 CALL ↗️" if d=="BUY" else "🔴 PUT ↘️"
            txt = f"🟡 OTC 24/7 - {status}\n📈 Binance REAL\n\n📊 {display}\n⏱ مدة: {tf}\n{emoji} قوة: {p}%\n\nBinance {bsym} {bin_interval} حقيقي\nRSI:{rsi:.1f} EMA9:{ema9:.5f}\nPrice:{price:.5f}"
            bot.edit_message_text(txt, call.message.chat.id, loading.message_id)
        return

app = Flask(__name__)
@app.route('/')
def home(): return "MAD BOT - REAL SIGNALS Yahoo+Binance - LIVE"
@app.route('/health')
def health(): return "OK"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

threading.Thread(target=run_flask, daemon=True).start()

try:
    bot.remove_webhook()
    time.sleep(1)
    requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook?drop_pending_updates=True", timeout=5)
except Exception as e:
    print(f"webhook error: {e}")

print("BOT STARTED WITH REAL SIGNALS")
while True:
    try:
        bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"poll error: {e}")
        time.sleep(5)
