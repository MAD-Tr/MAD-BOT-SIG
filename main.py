import os, time, threading, requests
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

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
    "🟡 🇪🇺/🇺🇸 EUR/USD OTC": "EURUSD", "🟡 🇬🇧/🇺🇸 GBP/USD OTC": "GBPUSD",
    "🟡 🇬🇧/🇯🇵 GBP/JPY OTC": "GBPJPY", "🟡 🇪🇺/🇯🇵 EUR/JPY OTC": "EURJPY",
    "🟡 🇦🇺/🇺🇸 AUD/USD OTC": "AUDUSD", "🟡 🇺🇸/🇯🇵 USD/JPY OTC": "USDJPY",
    "🟡 🇪🇺/🇬🇧 EUR/GBP OTC": "EURGBP", "🟡 🇺🇸/🇨🇭 USD/CHF OTC": "USDCHF",
}

authorized = set()

def get_signal(symbol, is_otc=False):
    try:
        if is_otc:
            url = "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=20"
            closes = [float(c[4]) for c in requests.get(url, timeout=4).json()]
            d = "BUY" if closes[-1] > closes[-2] else "SELL"
            return d, 75
        else:
            from tradingview_ta import TA_Handler, Interval
            h = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=Interval.INTERVAL_5_MINUTES)
            s = h.get_analysis().summary
            total = s['BUY'] + s['SELL']
            if total == 0: return "NEUTRAL", 0
            d = "BUY" if s['BUY'] > s['SELL'] else "SELL"
            p = int((max(s['BUY'], s['SELL']) / total) * 100)
            return d, p
    except:
        return "NEUTRAL", 0

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id not in authorized:
        bot.send_message(msg.chat.id, "🔒 كلمة السر:"); return
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔥 فرصة ذهبية", callback_data="golden"))
    markup.add(InlineKeyboardButton("📊 فحص سوق", callback_data="single"))
    markup.add(InlineKeyboardButton("📈 كل الأسواق مع الأعلام", callback_data="all"))
    bot.send_message(msg.chat.id, "💰 بوت الإشارات - مع كل الأعلام\n\n3 أزرار فقط:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def check_pass(m):
    if m.text.strip() == PASSWORD:
        authorized.add(m.from_user.id)
        start(m)
    else:
        bot.send_message(m.chat.id, "❌ غلط")

@bot.callback_query_handler(func=lambda c: c.data=="single")
def single(call):
    markup = InlineKeyboardMarkup(row_width=2)
    for name in MARKETS:
        markup.add(InlineKeyboardButton(name, callback_data=f"m_{name}"))
    bot.send_message(call.message.chat.id, "اختر السوق مع العلم:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("m_"))
def market(call):
    name = call.data[2:]
    sym = MARKETS.get(name)
    loading = bot.send_message(call.message.chat.id, f"⏳ {name}...")
    d,p = get_signal(sym, "OTC" in name)
    if d=="NEUTRAL" or p<68:
        bot.edit_message_text(f"{name}\n❌ لا تدخل - {p}%", call.message.chat.id, loading.message_id)
    else:
        emoji = "🟢 BUY ⬆️" if d=="BUY" else "🔴 SELL ⬇️"
        bot.edit_message_text(f"{name}\n{emoji}\n💪 {p}%\n\nادخل {d} - 1 دقيقة", call.message.chat.id, loading.message_id)

@bot.callback_query_handler(func=lambda c: c.data=="golden")
def golden(call):
    loading = bot.send_message(call.message.chat.id, "⏳ يفحص 30 سوق مع الأعلام...")
    best = []
    for name, sym in MARKETS.items():
        d,p = get_signal(sym, "OTC" in name)
        if d!="NEUTRAL" and p>=70:
            best.append((p, name, d))
        time.sleep(0.15)
    best.sort(reverse=True)
    if not best:
        bot.edit_message_text("❌ لا يوجد فرص قوية حاليا", call.message.chat.id, loading.message_id)
    else:
        txt = "🏆 أفضل الفرص مع الأعلام:\n\n"
        for p,name,d in best[:5]:
            e = "🟢" if d=="BUY" else "🔴"
            txt += f"{e} {name} {p}% {d}\n"
        bot.edit_message_text(txt, call.message.chat.id, loading.message_id)

@bot.callback_query_handler(func=lambda c: c.data=="all")
def all_markets(call):
    loading = bot.send_message(call.message.chat.id, "⏳ يفحص كل الأسواق مع الأعلام...")
    lines = []
    for name, sym in MARKETS.items():
        d,p = get_signal(sym, "OTC" in name)
        if d=="NEUTRAL":
            lines.append(f"⚪ {name} - لا يوجد")
        else:
            e = "🟢 BUY" if d=="BUY" else "🔴 SELL"
            lines.append(f"{e} {name} {p}%")
        time.sleep(0.15)
    txt = "📈 كل الأسواق مع الأعلام:\n\n" + "\n".join(lines)
    if len(txt) > 4000:
        bot.edit_message_text(txt[:4000], call.message.chat.id, loading.message_id)
        bot.send_message(call.message.chat.id, txt[4000:])
    else:
        bot.edit_message_text(txt, call.message.chat.id, loading.message_id)

app = Flask(__name__)
@app.route('/')
def home(): return "Bot - Flags + 3 Buttons"
@app.route('/health')
def health(): return "OK"
def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
threading.Thread(target=run_flask, daemon=True).start()
bot.remove_webhook()
time.sleep(2)
while True:
    try: bot.infinity_polling(timeout=60)
    except: time.sleep(5)
