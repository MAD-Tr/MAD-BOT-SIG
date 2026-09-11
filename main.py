import os
import time
import threading
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

MARKETS_OTC = {
    "🟡 EUR/USD OTC": "EURUSD",
    "🟡 GBP/USD OTC": "GBPUSD",
    "🟡 EUR/JPY OTC": "EURJPY",
}

user_data = {}
last_request = {}
authorized = set()

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

# === التعديل الوحيد هنا: صار 30 ثانية للتجربة ===
def get_confluence_signal(symbol):
    # نستخدم 1m و 5m و 15m كتمثيل للثواني لان TradingView ما عنده ثواني
    d1, p1 = get_tf_signal(symbol, Interval.INTERVAL_1_MINUTE) # نمثلها 15ث
    d5, p5 = get_tf_signal(symbol, Interval.INTERVAL_5_MINUTES) # نمثلها 30ث
    d15, p15 = get_tf_signal(symbol, Interval.INTERVAL_15_MINUTES) # نمثلها 1د

    if d1 == d5 == d15 and d1!= "ERROR":
        base = int(p1*0.40 + p5*0.35 + p15*0.25)
        diff = max(p1, p5, p15) - min(p1, p5, p15)
        if diff > 20: base -= 10
        elif diff > 12: base -= 4
        if min(p1, p5, p15) < 68: base -= 10
        if base > 92: base = 92
        if base < 0: base = 0

        if base >= 85:
            decision = "🔥🔥 TOP ثواني - ادخل الان بداية الشمعة"
        elif base >= 78:
            decision = "✅ ممتاز ثواني - ادخل 30ث"
        elif base >= 70:
            decision = "✅ جيد ثواني - 30ث"
        else:
            decision = "⚠️ ضعيف لا تدخل"

        return d1, base, f"15s~{p1}% | 30s~{p5}% | 1m:{p15}%\n{decision}\n⏱️ المدة: 30 ثانية\n⏰ ادخل بداية الشمعة الجديدة!"

    return "NO_TRADE", 0, f"1m:{p1}% {d1} | 5m:{p5}% {d5} | 15m:{p15}% {d15}\n\n❌ متضارب ثواني"

def main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("⚡ فحص ثواني 22 سوق حقيقي - 30ث", callback_data="golden"))
    markup.add(InlineKeyboardButton("🌙 فحص OTC ثواني - 30ث", callback_data="golden_otc"))
    markup.add(InlineKeyboardButton("📊 فحص سوق واحد - ثواني", callback_data="single"))
    markup.add(InlineKeyboardButton("📊 فحص سوق واحد OTC - ثواني", callback_data="single_otc"))
    bot.send_message(chat_id, "⚡ وضع الثواني التجريبي - 30 ثانية\nاختار:", reply_markup=markup)

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
        bot.send_message(m.chat.id, "✅ تم فتح البوت - وضع 30 ثانية")
        main_menu(m.chat.id)
    else:
        bot.send_message(m.chat.id, "❌ كلمة سر غلط")

def do_scan(markets_dict, chat_id, loading_id, is_otc=False):
    goldens = []
    start_t = time.time()
    for name, sym in markets_dict.items():
        try:
            d, p, details = get_confluence_signal(sym)
            if d!= "NO_TRADE" and p >= 70:
                emoji = "🟢 BUY" if d=="BUY" else "🔴 SELL"
                goldens.append((p, f"{emoji} {name} - {p}%\n{details}\n"))
        except: continue
    goldens.sort(key=lambda x: x[0], reverse=True)
    elapsed = round(time.time() - start_t, 1)
    label = "OTC" if is_otc else "حقيقي"
    if not goldens:
        bot.edit_message_text(f"❌ فحصت {len(markets_dict)} سوق {label} في {elapsed}ث - لا يوجد موثوق ثواني\nجرب بعد 30ث", chat_id, loading_id)
    else:
        best = goldens[0]
        text = f"🏆 أفضل صفقة {label} ثواني {best[0]}% 🏆\n{best[1]}\n"
        text += f"━━━━━━━━━━━━\n⚡ {len(goldens)} فرص ثواني في {elapsed}ث\n\n"
        for i, (p, detail) in enumerate(goldens, 1):
            crown = "👑" if i==1 else f"{i}."
            text += f"{crown} {detail}\n"
        text += f"\n⏰ ادخل بداية الشمعة القادمة - مدة 30ث"
        bot.edit_message_text(text, chat_id, loading_id)

@bot.callback_query_handler(func=lambda c: c.data=="golden")
def golden(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id, "⏳ افحص 22 سوق ثواني...")
    loading = bot.send_message(call.message.chat.id, f"⏳ افحص {len(MARKETS)} سوق ثواني...")
    do_scan(MARKETS, call.message.chat.id, loading.message_id, False)

@bot.callback_query_handler(func=lambda c: c.data=="golden_otc")
def golden_otc(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id, "⏳ افحص OTC ثواني...")
    loading = bot.send_message(call.message.chat.id, f"🌙 افحص {len(MARKETS_OTC)} سوق OTC ثواني...")
    do_scan(MARKETS_OTC, call.message.chat.id, loading.message_id, True)

@bot.callback_query_handler(func=lambda c: c.data=="single")
def single(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup(row_width=2)
    for name in MARKETS:
        markup.add(InlineKeyboardButton(name, callback_data=f"market_{name}"))
    bot.send_message(call.message.chat.id, "اختر السوق الحقيقي:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data=="single_otc")
def single_otc(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup(row_width=2)
    for name in MARKETS_OTC:
        markup.add(InlineKeyboardButton(name, callback_data=f"market_otc_{name}"))
    bot.send_message(call.message.chat.id, "اختر سوق OTC:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_"))
def choose_market(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    is_otc = call.data.startswith("market_otc_")
    name = call.data.replace("market_otc_", "").replace("market_", "")
    markets = MARKETS_OTC if is_otc else MARKETS
    if name not in markets: return
    symbol = markets[name]
    loading = bot.send_message(call.message.chat.id, f"⏳ جاري فحص {name} ثواني...")
    d, p, details = get_confluence_signal(symbol)
    if d == "NO_TRADE":
        bot.edit_message_text(f"📊 {name} ثواني\n{details}", call.message.chat.id, loading.message_id)
    else:
        emoji = "🟢 BUY" if d=="BUY" else "🔴 SELL"
        bot.edit_message_text(f"⚡ {name} ثواني\n{emoji}\n💪 ثقة: {p}%\n\n{details}", call.message.chat.id, loading.message_id)

app = Flask(__name__)
@app.route('/')
def home(): return "Bot 30s Live!"
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
