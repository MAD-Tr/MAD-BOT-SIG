import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval

# استدعاء القيم من متغيرات البيئة تلقائياً
TOKEN = os.environ.get("TOKEN") or "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
PASSWORD = os.environ.get("PASSWORD") or "7154"

bot = telebot.TeleBot(TOKEN, threaded=False)

# القائمة المحددة المقتصرة على الـ 13 زوجاً فقط
MARKETS = {
    "🇪🇺/🇺🇸 EUR/USD": "EURUSD",
    "🇺🇸/🇯🇵 USD/JPY": "USDJPY",
    "🇦🇺/🇺🇸 AUD/USD": "AUDUSD",
    "🇺🇸/🇨🇦 USD/CAD": "USDCAD",
    "🇪🇺/🇯🇵 EUR/JPY": "EURJPY",
    "🇨🇦/🇯🇵 CAD/JPY": "CADJPY",
    "🇦🇺/🇯🇵 AUD/JPY": "AUDJPY",
    "🇪🇺/🇨🇭 EUR/CHF": "EURCHF",
    "🇦🇺/🇨🇦 AUD/CAD": "AUDCAD",
    "🇪🇺/🇦🇺 EUR/AUD": "EURAUD",
    "🇺🇸/🇨🇭 USD/CHF": "USDCHF",
    "🇪🇺/🇨🇦 EUR/CAD": "EURCAD",
    "🇦🇺/🇨🇭 AUD/CHF": "AUDCHF",
    "🇨🇦/🇨🇭 CAD/CHF": "CADCHF",
}

user_data = {}
last_request = {}
authorized = set()

# متغيرات حالة التنبيه التلقائي
auto_alert_active = False
auto_alert_stop_time = None

def fetch_tf_data(symbol, interval):
    """جلب بيانات التحليل والمؤشرات التفصيلية"""
    try:
        h = TA_Handler(
            symbol=symbol,
            screener="forex",
            exchange="FX",
            interval=interval
        )
        analysis = h.get_analysis()
        return analysis.summary, analysis.indicators
    except Exception:
        return None, None

def analyze_confluence(symbol):
    """تحليل 3 أطر زمنية مع تصفية الدخول الفني"""
    s5, ind5 = fetch_tf_data(symbol, Interval.INTERVAL_5_MINUTES)
    s15, ind15 = fetch_tf_data(symbol, Interval.INTERVAL_15_MINUTES)
    s1h, ind1h = fetch_tf_data(symbol, Interval.INTERVAL_1_HOUR)

    if not s5 or not s15 or not s1h:
        return "ERROR", 0, "❌ خطأ في جلب بيانات السوق", False

    d5 = "BUY" if s5['BUY'] > s5['SELL'] else "SELL"
    d15 = "BUY" if s15['BUY'] > s15['SELL'] else "SELL"
    d1h = "BUY" if s1h['BUY'] > s1h['SELL'] else "SELL"

    # شرط الاتجاه الموحد بين الفريمات
    if d5 == d15 == d1h:
        p5 = int((max(s5['BUY'], s5['SELL']) / max(1, s5['BUY'] + s5['SELL'])) * 100)
        p15 = int((max(s15['BUY'], s15['SELL']) / max(1, s15['BUY'] + s15['SELL'])) * 100)
        p1h = int((max(s1h['BUY'], s1h['SELL']) / max(1, s1h['BUY'] + s1h['SELL'])) * 100)

        rsi_5m = ind5.get("RSI", 50)
        stoch_k = ind5.get("Stoch.K", 50)
        stoch_d = ind5.get("Stoch.D", 50)

        confidence = int((p5 + p15 + p1h) / 3)
        quality_msg = ""
        is_golden = False

        if d5 == "BUY" and rsi_5m < 50 and stoch_k > stoch_d:
            quality_msg = "🔥 دخول ذهبي مؤكد (ارتداد صاعد مع الاتجاه)"
            confidence = min(92, confidence + 8)
            is_golden = True
        elif d5 == "SELL" and rsi_5m > 50 and stoch_k < stoch_d:
            quality_msg = "🔥 دخول ذهبي مؤكد (ارتداد هابط مع الاتجاه)"
            confidence = min(92, confidence + 8)
            is_golden = True
        else:
            quality_msg = "⚠️ اتجاه متوافق ولكن الزخم قريب من التشبع"

        now_time = datetime.now()
        entry_time = now_time.strftime("%H:%M:%S")
        expiry_time = (now_time + timedelta(minutes=15)).strftime("%H:%M:%S")

        details = (
            f"⏱️ **توقيت التقرير:** `{entry_time}`\n"
            f"⏳ **مدة الصفقة المفضلة:** 15 دقيقة (تغلق `{expiry_time}`)\n"
            f"📊 **قوة الاتجاه:** H1:{p1h}% | 15m:{p15}% | 5m:{p5}%\n"
            f"🎯 **التقييم:** {quality_msg}"
        )
        return d5, confidence, details, is_golden

    return "NO_TRADE", 0, "❌ الاتجاه متضارب بين الفريمات الثلاثة (سوق متذبذب)", False

def process_single_market(item):
    name, sym = item
    try:
        d, p, details, is_golden = analyze_confluence(sym)
        if d != "NO_TRADE" and p >= 75:
            emoji = "🟢 CALL (صعود)" if d == "BUY" else "🔴 PUT (هبوط)"
            return f"{emoji} **{name}**\n💪 نسبة القوة: **{p}%**\n{details}\n"
    except Exception:
        pass
    return None

def auto_scanner_loop():
    """خيط خلفي يعمل دائماً لفحص السوق قبل بداية الشمعة الجديدة بدقيقة"""
    global auto_alert_active, auto_alert_stop_time
    already_scanned_minute = -1

    while True:
        try:
            now = datetime.now()
            
            # التحقق من انتهاء مهلة 24 ساعة
            if auto_alert_active and auto_alert_stop_time and now >= auto_alert_stop_time:
                auto_alert_active = False
                for user_id in authorized:
                    bot.send_message(user_id, "ℹ️ **انتهت مدة التنبيه التلقائي (24 ساعة).**\nيمكنك إعادة إشعاله من القائمة الرئيسية.", parse_mode="Markdown")

            # الفحص فقط إذا كان التنبيه مفعلاً وفي الدقائق 14, 29, 44, 59
            if auto_alert_active and now.minute in [14, 29, 44, 59]:
                if now.minute != already_scanned_minute:
                    already_scanned_minute = now.minute
                    
                    with ThreadPoolExecutor(max_workers=10) as executor:
                        results = list(executor.map(process_single_market, MARKETS.items()))
                    
                    goldens = [res for res in results if res is not None]

                    if goldens:
                        alert_msg = f"🔔 **تنبيه عاجل: فرصة قادمة خلال 60 ثانية!** 🔔\n\n" + "\n---\n".join(goldens) + "\n\n👉 **افتح المنصة وتجهز لدخول الشمعة الجديدة (15m)!**"
                        for user_id in authorized:
                            bot.send_message(user_id, alert_msg, parse_mode="Markdown")
            else:
                if now.minute not in [14, 29, 44, 59]:
                    already_scanned_minute = -1

        except Exception as e:
            print(f"Auto scanner error: {e}")
        
        time.sleep(10)

def main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=1)
    
    status_icon = "🟢 (مفعل)" if auto_alert_active else "🔴 (معطل)"
    if auto_alert_active:
        markup.add(InlineKeyboardButton(f"🔕 إيقاف التنبيه التلقائي {status_icon}", callback_data="toggle_auto"))
    else:
        markup.add(InlineKeyboardButton(f"🔔 تشغيل التنبيه التلقائي 24h {status_icon}", callback_data="toggle_auto"))
        
    markup.add(InlineKeyboardButton(f"🔥 فحص شامل يدوي ({len(MARKETS)} سوق)", callback_data="golden"))
    markup.add(InlineKeyboardButton("📊 فحص سوق واحد", callback_data="single"))
    
    bot.send_message(chat_id, "⚙️ **لوحة تحكم البوت (Triple TF + Auto Scanner)**\nاختر الخيار المناسب:", parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id not in authorized:
        bot.send_message(msg.chat.id, "🔒 أدخل كلمة السر لفتح البوت:")
        return
    main_menu(msg.chat.id)

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def check_pass(m):
    if m.text.strip() == PASSWORD:
        authorized.add(m.from_user.id)
        bot.send_message(m.chat.id, "✅ تم تسجيل الدخول بنجاح!")
        main_menu(m.chat.id)
    else:
        bot.send_message(m.chat.id, "❌ كلمة السر غير صحيحة")

@bot.callback_query_handler(func=lambda c: c.data == "toggle_auto")
def toggle_auto(call):
    global auto_alert_active, auto_alert_stop_time
    if call.from_user.id not in authorized: return
    
    auto_alert_active = not auto_alert_active
    
    if auto_alert_active:
        auto_alert_stop_time = datetime.now() + timedelta(hours=24)
        bot.answer_callback_query(call.id, "✅ تم تشغيل التنبيه التلقائي لمدة 24 ساعة")
        bot.send_message(call.message.chat.id, f"🟢 **تم تفعيل التنبيه التلقائي!**\nسيقوم البوت بمراقبة {len(MARKETS)} سوقاً وإرسال تنبيه قبل إغلاق أي شمعة 15m بدقيقة واحدة عند وجود فرصة ذهبية.", parse_mode="Markdown")
    else:
        auto_alert_stop_time = None
        bot.answer_callback_query(call.id, "🛑 تم إيقاف التنبيه التلقائي")
        bot.send_message(call.message.chat.id, "🔴 **تم إيقاف التنبيه التلقائي.**\nيمكنك الآن إجراء الفحص اليدوي فقط.", parse_mode="Markdown")
        
    main_menu(call.message.chat.id)

@bot.callback_query_handler(func=lambda c: c.data=="single")
def single(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup(row_width=2)
    for name in MARKETS:
        markup.add(InlineKeyboardButton(name, callback_data=f"market_{name}"))
    bot.send_message(call.message.chat.id, "اختر السوق للفحص المباشر:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data=="golden")
def golden(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id, "⚡ جاري الفحص اليدوي المباشر...")
    loading = bot.send_message(call.message.chat.id, f"⚡ جاري فحص {len(MARKETS)} سوق عبر المعالجة المتوازية...")
    
    start_t = time.time()
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(process_single_market, MARKETS.items()))
        
    goldens = [res for res in results if res is not None]
    elapsed = round(time.time() - start_t, 1)

    if not goldens:
        bot.edit_message_text(f"❌ تم فحص {len(MARKETS)} سوق في {elapsed} ثانية.\nلا توجد صفقات عالية الجودة متطابقة حالياً.", call.message.chat.id, loading.message_id)
    else:
        text = f"🔥🔥 **نتائج الفحص اليدوي ({len(goldens)} فرصة - {elapsed}ث)** 🔥🔥\n\n" + "\n---\n".join(goldens)
        bot.edit_message_text(text, call.message.chat.id, loading.message_id, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_"))
def choose_market(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    name = call.data.replace("market_", "")
    user_data[call.from_user.id] = MARKETS[name], name
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔍 فحص الاتجاه والزخم H1+15m+5m", callback_data="time_ALL"))
    bot.send_message(call.message.chat.id, f"السوق المحدد: **{name}**", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "time_ALL")
def choose_time(call):
    if call.from_user.id not in authorized: return
    user_id = call.from_user.id
    now = time.time()
    if user_id in last_request and now - last_request[user_id] < 3:
        bot.answer_callback_query(call.id, "⏳ انتظر 3 ثوانٍ بين الطلبات")
        return
    last_request[user_id] = now
    bot.answer_callback_query(call.id)

    symbol, name = user_data.get(user_id, (None, None))
    if not symbol: return

    loading = bot.send_message(call.message.chat.id, f"⏳ جاري تحليل **{name}**...", parse_mode="Markdown")
    direction, percent, details, _ = analyze_confluence(symbol)

    if direction == "NO_TRADE":
        bot.edit_message_text(f"📊 **{name}**\n\n{details}", call.message.chat.id, loading.message_id, parse_mode="Markdown")
    else:
        emoji = "🟢 CALL (شراء/صعود)" if direction == "BUY" else "🔴 PUT (بيع/هبوط)"
        bot.edit_message_text(f"📊 **{name}**\nالقرار: **{emoji}**\nقوة التوافق: **{percent}%**\n\n{details}", call.message.chat.id, loading.message_id, parse_mode="Markdown")

# تشغيل خادم Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is active and running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# تشغيل الخيوط الخلفية
threading.Thread(target=run_flask, daemon=True).start()
threading.Thread(target=auto_scanner_loop, daemon=True).start()

bot.remove_webhook()
time.sleep(1)

while True:
    try:
        bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"Polling error: {e}")
        time.sleep(5)
