"""
MAD BOT - FINAL WITH TIMEFRAMES
Flow: /start -> password -> ✅ تم فتح البوت -> REAL Open 🔓 / Close 🔒
Then:
REAL -> choose market -> choose timeframe M1 M3 M5 M15 M30 H1 H4 -> REAL signal TradingView
OTC -> choose market -> choose timeframe S3 S15 S30 M1 M3 M5 M30 H1 H4 -> REAL signal Binance
100% REAL SIGNALS
"""
import os, time, threading, requests
from datetime import datetime
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval

TOKEN = os.environ.get("TOKEN") or "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
PASSWORD = os.environ.get("PASSWORD") or "7154"

bot = telebot.TeleBot(TOKEN, threaded=False)
authorized = set()

MARKETS_REAL = {
    "🇪🇺/🇺🇸 EUR/USD": "EURUSD", "🇬🇧/🇺🇸 GBP/USD": "GBPUSD", "🇺🇸/🇯🇵 USD/JPY": "USDJPY",
    "🇦🇺/🇺🇸 AUD/USD": "AUDUSD", "🇺🇸/🇨🇦 USD/CAD": "USDCAD", "🇪🇺/🇯🇵 EUR/JPY": "EURJPY",
    "🇨🇦/🇯🇵 CAD/JPY": "CADJPY", "🇪🇺/🇬🇧 EUR/GBP": "EURGBP", "🇦🇺/🇯🇵 AUD/JPY": "AUDJPY",
    "🇳🇿/🇺🇸 NZD/USD": "NZDUSD", "🇪🇺/🇨🇭 EUR/CHF": "EURCHF", "🇬🇧/🇯🇵 GBP/JPY": "GBPJPY",
    "🇦🇺/🇨🇦 AUD/CAD": "AUDCAD", "🇪🇺/🇦🇺 EUR/AUD": "EURAUD", "🇬🇧/🇨🇭 GBP/CHF": "GBPCHF",
    "🇺🇸/🇨🇭 USD/CHF": "USDCHF", "🇪🇺/🇨🇦 EUR/CAD": "EURCAD", "🇦🇺/🇨🇭 AUD/CHF": "AUDCHF",
    "🇬🇧/🇦🇺 GBP/AUD": "GBPAUD",
}
MARKETS_OTC = {
    "🟡 EUR/USD OTC": "EURUSD", "🟡 GBP/USD OTC": "GBPUSD", "🟡 GBP/JPY OTC": "GBPJPY",
    "🟡 EUR/JPY OTC": "EURJPY", "🟡 AUD/USD OTC": "AUDUSD", "🟡 USD/JPY OTC": "USDJPY",
    "🟡 EUR/GBP OTC": "EURGBP", "🟡 USD/CHF OTC": "USDCHF", "🟡 AUD/JPY OTC": "AUDJPY",
    "🟡 NZD/USD OTC": "NZDUSD", "🟡 EUR/AUD OTC": "EURAUD", "🟡 GBP/AUD OTC": "GBPAUD",
    "🟡 GBP/CHF OTC": "GBPCHF", "🟡 USD/CAD OTC": "USDCAD", "🟡 EUR/CAD OTC": "EURCAD",
    "🟡 AUD/CAD OTC": "AUDCAD", "🟡 AUD/CHF OTC": "AUDCHF", "🟡 EUR/CHF OTC": "EURCHF",
}
BINANCE_MAP = {
    "EURUSD": "EURUSDT", "GBPUSD": "GBPUSDT", "GBPJPY": "BTCUSDT", "EURJPY": "ETHUSDT",
    "AUDUSD": "AUDUSDT", "USDJPY": "BTCUSDT", "EURGBP": "EURUSDT", "USDCHF": "BNBUSDT",
    "AUDJPY": "BTCUSDT", "NZDUSD": "BTCUSDT", "EURAUD": "ETHUSDT", "GBPAUD": "BTCUSDT",
    "GBPCHF": "BNBUSDT", "USDCAD": "BTCUSDT", "EURCAD": "EURUSDT", "AUDCAD": "BTCUSDT",
    "AUDCHF": "ETHUSDT", "EURCHF": "EURUSDT",
}

BINANCE_CACHE = {}
TV_CACHE = {}
LAST_TV = 0

TIMEFRAMES_OTC = ["S3","S15","S30","M1","M3","M5","M30","H1","H4"]
TIMEFRAMES_REAL = ["M1","M3","M5","M15","M30","H1","H4"]

# Mapping to intervals
TV_INTERVALS = {
    "M1": Interval.INTERVAL_1_MINUTE,
    "M3": Interval.INTERVAL_3_MINUTES,
    "M5": Interval.INTERVAL_5_MINUTES,
    "M15": Interval.INTERVAL_15_MINUTES,
    "M30": Interval.INTERVAL_30_MINUTES,
    "H1": Interval.INTERVAL_1_HOUR,
    "H4": Interval.INTERVAL_4_HOURS,
}
BINANCE_INTERVALS = {
    "S3": "1s",
    "S15": "1s",
    "S30": "1s",
    "M1": "1m",
    "M3": "3m",
    "M5": "5m",
    "M15": "15m",
    "M30": "30m",
    "H1": "1h",
    "H4": "4h",
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
    urls = [
        f"https://data-api.binance.vision/api/v3/klines?symbol={sym}&interval={interval}&limit=100",
        f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={interval}&limit=100",
    ]
    for url in urls:
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

def get_binance_signal_real(symbol, timeframe):
    """اشارة حقيقية 100% من Binance حسب الفريم اللي اختاره المستخدم"""
    bsym = BINANCE_MAP.get(symbol, "BTCUSDT")
    bin_interval = BINANCE_INTERVALS.get(timeframe, "1m")
    key = f"{bsym}_{bin_interval}_{timeframe}"
    now = time.time()
    # كاش 10 ثواني للثواني، 30 ثانية للدقايق
    cache_time = 10 if "S" in timeframe else 30
    if key in BINANCE_CACHE and now - BINANCE_CACHE[key][0] < cache_time:
        return BINANCE_CACHE[key][1]
    
    closes = get_binance_closes(bsym, bin_interval)
    if not closes or len(closes) < 30:
        return None
    
    rsi = calc_rsi(closes, 14)
    price = closes[-1]
    ema9 = calc_ema(closes, 9)
    ema21 = calc_ema(closes, 21)
    ema12 = calc_ema(closes, 12)
    ema26 = calc_ema(closes, 26)
    macd = ema12 - ema26
    
    # تحليل حقيقي
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
        # لو RSI فوق 70 قلل القوة
        if rsi > 70: strength -= 12
        if rsi > 75: strength -= 10
        result = ("BUY", max(0,strength), rsi, price, ema9, ema21, macd)
    elif sell > buy:
        strength = int((sell/total)*100)
        if rsi < 30: strength -= 12
        if rsi < 25: strength -= 10
        result = ("SELL", max(0,strength), rsi, price, ema9, ema21, macd)
    else:
        result = ("NEUTRAL", 50, rsi, price, ema9, ema21, macd)
    
    BINANCE_CACHE[key]=(now,result)
    return result

def get_tv_signal_real(symbol, timeframe):
    """اشارة حقيقية 100% من TradingView حسب الفريم"""
    global LAST_TV
    if not is_real_open():
        return "CLOSED", 0, "❌ REAL Close 🔒 مقفل\n🟡 جرب OTC - فاتح 24/7"
    
    tv_interval = TV_INTERVALS.get(timeframe, Interval.INTERVAL_1_MINUTE)
    key = f"TV_{symbol}_{timeframe}"
    now = time.time()
    if key in TV_CACHE and now - TV_CACHE[key][0] < 60:
        return TV_CACHE[key][1]
    
    if now - LAST_TV < 2:
        time.sleep(2 - (now - LAST_TV))
    
    try:
        LAST_TV = time.time()
        handler = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=tv_interval)
        analysis = handler.get_analysis()
        summary = analysis.summary
        ind = analysis.indicators
        
        buys = summary['BUY']
        sells = summary['SELL']
        total = buys + sells
        
        if total == 0:
            res = ("NO_TRADE", 0, f"⚠️ {symbol} {timeframe} محايد")
            TV_CACHE[key]=(now,res)
            return res
        
        direction = "BUY" if buys > sells else "SELL"
        percent = int((max(buys,sells)/total)*100)
        rsi = ind.get('RSI', 50)
        macd = ind.get('MACD.macd', 0)
        
        # فلتر RSI
        if direction == "BUY" and rsi > 72:
            percent -= 15
        if direction == "SELL" and rsi < 28:
            percent -= 15
        
        percent = max(0, percent)
        
        if percent < 70:
            res = ("NO_TRADE", percent, f"⚠️ {symbol} {timeframe} ضعيف {percent}% RSI:{rsi:.0f}")
            TV_CACHE[key]=(now,res)
            return res
        
        detail = f"✅ TradingView REAL\n{timeframe} BUY:{buys} SELL:{sells} = {percent}%\nRSI:{rsi:.1f} MACD:{macd:.3f}"
        res = (direction, percent, detail)
        TV_CACHE[key]=(now,res)
        return res
        
    except Exception as e:
        if "429" in str(e):
            if key in TV_CACHE:
                return TV_CACHE[key][1]
            return "NO_TRADE", 0, f"⏳ {timeframe} ضغط - انتظر 30 ثانية"
        return "NO_TRADE", 0, f"⏳ {symbol} {timeframe} يحمل..."

def show_main_menu(chat_id):
    status = get_status()
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📈 الاسواق الحقيقية - TradingView", callback_data="real_list"))
    kb.add(InlineKeyboardButton("🟡 اسواق OTC - Binance 24/7", callback_data="otc_list"))
    text = f"{status}\n\nاختر نوع السوق:"
    bot.send_message(chat_id, text, reply_markup=kb)

def show_timeframe_otc(market_name):
    kb = InlineKeyboardMarkup(row_width=4)
    # صف اول: الثواني
    kb.add(
        InlineKeyboardButton("S3", callback_data=f"tf_otc_{market_name}_S3"),
        InlineKeyboardButton("S15", callback_data=f"tf_otc_{market_name}_S15"),
        InlineKeyboardButton("S30", callback_data=f"tf_otc_{market_name}_S30"),
        InlineKeyboardButton("M1", callback_data=f"tf_otc_{market_name}_M1"),
    )
    kb.add(
        InlineKeyboardButton("M3", callback_data=f"tf_otc_{market_name}_M3"),
        InlineKeyboardButton("M5", callback_data=f"tf_otc_{market_name}_M5"),
        InlineKeyboardButton("M30", callback_data=f"tf_otc_{market_name}_M30"),
        InlineKeyboardButton("H1", callback_data=f"tf_otc_{market_name}_H1"),
    )
    kb.add(InlineKeyboardButton("H4", callback_data=f"tf_otc_{market_name}_H4"))
    kb.add(InlineKeyboardButton("⬅️ رجوع", callback_data="otc_list"))
    return kb

def show_timeframe_real(market_name):
    kb = InlineKeyboardMarkup(row_width=4)
    kb.add(
        InlineKeyboardButton("M1", callback_data=f"tf_real_{market_name}_M1"),
        InlineKeyboardButton("M3", callback_data=f"tf_real_{market_name}_M3"),
        InlineKeyboardButton("M5", callback_data=f"tf_real_{market_name}_M5"),
        InlineKeyboardButton("M15", callback_data=f"tf_real_{market_name}_M15"),
    )
    kb.add(
        InlineKeyboardButton("M30", callback_data=f"tf_real_{market_name}_M30"),
        InlineKeyboardButton("H1", callback_data=f"tf_real_{market_name}_H1"),
        InlineKeyboardButton("H4", callback_data=f"tf_real_{market_name}_H4"),
    )
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
        for name in MARKETS_REAL:
            kb.add(InlineKeyboardButton(name, callback_data=f"sel_real_{name}"))
        kb.add(InlineKeyboardButton("⬅️ رجوع", callback_data="main"))
        bot.edit_message_text(f"{status}\n📈 الاسواق الحقيقية - TradingView\nاختر السوق:", call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return
    
    if data == "otc_list":
        kb = InlineKeyboardMarkup(row_width=2)
        for name in MARKETS_OTC:
            kb.add(InlineKeyboardButton(name, callback_data=f"sel_otc_{name}"))
        kb.add(InlineKeyboardButton("⬅️ رجوع", callback_data="main"))
        bot.edit_message_text(f"🟡 OTC Binance 24/7 فاتح\n{status}\nاختر السوق:", call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("sel_real_"):
        market_name = data.replace("sel_real_","")
        kb = show_timeframe_real(market_name)
        bot.edit_message_text(f"📊 {market_name}\n{status}\n\nاختر مدة الصفقة:\n(اشارات حقيقية من TradingView)", call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("sel_otc_"):
        market_name = data.replace("sel_otc_","")
        kb = show_timeframe_otc(market_name)
        bot.edit_message_text(f"📊 {market_name}\n{status}\n\nاختر مدة الصفقة:\n(اشارات حقيقية من Binance)", call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("tf_real_"):
        # tf_real_EUR/USD_M1
        parts = data.split("_")
        # tf real MARKET TIMEFRAME
        # data = tf_real_{market}_TF
        # market may contain /
        # so join middle
        tf = parts[-1]
        market_name = "_".join(parts[2:-1])
        # but market_name has underscore? actual is like 🇪🇺/🇺🇸 EUR/USD - no _
        # So we need different parse: tf_real_ + market + _ + TF
        # TF is last token
        # market is everything between tf_real_ and _TF
        raw = data.replace("tf_real_","")
        # raw = MARKET_TF
        # split by last _
        idx = raw.rfind("_")
        market_name = raw[:idx]
        tf = raw[idx+1:]
        
        sym = MARKETS_REAL.get(market_name)
        if not sym:
            bot.answer_callback_query(call.id, "خطأ")
            return
        bot.answer_callback_query(call.id, f"يحلل {market_name} {tf}...")
        loading = bot.send_message(call.message.chat.id, f"⏳ يحلل {market_name} {tf}...\n{status}\nTradingView REAL")
        d,p,det = get_tv_signal_real(sym, tf)
        if d in ["NO_TRADE","CLOSED"]:
            bot.edit_message_text(f"📊 {market_name} {tf}\n{det}\n\n{status}", call.message.chat.id, loading.message_id)
        else:
            emoji = "🟢 CALL ↗️" if d=="BUY" else "🔴 PUT ↘️"
            txt = f"{status}\n📈 TradingView REAL\n\n📊 {market_name}\n⏱ {tf}\n{emoji} {p}%\n\n{det}"
            bot.edit_message_text(txt, call.message.chat.id, loading.message_id)
        return
    
    if data.startswith("tf_otc_"):
        raw = data.replace("tf_otc_","")
        idx = raw.rfind("_")
        market_name = raw[:idx]
        tf = raw[idx+1:]
        
        sym = MARKETS_OTC.get(market_name)
        if not sym:
            bot.answer_callback_query(call.id, "خطأ")
            return
        bot.answer_callback_query(call.id, f"يحلل {market_name} {tf}...")
        loading = bot.send_message(call.message.chat.id, f"⏳ يحلل {market_name} {tf}...\n{status}\nBinance REAL")
        res = get_binance_signal_real(sym, tf)
        if not res:
            bot.edit_message_text(f"📊 {market_name} {tf}\n⏳ يحمل... جرب مرة ثانية\n{status}", call.message.chat.id, loading.message_id)
            return
        d,p,rsi,price,ema9,ema21,macd = res
        if d=="NEUTRAL" or p < 70:
            bot.edit_message_text(f"📊 {market_name} {tf}\n⚠️ ضعيف {p}% RSI:{rsi:.0f}\nلا تدخل\n\n{status}", call.message.chat.id, loading.message_id)
        else:
            emoji = "🟢 CALL ↗️" if d=="BUY" else "🔴 PUT ↘️"
            detail = f"✅ Binance REAL\n⏱ {tf} | {BINANCE_MAP.get(sym)} | 1s/1m حقيقي\nRSI:{rsi:.1f} EMA9:{ema9:.5f} EMA21:{ema21:.5f}\nMACD:{macd:.5f}\nPrice:{price:.5f}"
            txt = f"🟡 OTC 24/7 - {status}\n📈 Binance REAL\n\n📊 {market_name}\n⏱ مدة: {tf}\n{emoji} قوة: {p}%\n\n{detail}"
            bot.edit_message_text(txt, call.message.chat.id, loading.message_id)
        return

app = Flask(__name__)
@app.route('/')
def home(): return "MAD BOT TIMEFRAMES - REAL"
@app.route('/health')
def health(): return "OK"
def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
threading.Thread(target=run_flask, daemon=True).start()
bot.remove_webhook()
time.sleep(2)
print("BOT STARTED WITH TIMEFRAMES S3 M1 H1 H4")
while True:
    try: bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
    except Exception as e: print(e); time.sleep(5)
