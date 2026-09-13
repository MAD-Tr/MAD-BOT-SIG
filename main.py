import os
import time
import threading
from datetime import datetime, timedelta
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval

TOKEN = os.environ.get("TOKEN") or "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
PASSWORD = os.environ.get("PASSWORD") or "7154"
bot = telebot.TeleBot(TOKEN, threaded=False)

MARKETS = {
    "🇪🇺/🇺🇸 EUR/USD": "EURUSD", "🇬🇧/🇺🇸 GBP/USD": "GBPUSD", "🇺🇸/🇯🇵 USD/JPY": "USDJPY",
    "🇦🇺/🇺🇸 AUD/USD": "AUDUSD", "🇺🇸/🇨🇦 USD/CAD": "USDCAD", "🇪🇺/🇯🇵 EUR/JPY": "EURJPY",
    "🇨🇦/🇯🇵 CAD/JPY": "CADJPY", "🇪🇺/🇬🇧 EUR/GBP": "EURGBP", "🇦🇺/🇯🇵 AUD/JPY": "AUDJPY",
    "🇳🇿/🇺🇸 NZD/USD": "NZDUSD", "🇪🇺/🇨🇭 EUR/CHF": "EURCHF", "🇬🇧/🇯🇵 GBP/JPY": "GBPJPY",
    "🇦🇺/🇨🇦 AUD/CAD": "AUDCAD", "🇪🇺/🇦🇺 EUR/AUD": "EURAUD", "🇬🇧/🇨🇭 GBP/CHF": "GBPCHF",
    "🇺🇸/🇨🇭 USD/CHF": "USDCHF", "🇪🇺/🇨🇦 EUR/CAD": "EURCAD", "🇦🇺/🇨🇭 AUD/CHF": "AUDCHF",
    "🇬🇧/🇦🇺 GBP/AUD": "GBPAUD", "🇨🇦/🇨🇭 CAD/CHF": "CADCHF", "🇪🇺/🇳🇿 EUR/NZD": "EURNZD",
    "🇬🇧/🇳🇿 GBP/NZD": "GBPNZD",
}

user_data = {}
last_request = {}
authorized = set()

# ===== عداد البنوك للأسواق الحقيقية =====
def get_bank_counter():
    """يرجع حالة البنوك والعد التنازلي - بتوقيت نيويورك"""
    try:
        # نحسب بتوقيت UTC ثم نحول لنيويورك (EST -5)
        now_utc = datetime.utcnow()
        # توقيت نيويورك = UTC-4 (صيفي) أو -5 (شتوي) - نستخدم -4 للتبسيط
        now_ny = now_utc - timedelta(hours=4)
        h = now_ny.hour
        m = now_ny.minute
        s = now_ny.second
        
        # جلسات البنوك بتوقيت نيويورك
        # آسيا: 8م - 2ص، لندن: 2ص - 7ص، لندن+نيويورك: 7ص - 12ظ، نيويورك: 12ظ - 8م
        if h >= 20 or h < 2:
            # آسيا
            status = "🌙 آسيا - سيولة ضعيفة"
            target_h = 2
            is_top = False
        elif h >= 2 and h < 7:
            # لندن
            status = "🇬🇧 لندن - سيولة جيدة"
            target_h = 7
            is_top = False
        elif h >= 7 and h < 12:
            # لندن+نيويورك TOP
            status = "🔥 لندن+نيويورك TOP - أفضل وقت"
            target_h = 12
            is_top = True
        else:
            # نيويورك
            status = "🇺🇸 نيويورك - سيولة جيدة"
            target_h = 20
            is_top = False
        
        # حساب الوقت المتبقي
        target = now_ny.replace(hour=target_h, minute=0, second=0, microsecond=0)
        if target <= now_ny:
            target += timedelta(days=1)
        diff = target - now_ny
        total_sec = int(diff.total_seconds())
        hh = total_sec // 3600
        mm = (total_sec % 3600) // 60
        ss = total_sec % 60
        
        countdown = f"{hh:02d}:{mm:02d}:{ss:02d}"
        
        return status, countdown, is_top, h
    except Exception as e:
        return "🏦 البنوك", "00:00:00", False, 0

def get_tf_signal(symbol, interval):
    try:
        h = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=interval)
        s = h.get_analysis().summary
        buys, sells = s['BUY'], s['SELL']
        if buys+sells == 0: return "NEUTRAL", 50
        direction = "BUY" if buys > sells else "SELL"
        percent = int((max(buys, sells) / (buys + sells)) * 100)
        return direction, percent
    except:
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

        if final >= 85:
            decision = "🔥🔥 ممتاز جدا - TOP ادخل 2% 🔥🔥"
        elif final >= 78:
            decision = "✅ ممتاز - ادخل 1.5%"
        elif final >= 70:
            decision = "✅ جيد - ادخل 1%"
        else:
            decision = "⚠️ متوسط - لا تدخل"

        return d5, final, f"H1:{p1h}% | 15m:{p15}% | 5m:{p5}%\n{decision}"

    return "NO_TRADE", 0, f"H1:{p1h}% {d1h} | 15m:{p15}% {d15} | 5m:{p5}% {d5}\n\n❌ متضارب"

def main_menu(chat_id):
    status, countdown, is_top, _ = get_bank_counter()
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔥 البحث عن الفرصة الذهبية (22 سوق)", callback_data="golden"))
    markup.add(InlineKeyboardButton("📊 فحص سوق واحد", callback_data="single"))
    markup.add(InlineKeyboardButton(f"🏦 {status} - {countdown}", callback_data="bank_info"))
    
    top_msg = "🔥🔥 TOP وقت البنوك الآن - أفضل إشارات 🔥🔥\n" if is_top else ""
    text = f"{top_msg}💰 بوت احترافي - أسواق حقيقية فقط\n\n🏦 {status}\n⏰ العد التنازلي: {countdown}\n\nاختار:"
    bot.send_message(chat_id, text, reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id not in authorized:
        bot.send_message(msg.chat.id, "🔒 ارسل كلمة السر:")
        return
    main_menu(msg.chat.id)

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def check_pass(m):
    if m.text.strip() == PASSWORD:
        authorized.add(m.from_user.id)
        bot.send_message(m.chat.id, "✅ تم فتح البوت")
        main_menu(m.chat.id)
    else:
        bot.send_message(m.chat.id, "❌ كلمة سر غلط")

@bot.callback_query_handler(func=lambda c: c.data=="single")
def single(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup(row_width=2)
    for name in MARKETS:
        markup.add(InlineKeyboardButton(name, callback_data=f"market_{name}"))
    status, countdown, _, _ = get_bank_counter()
    bot.send_message(call.message.chat.id, f"🏦 {status}\n⏰ {countdown}\n\nاختر السوق:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data=="bank_info")
def bank_info(call):
    if call.from_user.id not in authorized: return
    status, countdown, is_top, h = get_bank_counter()
    msg = f"🏦 عداد البنوك للأسواق الحقيقية\n\n"
    msg += f"📍 الحالة: {status}\n"
    msg += f"⏰ الوقت المتبقي: {countdown}\n\n"
    msg += f"🕐 توقيت نيويورك الآن: {h}:00\n\n"
    msg += f"📊 جلسات التداول:\n"
    msg += f"🌙 آسيا (8م-2ص): سيولة ضعيفة - تجنب\n"
    msg += f"🇬🇧 لندن (2ص-7ص): سيولة جيدة\n"
    msg += f"🔥 لندن+نيويورك (7ص-12ظ): TOP - أفضل وقت ✅\n"
    msg += f"🇺🇸 نيويورك (12ظ-8م): سيولة جيدة\n\n"
    if is_top:
        msg += f"🔥🔥 الآن أفضل وقت للتداول! البنوك الكبيرة شغالة مع بعض 🔥🔥"
    else:
        msg += f"💡 نصيحة: انتظر جلسة لندن+نيويورك للحصول على إشارات أقوى"
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, msg)

@bot.callback_query_handler(func=lambda c: c.data=="golden")
def golden(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id, "⏳ افحص 22 سوق...")
    status, countdown, is_top, _ = get_bank_counter()
    loading = bot.send_message(call.message.chat.id, f"🏦 {status}\n⏰ {countdown}\n\n⏳ افحص {len(MARKETS)} سوق (25 ثانية)...")
    goldens = []
    start_t = time.time()
    for name, sym in MARKETS.items():
        try:
            d, p, details = get_confluence_signal(sym)
            if d!= "NO_TRADE" and p >= 70:
                emoji = "🟢 BUY" if d=="BUY" else "🔴 SELL"
                goldens.append((p, f"{emoji} {name} - {p}%\n{details}\n"))
        except: continue

    goldens.sort(key=lambda x: x[0], reverse=True)
    elapsed = round(time.time() - start_t, 1)
    status2, countdown2, is_top2, _ = get_bank_counter()
    
    if not goldens:
        bot.edit_message_text(f"🏦 {status2} | ⏰ {countdown2}\n\n❌ فحصت {len(MARKETS)} سوق في {elapsed}ث - لا يوجد موثوق حاليا\nجرب بعد 5 دقايق", call.message.chat.id, loading.message_id)
    else:
        best = goldens[0]
        top_banner = f"🔥 TOP وقت بنوك - {countdown2} متبقي 🔥\n" if is_top2 else f"🏦 {status2} - {countdown2}\n"
        text = f"{top_banner}\n🏆 أفضل صفقة موثوقة {best[0]}% 🏆\n{best[1]}\n"
        text += f"━━━━━━━━━━━━\n🔥🔥 {len(goldens)} فرص مرتبة حسب الثقة في {elapsed}ث 🔥🔥\n\n"
        for i, (p, detail) in enumerate(goldens, 1):
            crown = "👑" if i==1 else f"{i}."
            text += f"{crown} {detail}\n"
        text += f"\n💡 نصيحة: ادخل رقم 1 فقط - أعلى ثقة"
        text += f"\n\n🏦 {status2} | ⏰ {countdown2}"
        bot.edit_message_text(text, call.message.chat.id, loading.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_"))
def choose_market(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    name = call.data.replace("market_", "")
    user_data[call.from_user.id] = MARKETS[name], name
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔍 فحص شامل H1+15m+5m", callback_data="time_ALL"))
    markup.add(InlineKeyboardButton("5m فقط", callback_data="time_5"), InlineKeyboardButton("15m فقط", callback_data="time_15"))
    status, countdown, _, _ = get_bank_counter()
    bot.send_message(call.message.chat.id, f"📊 اخترت {name}\n🏦 {status}\n⏰ {countdown}\n\nاختر نوع الفحص:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("time_"))
def choose_time(call):
    if call.from_user.id not in authorized: return
    user_id = call.from_user.id
    now = time.time()
    if user_id in last_request and now - last_request[user_id] < 3:
        bot.answer_callback_query(call.id, "⏳ انتظر 3 ثواني")
        return
    last_request[user_id] = now
    bot.answer_callback_query(call.id)
    mode = call.data.replace("time_", "")
    symbol, name = user_data.get(user_id, (None, None))
    if not symbol: return
    status, countdown, is_top, _ = get_bank_counter()
    loading = bot.send_message(call.message.chat.id, f"🏦 {status}\n⏰ {countdown}\n\n⏳ جاري فحص {name}...")
    if mode == "ALL":
        direction, percent, details = get_confluence_signal(symbol)
        status2, countdown2, _, _ = get_bank_counter()
        if direction == "NO_TRADE":
            bot.edit_message_text(f"📊 {name}\n🏦 {status2} | ⏰ {countdown2}\n\n{details}", call.message.chat.id, loading.message_id)
            return
        emoji = "🟢 BUY صعود" if direction == "BUY" else "🔴 SELL هبوط"
        top_note = "\n🔥 TOP وقت بنوك - إشارة قوية" if is_top else ""
        bot.edit_message_text(f"📊 {name}\n{emoji}\n💪 ثقة: {percent}%\n🏦 {status2} | ⏰ {countdown2}{top_note}\n\n{details}", call.message.chat.id, loading.message_id)
    else:
        tf_map = {"5": Interval.INTERVAL_5_MINUTES, "15": Interval.INTERVAL_15_MINUTES}
        d, p = get_tf_signal(symbol, tf_map[mode])
        status2, countdown2, _, _ = get_bank_counter()
        bot.edit_message_text(f"📊 {name} {mode}m\n🏦 {status2} | ⏰ {countdown2}\n{'🟢 BUY' if d=='BUY' else '🔴 SELL'}\n💪 {p}%\n\n{'✅ ادخل' if p>=70 else '❌ لا تدخل'}", call.message.chat.id, loading.message_id)

app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Live! - Real Markets + Bank Counter"
@app.route('/health')
def health(): return "OK"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

threading.Thread(target=run_flask, daemon=True).start()
bot.remove_webhook()
time.sleep(2)
while True:
    try:
        bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)
