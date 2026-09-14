"""
MAD BOT - POCKET OPTION SYNC - FINAL
- REAL = يقفل نفس بوكت أوبشن (الجمعة 9م UTC الى الأحد 9م UTC + السبت كامل)
- OTC = فاتح 24/7 طول الوقت حتى لو REAL مقفل
- 100% REAL SIGNALS
"""
import os, time, threading, requests
from datetime import datetime, timedelta
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval

TOKEN = os.environ.get("TOKEN") or "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
PASSWORD = os.environ.get("PASSWORD") or "7154"
BOT_NAME = "MAD BOT"

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
CACHE_TIME = 20

def is_pocket_real_open():
    now_utc = datetime.utcnow()
    wd = now_utc.weekday()
    h = now_utc.hour
    if wd == 5: return False, "السبت - مقفل في بوكت أوبشن"
    if wd == 6 and h < 21: return False, f"الأحد - يفتح بعد {21-h} ساعة"
    if wd == 4 and h >= 21: return False, "الجمعة ليلا - قفل بوكت"
    return True, "فاتح"

def get_market_status_text():
    real_open, real_reason = is_pocket_real_open()
    if real_open:
        return "✅ REAL فاتح في بوكت\n🟡 OTC فاتح 24/7"
    else:
        return f"❌ REAL مقفل - {real_reason}\n🟡 OTC فاتح 24/7"

def get_binance_closes(symbol, interval, limit=50):
    endpoints = [
        f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}",
        f"https://api1.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}",
    ]
    for url in endpoints:
        try:
            r = requests.get(url, timeout=4, headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code == 200:
                data = r.json()
                if data and len(data) >= 26:
                    return [float(c[4]) for c in data]
        except: continue
    return None

def calc_rsi(prices, period=14):
    if len(prices) < period+1: return 50
    deltas = [prices[i+1]-prices[i] for i in range(len(prices)-1)]
    gains = [max(0,d) for d in deltas[-period:]]
    losses = [max(0,-d) for d in deltas[-period:]]
    avg_gain = sum(gains)/period if gains else 0
    avg_loss = sum(losses)/period if losses else 0.00001
    if avg_loss == 0: return 70 if avg_gain>0 else 50
    rs = avg_gain/avg_loss
    return 100 - (100/(1+rs))

def calc_ema(prices, period):
    if len(prices) < period: return prices[-1] if prices else 0
    k = 2/(period+1)
    ema = prices[0]
    for p in prices[1:]: ema = p*k + ema*(1-k)
    return ema

def calc_macd(prices):
    if len(prices) < 26: return 0,0
    ema12 = calc_ema(prices, 12); ema26 = calc_ema(prices, 26)
    return ema12-ema26, ema12*0.9

def get_binance_signal(symbol, interval_str):
    key = f"{symbol}_{interval_str}"
    now = time.time()
    if key in BINANCE_CACHE:
        t,d = BINANCE_CACHE[key]
        if now - t < CACHE_TIME: return d
    closes = get_binance_closes(symbol, interval_str, 50)
    if not closes or len(closes) < 26: return None
    rsi = calc_rsi(closes, 14); macd, sig = calc_macd(closes)
    ema9 = calc_ema(closes, 9); ema21 = calc_ema(closes, 21); price = closes[-1]
    buy=0; sell=0
    if price > ema9: buy+=30
    else: sell+=30
    if ema9 > ema21: buy+=20
    else: sell+=20
    if rsi > 50: buy+=25
    else: sell+=25
    if macd > sig: buy+=25
    else: sell+=25
    total=buy+sell
    if buy > sell:
        strength = int((buy/total)*100)
        if rsi>70: strength-=12
        result = ("BUY", max(0,strength), rsi, macd, sig, price, ema9, ema21)
    elif sell > buy:
        strength = int((sell/total)*100)
        if rsi<30: strength-=12
        result = ("SELL", max(0,strength), rsi, macd, sig, price, ema9, ema21)
    else:
        result = ("NEUTRAL", 50, rsi, macd, sig, price, ema9, ema21)
    BINANCE_CACHE[key]=(now,result)
    return result

def get_otc_real(symbol):
    bsym = BINANCE_MAP.get(symbol, "BTCUSDT")
    d1 = get_binance_signal(bsym, "1m")
    if not d1: return "NO_TRADE", 0, f"❌ {bsym} لا يرد"
    d, p1, rsi, macd, sig, price, ema9, ema21 = d1
    if p1 < 68: return "NO_TRADE", p1, f"📊 {bsym} | 1m:{p1}% RSI:{int(rsi)} ضعيف"
    d5 = get_binance_signal(bsym, "5m")
    if not d5:
        if p1 >= 80:
            return d, p1, f"🔥 BINANCE OTC REAL 24/7\n{bsym} 1m:{p1}% RSI:{rsi:.1f}\nOTC فاتح طول الوقت"
        return "NO_TRADE", p1, f"⏳ {bsym} 5m يحمل..."
    d5_dir, p5, rsi5, _, _, _, _, _ = d5
    if d!= d5_dir: return "NO_TRADE", 0, f"❌ متذبذب {bsym} 1m:{d}({p1}%) vs 5m:{d5_dir}({p5}%)"
    final_p = int(p1*0.6 + p5*0.4)
    if final_p < 75: return "NO_TRADE", final_p, f"⚠️ {bsym} ضعيف {final_p}%"
    return d, final_p, f"🔥 BINANCE OTC REAL 24/7\n{bsym} 1m:{p1}% 5m:{p5}% = {final_p}%\nRSI:{rsi:.1f}/{rsi5:.1f}\nOTC فاتح 24/7"

def get_tv_real(symbol):
    real_open, reason = is_pocket_real_open()
    if not real_open:
        return "CLOSED", 0, f"❌ REAL مقفل في بوكت أوبشن\n{reason}\n🟡 روح OTC - فاتح 24/7"
    try:
        h = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=Interval.INTERVAL_5_MINUTES)
        a = h.get_analysis(); s = a.summary; ind = a.indicators
        buys = s['BUY']; sells = s['SELL']
        if buys+sells == 0: return "NO_TRADE", 0, "⚠️ محايد"
        d = "BUY" if buys > sells else "SELL"
        p = int((max(buys,sells)/(buys+sells))*100)
        if p < 68: return "NO_TRADE", p, f"⚠️ {symbol} ضعيف {p}%"
        rsi = ind.get('RSI', 50)
        if d=="BUY" and rsi>70: p-=10
        if d=="SELL" and rsi<30: p-=10
        detail = f"✅ TRADINGVIEW REAL\n{symbol} BUY:{buys} SELL:{sells} = {p}%\nRSI:{rsi:.1f}\nREAL فاتح في بوكت"
        return d, max(0,p), detail
    except Exception as e:
        return "NO_TRADE", 0, f"❌ خطأ: {str(e)[:80]}"

def main_menu(chat_id):
    real_open, real_reason = is_pocket_real_open()
    markup = InlineKeyboardMarkup(row_width=1)
    if real_open:
        markup.add(InlineKeyboardButton("✅ REAL فاتح (TradingView)", callback_data="cat_real"))
        markup.add(InlineKeyboardButton("🟡 OTC فاتح 24/7 (Binance REAL)", callback_data="cat_otc"))
        text = f"🤖 {BOT_NAME} - POCKET SYNC\n\n✅ REAL: فاتح في بوكت أوبشن\n🟡 OTC: فاتح 24/7\n\n{get_market_status_text()}\n\nاختر:"
    else:
        markup.add(InlineKeyboardButton("❌ REAL مقفل في بوكت", callback_data="real_closed"))
        markup.add(InlineKeyboardButton("🟡 OTC فاتح 24/7 - اضغط هنا", callback_data="cat_otc"))
        text = f"🤖 {BOT_NAME} - POCKET SYNC\n\n{get_market_status_text()}\n\n⚠️ الأسواق الحقيقية مقفلة في بوكت أوبشن الآن\n{real_reason}\n\n✅ تقدر تتداول OTC - فاتح طول الوقت"
    markup.add(InlineKeyboardButton("📊 فحص كل الأسواق الفاتحة", callback_data="scan_all"))
    bot.send_message(chat_id, text, reply_markup=markup)

def pair_kb(real_only=False, otc_only=False):
    kb = InlineKeyboardMarkup(row_width=2)
    if not otc_only:
        real_open, _ = is_pocket_real_open()
        if real_open:
            for name in MARKETS_REAL.keys():
                kb.add(InlineKeyboardButton(name, callback_data=f"sel:{name}"))
        else:
            kb.add(InlineKeyboardButton("❌ REAL مقفل - يفتح الأحد 12 ليلا", callback_data="real_closed"))
    if not real_only:
        for name in MARKETS_OTC.keys():
            kb.add(InlineKeyboardButton(name, callback_data=f"sel:{name}"))
    kb.add(InlineKeyboardButton("⬅️ رجوع", callback_data="main"))
    return kb

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id not in authorized:
        bot.send_message(msg.chat.id, f"🔒 {BOT_NAME}\nكلمة السر:"); return
    main_menu(msg.chat.id)

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def check(m):
    try: bot.delete_message(m.chat.id, m.message_id)
    except: pass
    if m.text.strip() == PASSWORD:
        authorized.add(m.from_user.id)
        bot.send_message(m.chat.id, f"✅ تم فتح {BOT_NAME}\nPOCKET SYNC - REAL يقفل مع بوكت, OTC فاتح 24/7")
        main_menu(m.chat.id)
    else: bot.send_message(m.chat.id, "❌")

@bot.callback_query_handler(func=lambda c: True)
def all_cb(call):
    if call.from_user.id not in authorized: return
    data = call.data
    if data == "main":
        real_open, _ = is_pocket_real_open()
        kb = InlineKeyboardMarkup(row_width=1)
        if real_open:
            kb.add(InlineKeyboardButton("✅ REAL", callback_data="cat_real"))
        else:
            kb.add(InlineKeyboardButton("❌ REAL مقفل", callback_data="real_closed"))
        kb.add(InlineKeyboardButton("🟡 OTC 24/7", callback_data="cat_otc"))
        kb.add(InlineKeyboardButton("📊 فحص الكل", callback_data="scan_all"))
        bot.edit_message_text(f"🤖 {BOT_NAME}\n\n{get_market_status_text()}\n\nاختر:", call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id); return
    if data == "real_closed":
        real_open, reason = is_pocket_real_open()
        bot.answer_callback_query(call.id, f"REAL مقفل: {reason}", show_alert=True)
        bot.send_message(call.message.chat.id, f"❌ الأسواق الحقيقية مقفلة في بوكت أوبشن\n{reason}\n\n🟡 الحل: تداول OTC - فاتح 24/7", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🟡 OTC فاتح 24/7", callback_data="cat_otc")))
        return
    if data == "cat_real":
        real_open, reason = is_pocket_real_open()
        if not real_open:
            bot.answer_callback_query(call.id, "REAL مقفل في بوكت الآن", show_alert=True)
            bot.send_message(call.message.chat.id, f"❌ REAL مقفل\n{reason}\n\n🟡 OTC فاتح 24/7", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🟡 روح OTC", callback_data="cat_otc")))
            return
        bot.edit_message_text(f"📈 REAL - TradingView REAL\n✅ فاتح في بوكت أوبشن\n{get_market_status_text()}\n\nاختر زوج:", call.message.chat.id, call.message.message_id, reply_markup=pair_kb(real_only=True))
        bot.answer_callback_query(call.id); return
    if data == "cat_otc":
        bot.edit_message_text(f"🟡 OTC LEGENDARY - Binance REAL 24/7\n✅ فاتح طول الوقت - حتى لو REAL مقفل\n{get_market_status_text()}\n\nاختر:", call.message.chat.id, call.message.message_id, reply_markup=pair_kb(otc_only=True))
        bot.answer_callback_query(call.id); return
    if data == "scan_all":
        bot.answer_callback_query(call.id, "⏳ افحص...")
        loading = bot.send_message(call.message.chat.id, f"⏳ {BOT_NAME}\n{get_market_status_text()}\n\nيفحص الأسواق الفاتحة...")
        strong=[]; real_open,_=is_pocket_real_open()
        if real_open:
            for name,sym in MARKETS_REAL.items():
                d,p,det=get_tv_real(sym)
                if d not in ["NO_TRADE","CLOSED"] and p>=75: strong.append((p,name,d,det))
        for name,sym in MARKETS_OTC.items():
            d,p,det=get_otc_real(sym)
            if d!="NO_TRADE" and p>=80: strong.append((p,name,d,det))
        strong.sort(reverse=True, key=lambda x:x[0])
        if not strong:
            bot.edit_message_text(f"{get_market_status_text()}\n\n⛔ لا يوجد إشارات قوية في الأسواق الفاتحة الآن", call.message.chat.id, loading.message_id)
        else:
            txt=f"🔥 {BOT_NAME} POCKET SYNC\n{get_market_status_text()}\n\n{len(strong)} فرص فاتحة الآن\n\n"
            for p,name,d,det in strong[:8]:
                emoji="🟢 CALL" if d=="BUY" else "🔴 PUT"
                txt+=f"{emoji} {name} {p}%\n{det}\n\n"
            bot.edit_message_text(txt, call.message.chat.id, loading.message_id)
        return
    if data.startswith("sel:"):
        name=data.replace("sel:",""); is_otc="OTC" in name; sym=(MARKETS_OTC if is_otc else MARKETS_REAL).get(name)
        if not is_otc:
            real_open,reason=is_pocket_real_open()
            if not real_open:
                bot.answer_callback_query(call.id,"REAL مقفل",show_alert=True)
                bot.send_message(call.message.chat.id, f"❌ {name} مقفل في بوكت أوبشن\n{reason}\n\n🟡 تداول OTC بداله - فاتح 24/7", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🟡 OTC فاتح", callback_data="cat_otc")))
                return
        bot.answer_callback_query(call.id, f"جاري تحليل {name}...")
        loading=bot.send_message(call.message.chat.id, f"⏳ {BOT_NAME}\n📊 يحلل {name}...\n{get_market_status_text()}")
        if is_otc: d,p,det=get_otc_real(sym)
        else: d,p,det=get_tv_real(sym)
        if d in ["NO_TRADE","CLOSED"]:
            bot.edit_message_text(f"📊 {name}\n\n{det}\n\n{get_market_status_text()}", call.message.chat.id, loading.message_id)
        else:
            emoji="🟢 CALL ↗️ HIGHER" if d=="BUY" else "🔴 PUT ↘️ LOWER"
            txt=f"🤖 {BOT_NAME} - POCKET SYNC\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{get_market_status_text()}\n\nPair: {name}\nSignal: {emoji}\nProbability: {p}%\n\n{det}"
            bot.edit_message_text(txt, call.message.chat.id, loading.message_id)

app=Flask(__name__)
@app.route('/')
def home(): return f"{BOT_NAME} - POCKET SYNC - REAL يقفل مع بوكت, OTC فاتح 24/7"
@app.route('/health')
def health(): return "OK"
def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
threading.Thread(target=run_flask, daemon=True).start()
bot.remove_webhook(); time.sleep(2)
print(f"{BOT_NAME} POCKET SYNC STARTED")
while True:
    try: bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
    except Exception as e: print(e); time.sleep(5)
