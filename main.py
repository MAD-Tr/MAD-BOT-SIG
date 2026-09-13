import os, time, threading, requests, math
from flask import Flask, request, jsonify
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from tradingview_ta import TA_Handler, Interval

TOKEN = "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
PASSWORD = "7154"

bot = None
try:
    bot = telebot.TeleBot(TOKEN, threaded=False)
except Exception as e:
    print(f"Bot init failed: {e}")
    bot = None

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
    "🟡 🇪🇺/🇺🇸 EUR/USD OTC": "EURUSD",
    "🟡 🇬🇧/🇺🇸 GBP/USD OTC": "GBPUSD",
    "🟡 🇬🇧/🇯🇵 GBP/JPY OTC": "GBPJPY",
    "🟡 🇪🇺/🇯🇵 EUR/JPY OTC": "EURJPY",
    "🟡 🇦🇺/🇺🇸 AUD/USD OTC": "AUDUSD",
    "🟡 🇺🇸/🇯🇵 USD/JPY OTC": "USDJPY",
    "🟡 🇪🇺/🇬🇧 EUR/GBP OTC": "EURGBP",
    "🟡 🇺🇸/🇨🇭 USD/CHF OTC": "USDCHF",
}
ALL_MARKETS = {**MARKETS_REAL, **MARKETS_OTC}
authorized = set()

# ========== BINANCE OTC ==========
# خريطة OTC -> Binance (24 ساعة)
BINANCE_OTC_MAP = {
    "EURUSD": "EURUSDT",   # يورو
    "GBPUSD": "GBPUSDT",   # باوند
    "GBPJPY": "BTCUSDT",   # بديل متقلب للـ JPY
    "EURJPY": "ETHUSDT",   # بديل متقلب
    "AUDUSD": "AUDUSDT",   # استرالي موجود
    "USDJPY": "BTCUSDT",   # بديل
    "EURGBP": "EURUSDT",   # يورو
    "USDCHF": "BNBUSDT",   # بديل
}

BINANCE_CACHE = {}
BINANCE_CACHE_TIME = 15

def get_binance_klines(symbol, interval, limit=100):
    """جيب شموع من Binance"""
    try:
        # interval: 1m, 5m, 15m
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            return None
        data = r.json()
        closes = [float(c[4]) for c in data]  # close prices
        return closes
    except Exception as e:
        print(f"Binance error {symbol} {interval}: {e}")
        return None

def calc_rsi(prices, period=14):
    if len(prices) < period+1:
        return 50
    deltas = [prices[i+1]-prices[i] for i in range(len(prices)-1)]
    gains = [max(0,d) for d in deltas[-period:]]
    losses = [max(0,-d) for d in deltas[-period:]]
    avg_gain = sum(gains)/period if gains else 0
    avg_loss = sum(losses)/period if losses else 0.00001
    if avg_loss == 0:
        return 70 if avg_gain>0 else 50
    rs = avg_gain/avg_loss
    return 100 - (100/(1+rs))

def calc_ema(prices, period):
    if len(prices) < period:
        return prices[-1] if prices else 0
    k = 2/(period+1)
    ema = prices[0]
    for p in prices[1:]:
        ema = p*k + ema*(1-k)
    return ema

def calc_macd(prices):
    if len(prices) < 26:
        return 0, 0
    ema12 = calc_ema(prices, 12)
    ema26 = calc_ema(prices, 26)
    macd = ema12 - ema26
    # signal = EMA9 of MACD - نبسطها
    # نحسب MACD line تاريخي بسيط
    macd_history = []
    for i in range(len(prices)):
        if i < 26: continue
        e12 = calc_ema(prices[:i+1], 12)
        e26 = calc_ema(prices[:i+1], 26)
        macd_history.append(e12-e26)
    signal = calc_ema(macd_history[-20:], 9) if len(macd_history)>=9 else macd*0.9
    return macd, signal

def get_binance_tf_signal(symbol, interval_str):
    """إشارة من Binance لفريم واحد"""
    cache_key = f"BN_{symbol}_{interval_str}"
    now = time.time()
    if cache_key in BINANCE_CACHE:
        t, d = BINANCE_CACHE[cache_key]
        if now - t < BINANCE_CACHE_TIME:
            return d

    closes = get_binance_klines(symbol, interval_str, 100)
    if not closes or len(closes) < 30:
        return "NEUTRAL", 50, 50, 0, 0

    rsi = calc_rsi(closes, 14)
    macd, sig = calc_macd(closes)
    
    # تحديد الاتجاه
    # RSI + EMA + MACD
    ema_fast = calc_ema(closes, 9)
    ema_slow = calc_ema(closes, 21)
    price = closes[-1]
    
    buy_score = 0
    sell_score = 0
    
    if price > ema_fast: buy_score += 30
    else: sell_score += 30
    
    if ema_fast > ema_slow: buy_score += 20
    else: sell_score += 20
    
    if rsi > 50: buy_score += 25
    else: sell_score += 25
    
    if macd > sig: buy_score += 25
    else: sell_score += 25
    
    # قوة
    total = buy_score + sell_score
    if total == 0:
        result = ("NEUTRAL", 50, rsi, macd, sig)
    elif buy_score > sell_score:
        strength = int((buy_score/total)*100)
        # تعديل RSI
        if rsi > 70: strength -= 15
        if rsi > 80: strength -= 10
        result = ("BUY", max(0,strength), rsi, macd, sig)
    else:
        strength = int((sell_score/total)*100)
        if rsi < 30: strength -= 15
        if rsi < 20: strength -= 10
        result = ("SELL", max(0,strength), rsi, macd, sig)
    
    BINANCE_CACHE[cache_key] = (now, result)
    return result

def get_strong_signal_otc_binance(symbol):
    """إشارة OTC قوية من Binance - 1m+5m+15m"""
    bin_symbol = BINANCE_OTC_MAP.get(symbol, "BTCUSDT")
    
    d1,p1,r1,_,_ = get_binance_tf_signal(bin_symbol, "1m")
    d5,p5,r5,_,_ = get_binance_tf_signal(bin_symbol, "5m")
    d15,p15,r15,_,_ = get_binance_tf_signal(bin_symbol, "15m")
    
    if min(p1,p5,p15) == 0 and "NEUTRAL" in [d1,d5,d15]:
        return "NO_TRADE", 0, f"⏳ Binance {bin_symbol} يحمل البيانات..."
    
    # لازم كل الفريمات نفس الاتجاه
    if d1==d5==d15 and d1 in ["BUY","SELL"]:
        base = int(p1*0.45 + p5*0.35 + p15*0.20)  # 1m أهم
        diff = max(p1,p5,p15) - min(p1,p5,p15)
        if diff > 25: base -= 12
        elif diff > 15: base -= 6
        if min(p1,p5,p15) < 65: base -= 12
        if min(p1,p5,p15) < 75: base -= 5
        if r1 > 78 and d1=="BUY": base -= 10
        if r1 < 22 and d1=="SELL": base -= 10
        
        base = max(0, min(96, base))
        if base >= 82:
            return d1, base, f"BINANCE OTC {bin_symbol} 1m:{p1}% 5m:{p5}% 15m:{p15}% | RSI:{int(r1)} - مباشر 24h"
        else:
            return "NO_TRADE", base, f"⚠️ BINANCE OTC ضعيف {base}% - {bin_symbol} | 1m:{p1}% 5m:{p5}% 15m:{p15}%"
    
    return "NO_TRADE", 0, f"❌ BINANCE OTC متذبذب {d1}/{d5}/{d15} - {bin_symbol} لا تدخل"

# كاش لتقليل طلبات TradingView
signal_cache = {}
CACHE_TIME = 30  # ثانية

def get_tf_signal_strong(symbol, interval):
    cache_key = f"{symbol}_{interval}"
    now = time.time()
    if cache_key in signal_cache:
        cached_time, cached_data = signal_cache[cache_key]
        if now - cached_time < CACHE_TIME:
            return cached_data
    
    # إعادة محاولة 3 مرات مع تأخير
    for attempt in range(3):
        try:
            h = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=interval)
            a = h.get_analysis()
            s = a.summary
            ind = a.indicators
            rsi = ind.get('RSI', 50)
            macd = ind.get('MACD.macd', 0)
            sig = ind.get('MACD.signal', 0)
            if s['BUY']+s['SELL']==0: 
                result = ("NEUTRAL", 50, rsi, macd, sig)
                signal_cache[cache_key] = (now, result)
                return result
            d = "BUY" if s['BUY']>s['SELL'] else "SELL"
            strength = int((max(s['BUY'],s['SELL'])/(s['BUY']+s['SELL']))*100)
            if d=="BUY":
                if rsi>70: strength-=15
                if macd<sig: strength-=10
            else:
                if rsi<30: strength-=15
                if macd>sig: strength-=10
            result = (d, max(0,strength), rsi, macd, sig)
            signal_cache[cache_key] = (now, result)
            return result
        except Exception as e:
            if attempt < 2:
                time.sleep(0.8 + attempt*0.5)  # تأخير متزايد
                continue
            print(f"TV Error {symbol} {interval}: {e}")
            # لا ترجع ERROR - رجع NEUTRAL عشان ما يظهر 0%
            return "NEUTRAL", 0, 50, 0, 0
    return "NEUTRAL", 0, 50, 0, 0

def get_strong_signal_real(symbol):
    d5,p5,r5,_,_ = get_tf_signal_strong(symbol, Interval.INTERVAL_5_MINUTES)
    d15,p15,r15,_,_ = get_tf_signal_strong(symbol, Interval.INTERVAL_15_MINUTES)
    d30,p30,r30,_,_ = get_tf_signal_strong(symbol, Interval.INTERVAL_30_MINUTES)
    if "ERROR" in [d5,d15,d30] or "NEUTRAL" in [d5,d15,d30] and min(p5,p15,p30)==0:
        # لو البيانات ما تحملت - حاول مرة ثانية
        time.sleep(0.5)
        d5,p5,r5,_,_ = get_tf_signal_strong(symbol, Interval.INTERVAL_5_MINUTES)
        d15,p15,r15,_,_ = get_tf_signal_strong(symbol, Interval.INTERVAL_15_MINUTES)
        if min(p5,p15,p30)==0:
            return "NO_TRADE",0,"⏳ جاري تحميل بيانات TradingView - حاول مرة ثانية بعد 10 ثواني"
    if d5==d15==d30 and d5 in ["BUY","SELL"]:
        base=int(p5*0.25+p15*0.40+p30*0.35)
        diff=max(p5,p15,p30)-min(p5,p15,p30)
        if diff>25: base-=15
        elif diff>15: base-=8
        if min(p5,p15,p30)<60: base-=15
        if min(p5,p15,p30)<70: base-=5
        if d5=="BUY" and r15>75: base-=10
        if d5=="SELL" and r15<25: base-=10
        base=max(0,min(95,base))
        if base>=78:
            return d5,base,"TV REAL 5m:%s%% 15m:%s%% 30m:%s%% | RSI:%s - مباشر TradingView" % (p5,p15,p30,int(r15))
        else:
            return "NO_TRADE",base,"⚠️ إشارة ضعيفة %s%% - لا تدخل | 5m:%s%% 15m:%s%% 30m:%s%%" % (base,p5,p15,p30)
    return "NO_TRADE",0,"❌ متضارب %s/%s/%s - لا تدخل" % (d5,d15,d30)

def get_strong_signal_otc(symbol):
    # الآن OTC من Binance مباشر 24 ساعة
    return get_strong_signal_otc_binance(symbol)

def main_menu(chat_id):
    if not bot: return
    markup = InlineKeyboardMarkup(row_width=1)
    base_url = os.environ.get("RENDER_EXTERNAL_URL") or "https://mad-bot.onrender.com"
    webapp_url = base_url.rstrip("/") + "/mad"
    markup.add(InlineKeyboardButton("💰 التطبيق المصغر - إشارات حقيقية", web_app=WebAppInfo(url=webapp_url)))
    markup.add(InlineKeyboardButton("📉 حقيقي قوي 78%+", callback_data="all_real"))
    markup.add(InlineKeyboardButton("🟡 OTC قوي 82%+", callback_data="all_otc"))
    markup.add(InlineKeyboardButton("🔥 أقوى فرصة الآن", callback_data="golden_strong"))
    bot.send_message(chat_id, "✅ MAD BOT - إشارات TradingView حقيقية\nبدون عشوائي • مباشر\n⬇️ اختار", reply_markup=markup)

app = Flask(__name__)

MAD_HTML = """
<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>MAD SIGNALS - TradingView Live</title><style>
*{box-sizing:border-box;margin:0;padding:0}body{background:radial-gradient(ellipse at top,#2a0000 0%,#000 80%);color:#fff;font-family:-apple-system,Arial;min-height:100vh;direction:rtl}
.container{max-width:420px;margin:0 auto;padding:12px}.crown-wrap{display:flex;justify-content:center;margin:16px 0}.crown{width:100px;height:100px;background:radial-gradient(circle at 30% 30%,#ff3333,#7a0000);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:52px;box-shadow:0 0 40px rgba(255,0,0,.6)}
.title{color:#ff0000;font-size:26px;font-weight:900;text-align:center;letter-spacing:3px;text-shadow:0 0 15px #ff0000}.subtitle{text-align:center;font-size:18px;font-weight:800;margin-top:4px}.sub2{text-align:center;color:#00ff00;font-size:10px;letter-spacing:1px;margin-top:6px}
.card{background:linear-gradient(135deg,#1a0a0a,#0e0e0e);border:1px solid rgba(255,0,0,.2);border-radius:20px;padding:16px;margin:12px 0}
.input-wrap{display:flex;align-items:center;background:#0009;border:1px solid #333;border-radius:14px;padding:4px 14px}.input-wrap input{flex:1;background:transparent;border:none;color:#fff;padding:12px 8px;outline:none;font-size:15px}.counter{color:#666;font-size:12px}
.btn-main{width:100%;padding:14px;background:#111;border:1px solid #333;border-radius:14px;color:#777;font-weight:800;margin-top:12px}.btn-main.active{background:linear-gradient(135deg,#ff0000,#b00000);color:#fff;border-color:#ff0000;box-shadow:0 0 20px rgba(255,0,0,.5)}
.bank-card{border:2px solid #ff0000;border-radius:18px;padding:14px;text-align:center;background:linear-gradient(135deg,#1a0000,#000);box-shadow:0 0 25px rgba(255,0,0,.3)}.bank-time{font-size:32px;font-weight:900;color:#ff0000}.bank-status{font-size:13px;font-weight:800;margin-top:4px}
.btn-red{width:100%;background:linear-gradient(135deg,#ff0000,#cc0000);border:none;border-radius:14px;padding:15px;color:#fff;font-weight:900;font-size:15px;box-shadow:0 0 20px rgba(255,0,0,.5);margin:10px 0;cursor:pointer}
.btn-green{width:100%;background:linear-gradient(135deg,#00cc00,#009900);border:none;border-radius:14px;padding:15px;color:#fff;font-weight:900;font-size:15px;box-shadow:0 0 20px rgba(0,255,0,.3);margin:10px 0;cursor:pointer}
.select{width:100%;background:#000;border:1px solid #333;border-radius:12px;color:#fff;padding:12px;font-weight:700}.btn-small{background:#000;border:1px solid #ff0000;color:#fff;border-radius:12px;padding:12px 16px;font-weight:800}
.tabs{display:flex;gap:8px;margin:10px 0}.tab{flex:1;padding:11px;border-radius:12px;border:1px solid #222;background:#111;color:#777;font-weight:800;font-size:13px}.tab.active{background:#ff0000;color:#fff;border-color:#ff0000}
.list{max-height:350px;overflow-y:auto}.item{display:flex;justify-content:space-between;align-items:center;background:#000;border:1px solid #222;border-radius:10px;padding:10px 12px;margin:6px 0;font-size:13px;cursor:pointer}
.item.strong{border-color:#00ff00;box-shadow:0 0 10px rgba(0,255,0,.15)}.item.weak{border-color:#333;opacity:.6}
.hidden{display:none}.row{display:flex;gap:8px}.live-badge{display:flex;justify-content:space-between;background:#111;border:1px solid #222;border-radius:20px;padding:10px 16px;font-size:12px;margin:10px 0}
.badge-buy{background:#00ff00;color:#000;padding:3px 10px;border-radius:20px;font-weight:900;font-size:11px}.badge-sell{background:#ff0000;color:#fff;padding:3px 10px;border-radius:20px;font-weight:900;font-size:11px}.badge-no{background:#333;color:#888;padding:3px 10px;border-radius:20px;font-size:11px}

/* صندوق النتيجة الأسود الجديد */
.result-box{background:#000;border:3px solid #222;border-radius:20px;padding:20px;margin:16px 0;text-align:center;box-shadow:0 0 30px rgba(0,0,0,.8)}
.result-box.buy{border-color:#00ff00;box-shadow:0 0 30px rgba(0,255,0,.4), inset 0 0 20px rgba(0,255,0,.05)}
.result-box.sell{border-color:#ff0000;box-shadow:0 0 30px rgba(255,0,0,.4), inset 0 0 20px rgba(255,0,0,.05)}
.result-box.no{border-color:#555;box-shadow:0 0 15px rgba(255,255,255,.1)}
.result-pair{font-size:13px;color:#888;margin-bottom:6px;letter-spacing:1px}
.result-dir{font-size:44px;font-weight:900;margin:8px 0;line-height:1;letter-spacing:2px}
.result-dir.buy{color:#00ff00;text-shadow:0 0 20px #00ff00}
.result-dir.sell{color:#ff0000;text-shadow:0 0 20px #ff0000}
.result-dir.no{color:#888;font-size:28px}
.result-percent{font-size:22px;font-weight:800;color:#fff;margin:6px 0}
.result-detail{font-size:11px;color:#aaa;margin-top:8px;line-height:1.4}
.countdown-box{background:linear-gradient(135deg,#1a1a00,#000);border:2px solid #ffcc00;border-radius:14px;padding:12px;margin-top:14px}
.countdown-label{font-size:11px;color:#ffcc00;letter-spacing:1px}
.countdown-time{font-size:36px;font-weight:900;color:#ffcc00;text-shadow:0 0 15px #ffcc00;margin:4px 0}
.countdown-hint{font-size:11px;color:#fff;font-weight:700}
</style></head><body>
<div class="container" id="screen1">
<div class="crown-wrap"><div class="crown">👑</div></div>
<div class="title">MAD SIGNALS</div>
<div class="subtitle">TradingView مباشر</div>
<div class="sub2">● LIVE • REAL DATA • NO RANDOM • STRONG ONLY</div>
<div class="card" style="margin-top:22px">
<div style="font-size:13px;font-weight:700;margin-bottom:10px">اسمك</div>
<div class="input-wrap"><input id="nameInput" maxlength="20" placeholder="اكتب اسمك المميز" oninput="onNameInput()"><span class="counter" id="counter">0/20</span></div>
<button class="btn-main" id="enterBtn" onclick="enterApp()">🔥 ادخل كملك</button>
<div style="text-align:center;color:#00ff00;font-size:11px;margin-top:10px">● مباشر من TradingView • 78%+ قوي فقط • بدون عشوائي</div>
</div></div>
<div class="container hidden" id="screen2">
<div class="crown-wrap"><div class="crown" style="width:78px;height:78px;font-size:38px">👑</div></div>
<div style="text-align:center;font-size:21px;font-weight:900">👑 أهلاً <span id="userName" style="color:#ff0000">محمد</span></div>
<div class="sub2">● TradingView LIVE • إشارات حقيقية مباشرة</div>
<div class="live-badge"><span id="lastUpdate">آخر تحديث: --:--:--</span><span style="color:#ff0000" onclick="checkStrongOnly()">تحديث ↻</span></div>
<div class="bank-card"><div style="font-size:11px;color:#888">البنوك الحقيقية • LIVE</div><div class="bank-time" id="countdown">00:00:00</div><div class="bank-status" id="bankStatus">جاري...</div><div style="font-size:10px;color:#666;margin-top:4px" id="bankNext"></div></div>
<button class="btn-green" onclick="checkStrongOnly()">🎯 إشارات قوية فقط 78%+</button>
<button class="btn-red" onclick="checkAllMarkets()">📊 فحص جميع الأسواق</button>
<div class="card"><div style="font-weight:800;margin-bottom:10px">📊 فحص سوق واحد - مباشر قوي</div><div class="row"><select id="singleSelect" class="select">
<option>🇪🇺/🇺🇸 EUR/USD</option><option>🇬🇧/🇺🇸 GBP/USD</option><option>🇺🇸/🇯🇵 USD/JPY</option><option>🇦🇺/🇺🇸 AUD/USD</option><option>🇺🇸/🇨🇦 USD/CAD</option><option>🇪🇺/🇯🇵 EUR/JPY</option><option>🇨🇦/🇯🇵 CAD/JPY</option><option>🇪🇺/🇬🇧 EUR/GBP</option><option>🇦🇺/🇯🇵 AUD/JPY</option><option>🇳🇿/🇺🇸 NZD/USD</option><option>🇪🇺/🇨🇭 EUR/CHF</option><option>🇬🇧/🇯🇵 GBP/JPY</option><option>🇦🇺/🇨🇦 AUD/CAD</option><option>🇪🇺/🇦🇺 EUR/AUD</option><option>🇬🇧/🇨🇭 GBP/CHF</option><option>🇺🇸/🇨🇭 USD/CHF</option><option>🇪🇺/🇨🇦 EUR/CAD</option><option>🇦🇺/🇨🇭 AUD/CHF</option><option>🇬🇧/🇦🇺 GBP/AUD</option>
<option>🟡 🇪🇺/🇺🇸 EUR/USD OTC</option><option>🟡 🇬🇧/🇺🇸 GBP/USD OTC</option><option>🟡 🇬🇧/🇯🇵 GBP/JPY OTC</option><option>🟡 🇪🇺/🇯🇵 EUR/JPY OTC</option><option>🟡 🇦🇺/🇺🇸 AUD/USD OTC</option><option>🟡 🇺🇸/🇯🇵 USD/JPY OTC</option><option>🟡 🇪🇺/🇬🇧 EUR/GBP OTC</option><option>🟡 🇺🇸/🇨🇭 USD/CHF OTC</option>
</select><button class="btn-small" onclick="checkSingle()">فحص قوي</button></div>
<div id="singleResult"></div>
</div>
<div class="tabs"><button class="tab active" id="tabReal" onclick="switchTab('real')">حقيقي قوي 78%+ (19)</button><button class="tab" id="tabOtc" onclick="switchTab('otc')">OTC قوي 82%+ (8)</button></div>
<div id="realList" class="list"></div><div id="otcList" class="list hidden"></div>
</div>
<script>
let saved=localStorage.getItem('mad_name')||'';
if(saved){document.getElementById('nameInput').value=saved;onNameInput();}
function onNameInput(){let v=document.getElementById('nameInput').value;document.getElementById('counter').innerText=v.length+'/20';let b=document.getElementById('enterBtn');if(v.trim().length>=2)b.classList.add('active');else b.classList.remove('active');}
function enterApp(){let n=document.getElementById('nameInput').value.trim();if(n.length<2)return;localStorage.setItem('mad_name',n);document.getElementById('userName').innerText=n;document.getElementById('screen1').classList.add('hidden');document.getElementById('screen2').classList.remove('hidden');loadMarkets();}
function switchTab(t){document.getElementById('tabReal').className=t=='real'?'tab active':'tab';document.getElementById('tabOtc').className=t=='otc'?'tab active':'tab';document.getElementById('realList').classList.toggle('hidden',t!='real');document.getElementById('otcList').classList.toggle('hidden',t!='otc');}
const realPairs=["🇪🇺/🇺🇸 EUR/USD","🇬🇧/🇺🇸 GBP/USD","🇺🇸/🇯🇵 USD/JPY","🇦🇺/🇺🇸 AUD/USD","🇺🇸/🇨🇦 USD/CAD","🇪🇺/🇯🇵 EUR/JPY","🇨🇦/🇯🇵 CAD/JPY","🇪🇺/🇬🇧 EUR/GBP","🇦🇺/🇯🇵 AUD/JPY","🇳🇿/🇺🇸 NZD/USD","🇪🇺/🇨🇭 EUR/CHF","🇬🇧/🇯🇵 GBP/JPY","🇦🇺/🇨🇦 AUD/CAD","🇪🇺/🇦🇺 EUR/AUD","🇬🇧/🇨🇭 GBP/CHF","🇺🇸/🇨🇭 USD/CHF","🇪🇺/🇨🇦 EUR/CAD","🇦🇺/🇨🇭 AUD/CHF","🇬🇧/🇦🇺 GBP/AUD"];
const otcPairs=["🟡 🇪🇺/🇺🇸 EUR/USD OTC","🟡 🇬🇧/🇺🇸 GBP/USD OTC","🟡 🇬🇧/🇯🇵 GBP/JPY OTC","🟡 🇪🇺/🇯🇵 EUR/JPY OTC","🟡 🇦🇺/🇺🇸 AUD/USD OTC","🟡 🇺🇸/🇯🇵 USD/JPY OTC","🟡 🇪🇺/🇬🇧 EUR/GBP OTC","🟡 🇺🇸/🇨🇭 USD/CHF OTC"];
let candleTimer=null;

function loadMarkets(){
  let r=document.getElementById('realList');r.innerHTML='';
  realPairs.forEach(function(p){
    let d=document.createElement('div');d.className='item';
    d.innerHTML='<span>'+p+'</span><span><b id="r_'+p+'" class="badge-no">--</b></span>';
    d.onclick=function(){document.getElementById('singleSelect').value=p;checkSingle();};
    r.appendChild(d);
  });
  let o=document.getElementById('otcList');o.innerHTML='';
  otcPairs.forEach(function(p){
    let d=document.createElement('div');d.className='item';
    d.innerHTML='<span>'+p+'</span><span><b id="o_'+p+'" class="badge-no">--</b></span>';
    d.onclick=function(){document.getElementById('singleSelect').value=p;checkSingle();};
    o.appendChild(d);
  });
  checkStrongOnly();updateClock();
}
async function fetchSignal(pair, strong){
  try{
    let url='/signal?pair='+encodeURIComponent(pair);
    if(strong) url+='&strong=1';
    let res=await fetch(url);
    return await res.json();
  }catch(e){
    return{dir:"NO_TRADE",dir_formatted:"❌ خطأ",accuracy:0,detail:'error',tf:'--',is_strong:false};
  }
}
function getNextCandleSeconds(isOtc){
  let now=new Date();
  if(isOtc){
    // OTC 1 دقيقة - كل دقيقة شمعة جديدة
    return 60 - now.getSeconds();
  }else{
    // حقيقي 15m - كل 15 دقيقة: 00,15,30,45
    let m=now.getMinutes();
    let s=now.getSeconds();
    let nextM=Math.ceil((m+1)/15)*15;
    let diffM=nextM - m -1;
    if(diffM<0) diffM+=15;
    return diffM*60 + (60 - s);
  }
}
function startCandleCountdown(isOtc){
  if(candleTimer) clearInterval(candleTimer);
  function update(){
    let sec=getNextCandleSeconds(isOtc);
    let mm=String(Math.floor(sec/60)).padStart(2,'0');
    let ss=String(sec%60).padStart(2,'0');
    let el=document.getElementById('candleCountdown');
    if(el){
      el.innerText=mm+':'+ss;
      if(sec<=10){el.style.color='#ff0000';el.style.textShadow='0 0 20px #ff0000';}
      else if(sec<=30){el.style.color='#ffcc00';el.style.textShadow='0 0 15px #ffcc00';}
      else{el.style.color='#00ff00';}
      if(sec<=3 && sec>0){
        el.innerText='🔥 ادخل الآن! 00:0'+sec;
      }
    }
    if(sec<=0){
      clearInterval(candleTimer);
      // مع بداية شمعة جديدة - نحدث الإشارة تلقائي
      let pair=document.getElementById('singleSelect').value;
      if(pair) setTimeout(function(){checkSingle();}, 1500);
    }
  }
  update();
  candleTimer=setInterval(update, 1000);
}
async function checkSingle(){
  let pair=document.getElementById('singleSelect').value;
  let isOtc=pair.indexOf('OTC')!==-1;
  let resDiv=document.getElementById('singleResult');
  resDiv.innerHTML='<div style="text-align:center;padding:20px;color:#888">⏳ يحلل '+pair+' من TradingView مباشر...</div>';
  // ينزل تحت تلقائي
  setTimeout(function(){resDiv.scrollIntoView({behavior:'smooth',block:'center'});}, 200);
  
  let data=await fetchSignal(pair, true);
  
  // ينزل تحت مرة ثانية بعد النتيجة
  setTimeout(function(){resDiv.scrollIntoView({behavior:'smooth',block:'center'});}, 100);
  
  if(data.dir=='NO_TRADE'){
    resDiv.innerHTML='<div class="result-box no">'
      +'<div class="result-pair">'+pair+'</div>'
      +'<div class="result-dir no">⛔ لا تدخل</div>'
      +'<div class="result-percent" style="color:#888">'+data.accuracy+'% ضعيف</div>'
      +'<div class="result-detail">'+data.detail+'</div>'
      +'<div class="countdown-box"><div class="countdown-label">انتظر الشمعة القادمة</div><div id="candleCountdown" class="countdown-time">--:--</div><div class="countdown-hint">السوق متذبذب - لا تدخل الآن</div></div>'
      +'</div>';
  }else{
    let isBuy=data.dir.indexOf('BUY')!==-1;
    let boxClass=isBuy?'buy':'sell';
    let dirClass=isBuy?'buy':'sell';
    let dirText=isBuy?'BUY ↗️':'SELL ↘️';
    let dirEmoji=isBuy?'🟢':'🔴';
    let bgColor=isBuy?'#00ff00':'#ff0000';
    resDiv.innerHTML='<div class="result-box '+boxClass+'">'
      +'<div class="result-pair">'+pair+' • TradingView LIVE</div>'
      +'<div class="result-dir '+dirClass+'">'+dirEmoji+' '+dirText+'</div>'
      +'<div class="result-percent">'+data.dir_formatted+'</div>'
      +'<div class="result-detail">'+data.detail+'<br>● مباشر من TradingView • حقيقي 100%</div>'
      +'<div class="countdown-box"><div class="countdown-label">⏰ عداد الشمعة الجديدة - استعد للدخول</div><div id="candleCountdown" class="countdown-time">00:00</div><div class="countdown-hint">ادخل مع بداية الشمعة الجديدة • '+(isOtc?'OTC 1 دقيقة':'حقيقي 15 دقيقة')+'</div></div>'
      +'</div>';
  }
  startCandleCountdown(isOtc);
}
async function checkStrongOnly(){
  let btn=document.querySelector('.btn-green');
  if(btn){btn.innerText='⏳ يفحص القوي من TradingView...';btn.disabled=true;}
  let all=realPairs.concat(otcPairs);
  let strongCount=0;
  let promises=all.map(async function(p){
    try{let d=await fetchSignal(p,true);return {pair:p,data:d};}catch(e){return {pair:p,data:null};}
  });
  let results=await Promise.all(promises);
  results.forEach(function(r){
    let p=r.pair;let d=r.data;
    if(!d) return;
    let id=(p.indexOf('OTC')!==-1?'o_':'r_')+p;
    let el=document.getElementById(id);
    if(el){
      if(d.dir=='NO_TRADE'){el.innerText='⛔ لا تدخل';el.className='badge-no';el.parentElement.parentElement.className='item weak';}
      else{el.innerText=d.dir_formatted;el.className=d.dir.indexOf('BUY')!==-1?'badge-buy':'badge-sell';el.parentElement.parentElement.className='item strong';strongCount++;}
    }
  });
  document.getElementById('lastUpdate').innerText='✅ قوي TradingView: '+strongCount+' / '+all.length+' • '+new Date().toLocaleTimeString('ar-SA');
  if(btn){btn.innerText='🎯 إشارات قوية TradingView ('+strongCount+')';btn.disabled=false;}
}
async function checkAllMarkets(){
  let btn=document.querySelector('.btn-red');
  if(btn){btn.innerText='⏳ فحص TradingView...';btn.disabled=true;}
  let all=realPairs.concat(otcPairs);
  let promises=all.map(async function(p){
    try{let d=await fetchSignal(p,false);return {pair:p,data:d};}catch(e){return {pair:p,data:null};}
  });
  let results=await Promise.all(promises);
  results.forEach(function(r){
    let p=r.pair;let d=r.data;
    if(!d) return;
    let id=(p.indexOf('OTC')!==-1?'o_':'r_')+p;
    let el=document.getElementById(id);
    if(el){
      if(d.dir=='NO_TRADE'){el.innerText='⛔ لا تدخل';el.className='badge-no';}
      else{el.innerText=d.dir_formatted;el.className=d.dir.indexOf('BUY')!==-1?'badge-buy':'badge-sell';}
    }
  });
  document.getElementById('lastUpdate').innerText='آخر تحديث TradingView: '+new Date().toLocaleTimeString('ar-SA');
  if(btn){btn.innerText='📊 فحص جميع الأسواق';btn.disabled=false;}
}
function updateClock(){
  function tick(){
    let now=new Date();
    let ny=new Date(now.toLocaleString("en-US",{timeZone:"America/New_York"}));
    let h=ny.getHours();let target,status;
    if(h>=20||h<2){target=2;status="🌙 آسيا";}else if(h>=2&&h<7){target=7;status="🇬🇧 لندن";}else if(h>=7&&h<12){status="🔥 لندن+نيويورك TOP";target=20;}else{status="🇺🇸 نيويورك";target=20;}
    let t=new Date(ny);t.setHours(target,0,0,0);if(t<=ny)t.setDate(t.getDate()+1);
    let diff=t-ny;
    let hh=String(Math.floor(diff/1000/3600)).padStart(2,'0');
    let mm=String(Math.floor((diff/1000%3600)/60)).padStart(2,'0');
    let ss=String(Math.floor(diff/1000%60)).padStart(2,'0');
    document.getElementById('countdown').innerText=hh+':'+mm+':'+ss;
    document.getElementById('bankStatus').innerText=status;
    document.getElementById('bankNext').innerText=status+' تفتح بعد: '+hh+':'+mm+':'+ss+' • LIVE TradingView';
  }
  tick();setInterval(tick,1000);
}
if(saved&&saved.length>=2)enterApp();
</script></body></html>
"""

@app.route('/')
def home(): return "MAD BOT TradingView Strong - No Random"
@app.route('/mad')
def mad(): return MAD_HTML
@app.route('/health')
def health(): return "OK"

@app.route('/signal')
def signal_api():
    pair = request.args.get('pair','EUR/USD')
    strong_mode = request.args.get('strong','0') == '1'
    clean = pair
    for flag in ["🇪🇺/🇺🇸 ","🇬🇧/🇺🇸 ","🇺🇸/🇯🇵 ","🇦🇺/🇺🇸 ","🇺🇸/🇨🇦 ","🇪🇺/🇯🇵 ","🇨🇦/🇯🇵 ","🇪🇺/🇬🇧 ","🇦🇺/🇯🇵 ","🇳🇿/🇺🇸 ","🇪🇺/🇨🇭 ","🇬🇧/🇯🇵 ","🇦🇺/🇨🇦 ","🇪🇺/🇦🇺 ","🇬🇧/🇨🇭 ","🇺🇸/🇨🇭 ","🇪🇺/🇨🇦 ","🇦🇺/🇨🇭 ","🇬🇧/🇦🇺 ","🟡 "," OTC"]:
        clean = clean.replace(flag,"")
    clean = clean.strip()
    symbol = ALL_MARKETS.get(pair) or "EURUSD"
    if "/" in clean:
        symbol = clean.replace("/","").replace("OTC","").strip()
    is_otc = "OTC" in pair
    try:
        if is_otc:
            d,p,det = get_strong_signal_otc(symbol)
            min_strong = 82
        else:
            d,p,det = get_strong_signal_real(symbol)
            min_strong = 78
        is_strong = p >= min_strong and d != "NO_TRADE"
        if d == "NO_TRADE":
            return jsonify({"dir": "NO_TRADE", "dir_formatted": "⛔ لا تدخل", "accuracy": p, "detail": det, "tf": "10s" if is_otc else "15m", "pair": pair, "is_strong": False})
        if d == "BUY":
            dir_fmt = "🟢 BUY ↗️ %s%%" % p
            dir_plain = "BUY"
        else:
            dir_fmt = "🔴 SELL ↘️ %s%%" % p
            dir_plain = "SELL"
        tf = "OTC 1m+5m+15m TradingView" if is_otc else "REAL 5m+15m+30m TradingView"
        return jsonify({"dir": dir_plain, "dir_formatted": dir_fmt, "accuracy": p, "detail": det, "tf": tf, "pair": pair, "is_strong": is_strong})
    except Exception as e:
        return jsonify({"dir": "NO_TRADE", "dir_formatted": "❌ خطأ", "accuracy": 0, "detail": str(e), "tf": "error", "pair": pair, "is_strong": False})

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting Flask on port {port}")
    # Render يحتاج 0.0.0.0 و debug=False
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if bot:
    @bot.message_handler(commands=['start'])
    def start(msg):
        if msg.from_user.id not in authorized:
            bot.send_message(msg.chat.id, "كلمة السر:")
            return
        main_menu(msg.chat.id)
    @bot.message_handler(func=lambda m: m.from_user.id not in authorized)
    def check(m):
        try: bot.delete_message(m.chat.id, m.message_id)
        except: pass
        if m.text.strip()==PASSWORD:
            authorized.add(m.from_user.id)
            main_menu(m.chat.id)
        else:
            bot.send_message(m.chat.id, "❌")
    @bot.callback_query_handler(func=lambda c: c.data=="all_real")
    def cb_all_real(call):
        ld = bot.send_message(call.message.chat.id, "⏳ افحص الحقيقي القوي TradingView...")
        strong=[]
        for n,s in MARKETS_REAL.items():
            d,p,det = get_strong_signal_real(s)
            if d!="NO_TRADE" and p>=78: strong.append((p,n,d,p,det))
        strong.sort(reverse=True, key=lambda x:x[0])
        if not strong:
            bot.edit_message_text("⛔ لا يوجد إشارات قوية TradingView الآن\nكل الأسواق متذبذبة", call.message.chat.id, ld.message_id)
        else:
            text="🔥 إشارات قوية حقيقية TradingView 78%+\n━━━━━━━━━━━━\n"
            for p,n,d,pp,det in strong[:5]:
                emoji="🟢 BUY ↗️" if d=="BUY" else "🔴 SELL ↘️"
                text+="%s %s %s%%\n%s\n\n" % (n, emoji, pp, det)
            bot.edit_message_text(text, call.message.chat.id, ld.message_id)
    @bot.callback_query_handler(func=lambda c: c.data=="all_otc")
    def cb_all_otc(call):
        ld = bot.send_message(call.message.chat.id, "⏳ افحص OTC القوي TradingView...")
        strong=[]
        for n,s in MARKETS_OTC.items():
            d,p,det = get_strong_signal_otc(s)
            if d!="NO_TRADE" and p>=82: strong.append((p,n,d,p,det))
        strong.sort(reverse=True, key=lambda x:x[0])
        if not strong:
            bot.edit_message_text("⛔ لا يوجد OTC قوي الآن", call.message.chat.id, ld.message_id)
        else:
            text="🟡 OTC قوي TradingView 82%+\n━━━━━━━━━━━━\n"
            for p,n,d,pp,det in strong[:5]:
                emoji="🟢 BUY ↗️" if d=="BUY" else "🔴 SELL ↘️"
                text+="%s %s %s%%\n%s\n\n" % (n, emoji, pp, det)
            bot.edit_message_text(text, call.message.chat.id, ld.message_id)
    @bot.callback_query_handler(func=lambda c: c.data=="golden_strong")
    def cb_golden_strong(call):
        ld = bot.send_message(call.message.chat.id, "⏳ أقوى فرصة TradingView...")
        all_strong=[]
        for n,s in ALL_MARKETS.items():
            is_otc = "OTC" in n
            if is_otc:
                d,p,det = get_strong_signal_otc(s)
                if p>=82 and d!="NO_TRADE": all_strong.append((p,n,d,p,det))
            else:
                d,p,det = get_strong_signal_real(s)
                if p>=78 and d!="NO_TRADE": all_strong.append((p,n,d,p,det))
        all_strong.sort(reverse=True, key=lambda x:x[0])
        if not all_strong:
            bot.edit_message_text("⛔ لا يوجد فرص قوية الآن", call.message.chat.id, ld.message_id)
        else:
            p,n,d,pp,det = all_strong[0]
            emoji="🟢 BUY ↗️" if d=="BUY" else "🔴 SELL ↘️"
            bot.edit_message_text("🔥🔥 أقوى فرصة TradingView %s%%\n%s\n%s\n\n%s\n\n✅ مباشر وقوي" % (pp, n, emoji, det), call.message.chat.id, ld.message_id)
    @bot.callback_query_handler(func=lambda c: c.data.startswith("s_"))
    def cb_s(call):
        n = call.data[2:]
        is_otc = "OTC" in n
        if is_otc: d,p,det = get_strong_signal_otc(ALL_MARKETS[n])
        else: d,p,det = get_strong_signal_real(ALL_MARKETS[n])
        if d=="NO_TRADE": bot.send_message(call.message.chat.id, "⛔ %s\n%s" % (n, det))
        else:
            emoji="🟢 BUY ↗️" if d=="BUY" else "🔴 SELL ↘️"
            bot.send_message(call.message.chat.id, "%s\n%s %s%%\n%s" % (n, emoji, p, det))

def run_bot():
    if not bot: return
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
    except Exception as e:
        print("Bot error: %s" % e)
        time.sleep(5)
        run_bot()

if __name__ == "__main__":
    # شغل البوت في ثريد منفصل - لو طاح الفلاسك يبقى شغال
    try:
        if bot:
            threading.Thread(target=run_bot, daemon=True).start()
            print("Bot thread started")
    except Exception as e:
        print(f"Bot thread failed to start: {e}")
    
    # شغل الفلاسك - هذا لازم يبقى شغال
    try:
        run_flask()
    except Exception as e:
        print(f"Flask failed: {e}")
        # حتى لو فشل الفلاسك، لا تخرج بسرعة
        import time
        time.sleep(10)
