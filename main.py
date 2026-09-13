import os, time, threading
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from tradingview_ta import TA_Handler, Interval
from datetime import datetime, timedelta
import pytz

TOKEN = os.environ.get("TOKEN") or "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
PASSWORD = os.environ.get("PASSWORD") or "7154"
bot = telebot.TeleBot(TOKEN, threaded=False)

MARKETS_REAL = {
    "🇪🇺/🇺🇸 EUR/USD": "EURUSD", "🇬🇧/🇺🇸 GBP/USD": "GBPUSD", "🇺🇸/🇯🇵 USD/JPY": "USDJPY",
    "🇦🇺/🇺🇸 AUD/USD": "AUDUSD", "🇺🇸/🇨🇦 USD/CAD": "USDCAD", "🇪🇺/🇯🇵 EUR/JPY": "EURJPY",
    "🇨🇦/🇯🇵 CAD/JPY": "CADJPY", "🇪🇺/🇬🇧 EUR/GBP": "EURGBP", "🇦🇺/🇯🇵 AUD/JPY": "AUDJPY",
    "🇳🇿/🇺🇸 NZD/USD": "NZDUSD", "🇪🇺/🇨🇭 EUR/CHF": "EURCHF", "🇬🇧/🇯🇵 GBP/JPY": "GBPJPY",
    "🇦🇺/🇨🇦 AUD/CAD": "AUDCAD", "🇪🇺/🇦🇺 EUR/AUD": "EURAUD", "🇬🇧/🇨🇭 GBP/CHF": "GBPCHF",
    "🇺🇸/🇨🇭 USD/CHF": "USDCHF", "🇪🇺/🇨🇦 EUR/CAD": "EURCAD", "🇦🇺/🇨🇭 AUD/CHF": "AUDCHF",
    "🇬🇧/🇦🇺 GBP/AUD": "GBPAUD", "🇨🇦/🇨🇭 CAD/CHF": "CADCHF", "🇪🇺/🇳🇿 EUR/NZD": "EURNZD",
    "🇬🇧/🇳🇿 GBP/NZD": "GBPNZD",
}

MARKETS_OTC = {
    "🟡 EUR/USD OTC": "EURUSD", "🟡 GBP/USD OTC": "GBPUSD", "🟡 GBP/JPY OTC": "GBPJPY",
    "🟡 EUR/JPY OTC": "EURJPY", "🟡 AUD/USD OTC": "AUDUSD", "🟡 USD/JPY OTC": "USDJPY",
    "🟡 EUR/GBP OTC": "EURGBP", "🟡 USD/CHF OTC": "USDCHF",
}

authorized = set()
KSA_TZ = pytz.timezone("Asia/Riyadh")
NY_TZ = pytz.timezone("America/New_York")

def get_tf_signal(symbol, interval):
    try:
        h = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=interval)
        s = h.get_analysis().summary
        if s['BUY']+s['SELL']==0: return "NEUTRAL", 50
        d = "BUY" if s['BUY']>s['SELL'] else "SELL"
        return d, int((max(s['BUY'],s['SELL'])/(s['BUY']+s['SELL']))*100)
    except: return "ERROR",0

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

def get_bank_status_fixed():
    now_ny = datetime.now(NY_TZ)
    now_ksa = datetime.now(KSA_TZ)
    def time_until(target_h, target_m=0):
        target = now_ny.replace(hour=target_h, minute=target_m, second=0, microsecond=0)
        if target <= now_ny:
            target += timedelta(days=1)
        delta = target - now_ny
        total = int(delta.total_seconds())
        return total//3600, (total%3600)//60, total%60
    h = now_ny.hour
    txt = f"🏦 MAD BOT - حالة البنوك (مصلحة)\n━━━━━━━━━━━━━━━\n"
    txt += f"🕐 نيويورك: {now_ny.strftime('%I:%M:%S %p')}\n"
    txt += f"🕐 السعودية: {now_ksa.strftime('%I:%M:%S %p')}\n━━━━━━━━━━━━━━━\n"
    if (20 <= h <= 23) or (0 <= h < 2):
        hh,mm,ss = time_until(2,0)
        txt += f"🌙 آسيا فاتحة (8م-1ص نيويورك)\n🇸🇦 4فجراً-9ص\n❌ لا تدخل\n⏳ لندن تفتح بعد: {hh:02d}:{mm:02d}:{ss:02d}\n"
        hh2,mm2,ss2 = time_until(7,0)
        txt += f"⏳ نيويورك تفتح بعد: {hh2:02d}:{mm2:02d}:{ss2:02d}\n"
    elif 2 <= h < 5:
        hh,mm,ss = time_until(7,0)
        txt += f"🇬🇧 لندن فاتحة (2ص-5ص نيويورك)\n🇸🇦 9ص-12ظ\n✅ ادخل\n⏳ نيويورك تفتح بعد: {hh:02d}:{mm:02d}:{ss:02d}\n🔥 أفضل وقت لما تفتح نيويورك\n"
    elif 5 <= h < 7:
        hh,mm,ss = time_until(7,0)
        txt += f"⏸️ بين الجلسات (5ص-7ص نيويورك)\n🇸🇦 12ظ-2ظ\n⏳ نيويورك تفتح بعد: {hh:02d}:{mm:02d}:{ss:02d}\n"
    elif 7 <= h < 12:
        txt += f"🇺🇸🇬🇧 نيويورك + لندن فاتحين\n🇸🇦 2ظ-7م\n"
        txt += f"🔥🔥 TOP - كل البنوك فاتحة\n✅ أفضل وقت الآن!\n"
        hh,mm,ss = time_until(20,0)
        txt += f"⏳ آسيا تفتح بعد: {hh:02d}:{mm:02d}:{ss:02d}\n"
    else:
        hh,mm,ss = time_until(20,0)
        txt += f"🇺🇸 نيويورك فاتحة لوحدها\n🇸🇦 7م-4فجراً\n✅ سيولة متوسطة\n⏳ آسيا تفتح بعد: {hh:02d}:{mm:02d}:{ss:02d}\n"
    txt += f"━━━━━━━━━━━━━━━\n💡 أفضل وقت: 9ص-5م السعودية 🇸🇦"
    return txt

def main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=1)
    webapp_url = os.environ.get("RENDER_EXTERNAL_URL","") + "/mad"
    if not webapp_url.startswith("http"):
        webapp_url = "https://mad-bot.onrender.com/mad"
    markup.add(InlineKeyboardButton("🔴 MAD BOT - الشكل الجديد أسود/أحمر", web_app=WebAppInfo(url=webapp_url)))
    markup.add(InlineKeyboardButton("🏦 حالة البنوك + عداد الفتح", callback_data="check_banks"))
    markup.add(InlineKeyboardButton("📊 قائمة الأسواق الحقيقية (22) - اضغط واختر", callback_data="single_real"))
    markup.add(InlineKeyboardButton("🌙 قائمة أسواق OTC (8) - اضغط واختر", callback_data="single_otc"))
    markup.add(InlineKeyboardButton("🔥 الفرص الذهبية حقيقي 15m", callback_data="golden_real"))
    markup.add(InlineKeyboardButton("⚡ الفرص الذهبية OTC 10s", callback_data="golden_otc"))
    bot.send_message(chat_id, "🔴⚫ MAD BOT - مصلح\n\n🏦 عداد البنوك صحيح 100%\n📊 22 سوق حقيقي\n🌙 8 OTC\n\nمنطق أصلي - ما لمسته", reply_markup=markup)

app = Flask(__name__)
@app.route('/')
def home(): return "MAD BOT Live! Bank Fixed"
@app.route('/bank')
def bank_route(): return get_bank_status_fixed()
def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id not in authorized:
        bot.send_message(msg.chat.id, "🔒 MAD BOT - ارسل كلمة السر:"); return
    main_menu(msg.chat.id)

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def check_pass(m):
    if m.text.strip()==PASSWORD:
        authorized.add(m.from_user.id)
        bot.send_message(m.chat.id, "✅ MAD BOT فتح - ساعة البنوك مصلحة")
        main_menu(m.chat.id)
    else: bot.send_message(m.chat.id, "❌ غلط")

@bot.callback_query_handler(func=lambda c: c.data=="check_banks")
def cb_banks(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔄 تحديث العداد", callback_data="check_banks"))
    bot.send_message(call.message.chat.id, get_bank_status_fixed(), reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data=="single_real")
def cb_single_real(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup(row_width=2)
    for name in MARKETS_REAL:
        markup.add(InlineKeyboardButton(name, callback_data=f"market_real_{name}"))
    bot.send_message(call.message.chat.id, "📋 قائمة الأسواق الحقيقية (22) - اضغط واختر أي سوق - تدخل 15m:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data=="single_otc")
def cb_single_otc(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup(row_width=2)
    for name in MARKETS_OTC:
        markup.add(InlineKeyboardButton(name, callback_data=f"market_otc_{name}"))
    bot.send_message(call.message.chat.id, "🌙 قائمة OTC (8) - اضغط واختر - تدخل 10s:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data=="golden_real")
def cb_golden_real(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id, "⏳ افحص 22 سوق...")
    loading = bot.send_message(call.message.chat.id, "⏳ MAD BOT يفحص 22 سوق حقيقي 15m...")
    goldens=[]; start=time.time()
    for name,sym in MARKETS_REAL.items():
        try:
            d,p,details = get_confluence_signal(sym)
            if d!="NO_TRADE" and p>=70: goldens.append((p,f"{'🟢 BUY' if d=='BUY' else '🔴 SELL'} {name} - {p}%\n{details}\n⏱️ 15m\n"))
        except: continue
    goldens.sort(key=lambda x:x[0], reverse=True)
    elapsed=round(time.time()-start,1)
    if not goldens:
        bot.edit_message_text(f"❌ فحصت {len(MARKETS_REAL)} سوق في {elapsed}ث - لا يوجد", call.message.chat.id, loading.message_id)
    else:
        text=f"🏆 TOP 15m {goldens[0][0]}%\n{goldens[0][1]}\n━━━━━━━━━━━━\n🔥 {len(goldens)} فرص في {elapsed}ث\n"
        for i,(p,d) in enumerate(goldens,1): text+=f"{'👑' if i==1 else f'{i}.'} {d}\n"
        bot.edit_message_text(text, call.message.chat.id, loading.message_id)

@bot.callback_query_handler(func=lambda c: c.data=="golden_otc")
def cb_golden_otc(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id, "⏳ افحص OTC...")
    loading = bot.send_message(call.message.chat.id, "⚡ MAD BOT يفحص 8 OTC 10s...")
    goldens=[]; start=time.time()
    for name,sym in MARKETS_OTC.items():
        try:
            d,p,details = get_confluence_signal(sym)
            if d!="NO_TRADE" and p>=70: goldens.append((p,f"{'🟢 BUY' if d=='BUY' else '🔴 SELL'} {name} - {p}%\n{details}\n⏱️ 10s\n"))
        except: continue
    goldens.sort(key=lambda x:x[0], reverse=True)
    elapsed=round(time.time()-start,1)
    if not goldens:
        bot.edit_message_text(f"❌ فحصت {len(MARKETS_OTC)} سوق في {elapsed}ث - لا يوجد", call.message.chat.id, loading.message_id)
    else:
        text=f"🏆 TOP 10s {goldens[0][0]}%\n{goldens[0][1]}\n━━━━━━━━━━━━\n⚡ {len(goldens)} فرص في {elapsed}ث\n"
        for i,(p,d) in enumerate(goldens,1): text+=f"{'👑' if i==1 else f'{i}.'} {d}\n"
        bot.edit_message_text(text, call.message.chat.id, loading.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_real_"))
def cb_market_real(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    name = call.data.replace("market_real_", "")
    loading = bot.send_message(call.message.chat.id, f"⏳ فحص {name} 15m...")
    d,p,details = get_confluence_signal(MARKETS_REAL[name])
    if d=="NO_TRADE":
        bot.edit_message_text(f"📊 {name} 15m\n{details}", call.message.chat.id, loading.message_id)
    else:
        emoji="🟢 BUY" if d=="BUY" else "🔴 SELL"
        bot.edit_message_text(f"🔴 MAD BOT 15m\n📊 {name}\n{emoji}\n💪 {p}%\n\n{details}\n⏱️ 15 دقيقة", call.message.chat.id, loading.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_otc_"))
def cb_market_otc(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    name = call.data.replace("market_otc_", "")
    loading = bot.send_message(call.message.chat.id, f"⏳ فحص {name} 10s...")
    d,p,details = get_confluence_signal(MARKETS_OTC[name])
    if d=="NO_TRADE":
        bot.edit_message_text(f"🌙 {name} 10s\n{details}", call.message.chat.id, loading.message_id)
    else:
        emoji="🟢 BUY" if d=="BUY" else "🔴 SELL"
        bot.edit_message_text(f"🔴 MAD BOT 10s\n🌙 {name}\n{emoji}\n💪 {p}%\n\n{details}\n⏱️ 10 ثواني", call.message.chat.id, loading.message_id)

threading.Thread(target=run_flask, daemon=True).start()
bot.remove_webhook()
time.sleep(2)
while True:
    try: bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
    except Exception as e: print(e); time.sleep(5)
