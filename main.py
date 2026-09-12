import os, time, threading
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval
from datetime import datetime
import pytz

TOKEN = os.environ.get("8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes")
PASSWORD = os.environ.get("PASSWORD", "7154")

# لا يوقف السيرفر لو التوكن ناقص
if not TOKEN:
    print("WARNING: TOKEN not set!")

bot = telebot.TeleBot(TOKEN, threaded=False) if TOKEN else None

MARKETS = {"🇪🇺/🇺🇸 EUR/USD": "EURUSD", "🇬🇧/🇺🇸 GBP/USD": "GBPUSD"}
MARKETS_MT5 = {"🏆 XAU/USD GOLD": "XAUUSD", "🇪🇺/🇺🇸 EUR/USD": "EURUSD"}
MARKETS_OTC = {"🟡 EUR/USD OTC": "EURUSD"}

authorized = set()
KSA_TZ = pytz.timezone("Asia/Riyadh")

def get_tf_signal(symbol, interval):
    try:
        screener = "cfd" if "XAU" in symbol else "forex"
        exchange = "OANDA" if "XAU" in symbol else "FX"
        h = TA_Handler(symbol=symbol, screener=screener, exchange=exchange, interval=interval)
        s = h.get_analysis().summary
        if s['BUY']+s['SELL']==0: return "NEUTRAL",50
        d = "BUY" if s['BUY']>s['SELL'] else "SELL"
        return d, int((max(s['BUY'],s['SELL'])/(s['BUY']+s['SELL']))*100)
    except: return "ERROR",0

def get_confluence_signal(symbol):
    d5,p5 = get_tf_signal(symbol, Interval.INTERVAL_5_MINUTES)
    d15,p15 = get_tf_signal(symbol, Interval.INTERVAL_15_MINUTES)
    d1h,p1h = get_tf_signal(symbol, Interval.INTERVAL_1_HOUR)
    if d5==d15==d1h and d5!="ERROR":
        base = int(p5*0.30 + p15*0.35 + p1h*0.35)
        return d5, base, f"H1:{p1h}% | 15m:{p15}% | 5m:{p5}%"
    return "NO_TRADE",0,f"متضارب"

def get_mt5_3targets(symbol):
    d,p,details = get_confluence_signal(symbol)
    if d=="NO_TRADE": return d,p,details,None
    price = 4348.0 if "XAU" in symbol else 1.0850
    try:
        scr = "cfd" if "XAU" in symbol else "forex"
        exc = "OANDA" if "XAU" in symbol else "FX"
        h = TA_Handler(symbol=symbol, screener=scr, exchange=exc, interval=Interval.INTERVAL_1_HOUR)
        price = h.get_analysis().indicators.get('close', price)
    except: pass
    if "XAU" in symbol:
        if d=="BUY": sl=price-13; tp1=price+7; tp2=price+14; tp3=price+27
        else: sl=price+13; tp1=price-7; tp2=price-14; tp3=price-27
    else:
        if d=="BUY": sl=price-0.0020; tp1=price+0.0010; tp2=price+0.0020; tp3=price+0.0040
        else: sl=price+0.0020; tp1=price-0.0010; tp2=price-0.0020; tp3=price-0.0040
    levels={"entry":round(price,2),"sl":round(sl,2),"tp1":round(tp1,2),"tp2":round(tp2,2),"tp3":round(tp3,2)}
    return d,p,details,levels

def main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("💰 MT5 - 3 أهداف", callback_data="mode_mt5"), InlineKeyboardButton("📉 POCKET", callback_data="mode_pocket"))
    bot.send_message(chat_id, "اختر:", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id not in authorized:
        bot.send_message(msg.chat.id, "🔒 ارسل كلمة السر:"); return
    main_menu(msg.chat.id)

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def check_pass(m):
    if m.text.strip()==PASSWORD:
        authorized.add(m.from_user.id); bot.send_message(m.chat.id, "✅ تم"); main_menu(m.chat.id)
    else: bot.send_message(m.chat.id, "❌ غلط")

@bot.callback_query_handler(func=lambda c: c.data=="mode_mt5")
def mode_mt5(call):
    markup = InlineKeyboardMarkup(row_width=2)
    for name in MARKETS_MT5: markup.add(InlineKeyboardButton(name, callback_data=f"market_mt5_{name}"))
    bot.send_message(call.message.chat.id, "💰 MT5 - الذهب أول:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data=="mode_pocket")
def mode_pocket(call):
    markup = InlineKeyboardMarkup(row_width=2)
    for name in MARKETS: markup.add(InlineKeyboardButton(name, callback_data=f"market_{name}"))
    bot.send_message(call.message.chat.id, "📉 POCKET:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_mt5_"))
def choose_mt5(call):
    name = call.data.replace("market_mt5_", ""); symbol = MARKETS_MT5[name]
    d,p,details,levels = get_mt5_3targets(symbol)
    if d=="NO_TRADE": bot.send_message(call.message.chat.id, f"📊 {name}\n{details}")
    else:
        emoji="🟢 BUY" if d=="BUY" else "🔴 SELL"
        text=f"💰 MT5 - {name} - {emoji}\n🎯 ENTRY: {levels['entry']}\n❌ SL: {levels['sl']}\n✅ TP1: {levels['tp1']} (50%)\n✅ TP2: {levels['tp2']} (30%)\n✅ TP3: {levels['tp3']} (20%)\n💪 {p}%"
        bot.send_message(call.message.chat.id, text)

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_") and "mt5" not in c.data)
def choose_market(call):
    name = call.data.replace("market_", ""); symbol = MARKETS.get(name)
    if not symbol: return
    d,p,details = get_confluence_signal(symbol)
    bot.send_message(call.message.chat.id, f"📊 {name}\n{d}\n💪 {p}%\n{details}")

app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Live!"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def run_bot():
    if not TOKEN: return
    bot.remove_webhook(); time.sleep(1)
    while True:
        try: bot.infinity_polling(skip_pending=True, timeout=60)
        except Exception as e: print(f"Bot error: {e}"); time.sleep(5)

threading.Thread(target=run_flask, daemon=True).start()
threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    run_flask()
