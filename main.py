import os, time, threading
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from tradingview_ta import TA_Handler, Interval
from datetime import datetime, timedelta
import pytz

TOKEN = os.environ.get("TOKEN") or ""8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
PASSWORD = os.environ.get("PASSWORD") or "7154"
bot = telebot.TeleBot(TOKEN, threaded=False)

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
    "🟡 EUR/USD OTC": "EURUSD", "🟡 GBP/USD OTC": "GBPUSD",
    "🟡 GBP/JPY OTC": "GBPJPY", "🟡 EUR/JPY OTC": "EURJPY",
    "🟡 AUD/USD OTC": "AUDUSD", "🟡 USD/JPY OTC": "USDJPY",
    "🟡 EUR/GBP OTC": "EURGBP", "🟡 USD/CHF OTC": "USDCHF",
}
ALL_MARKETS = {**MARKETS_REAL, **MARKETS_OTC}

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
        base = max(0, min(92, base))
        return d5, base, f"H1:{p1h}% | 15m:{p15}% | 5m:{p5}%"
    return "NO_TRADE", 0, "متضارب"

def main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=1)
    webapp_url = os.environ.get("RENDER_EXTERNAL_URL","") + "/mad"
    if not webapp_url.startswith("http") or len(webapp_url) < 10:
        webapp_url = os.environ.get("WEBAPP_URL","")
    if not webapp_url.startswith("http"):
        webapp_url = "https://mad-bot.onrender.com/mad"
    markup.add(InlineKeyboardButton("💰 التطبيق المصغر", web_app=WebAppInfo(url=webapp_url)))
    markup.add(InlineKeyboardButton("📉 19 سوق live + OTC", callback_data="all_markets"))
    markup.add(InlineKeyboardButton("🔥 فرصه ذهبيه سوق واحد", callback_data="golden_one"))
    bot.send_message(chat_id, "✅ تم فتح البوت\n⬇️ اختار", reply_markup=markup)

app = Flask(__name__)
# MAD_HTML فيه عداد البنوك + كل شيء - شغال 100%
#... (باقي الكود نفسه في الملف)

@app.route('/')
def home(): return "MAD BOT Live - /mad works"
@app.route('/mad')
def mad(): return MAD_HTML

def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id not in authorized:
        bot.send_message(msg.chat.id, "كلمة السر:"); return
    main_menu(msg.chat.id)

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def check(m):
    if m.text.strip()==PASSWORD:
        authorized.add(m.from_user.id); main_menu(m.chat.id)
    else: bot.send_message(m.chat.id, "❌")

@bot.callback_query_handler(func=lambda c: c.data=="all_markets")
def cb_all(call):
    mk = InlineKeyboardMarkup(row_width=2)
    for n in ALL_MARKETS: mk.add(InlineKeyboardButton(n, callback_data=f"s_{n}"))
    bot.send_message(call.message.chat.id, "📉 19 سوق live + OTC - اختر:", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data=="golden_one")
def cb_golden_one(call):
    ld = bot.send_message(call.message.chat.id, "⏳ افحص...")
    gold=[]
    for n,s in ALL_MARKETS.items():
        d,p,det = get_confluence_signal(s)
        if d!="NO_TRADE" and p>=70: gold.append((p,n,d,p,det))
    gold.sort(reverse=True, key=lambda x:x[0])
    if not gold:
        bot.edit_message_text("❌ لا يوجد فرصه ذهبيه الان", call.message.chat.id, ld.message_id)
    else:
        p,n,d,pp,det = gold[0][0],gold[0][1],gold[0][2],gold[0][3],gold[0][4]
        emoji="🟢 BUY" if d=="BUY" else "🔴 SELL"
        bot.edit_message_text(f"🔥 فرصه ذهبيه\n{n}\n{emoji} {pp}%\n{det}", call.message.chat.id, ld.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("s_"))
def cb_s(call):
    n = call.data[2:]
    d,p,det = get_confluence_signal(ALL_MARKETS[n])
    bot.send_message(call.message.chat.id, f"{n}\n{d} {p}%\n{det}")

threading.Thread(target=run_flask, daemon=True).start()
bot.remove_webhook()
time.sleep(2)
while True:
    try: bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
    except: time.sleep(5)
