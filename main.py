import os, time, threading
from flask import Flask, request, jsonify
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from tradingview_ta import TA_Handler, Interval
from datetime import datetime, timedelta
import pytz

TOKEN = "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
PASSWORD = os.environ.get("PASSWORD") or "7154"

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
    "🟡 EUR/USD OTC": "EURUSD", "🟡 GBP/USD OTC": "GBPUSD",
    "🟡 GBP/JPY OTC": "GBPJPY", "🟡 EUR/JPY OTC": "EURJPY",
    "🟡 AUD/USD OTC": "AUDUSD", "🟡 USD/JPY OTC": "USDJPY",
    "🟡 EUR/GBP OTC": "EURGBP", "🟡 USD/CHF OTC": "USDCHF",
}
ALL_MARKETS = {**MARKETS_REAL, **MARKETS_OTC}
authorized = set()
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
    if not bot: return
    markup = InlineKeyboardMarkup(row_width=1)
    webapp_url = os.environ.get("RENDER_EXTERNAL_URL","") + "/mad"
    if not webapp_url.startswith("http"):
        webapp_url = "https://mad-bot.onrender.com/mad"
    markup.add(InlineKeyboardButton("💰 التطبيق المصغر", web_app=WebAppInfo(url=webapp_url)))
    markup.add(InlineKeyboardButton("📉 19 سوق live + OTC", callback_data="all_markets"))
    markup.add(InlineKeyboardButton("🔥 فرصه ذهبيه سوق واحد", callback_data="golden_one"))
    bot.send_message(chat_id, "✅ تم فتح البوت\n⬇️ اختار", reply_markup=markup)

app = Flask(__name__)
MAD_HTML = """<!DOCTYPE html>... (الكود كامل في الملف) ..."""
# باقي الكود - نفس الملف
