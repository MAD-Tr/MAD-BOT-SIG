import os, time, threading
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

def get_tf_signal_strong(symbol, interval):
    try:
        h = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=interval)
        a = h.get_analysis()
        s = a.summary
        ind = a.indicators
        rsi = ind.get('RSI', 50)
        macd = ind.get('MACD.macd', 0)
        sig = ind.get('MACD.signal', 0)
        if s['BUY']+s['SELL']==0: return "NEUTRAL", 50, rsi, macd, sig
        d = "BUY" if s['BUY']>s['SELL'] else "SELL"
        strength = int((max(s['BUY'],s['SELL'])/(s['BUY']+s['SELL']))*100)
        if d=="BUY":
            if rsi>70: strength-=15
            if macd<sig: strength-=10
        else:
            if rsi<30: strength-=15
            if macd>sig: strength-=10
        return d, max(0,strength), rsi, macd, sig
    except:
        return "ERROR",0,50,0,0

def get_strong_signal_real(symbol):
    d5,p5,r5,_,_ = get_tf_signal_strong(symbol, Interval.INTERVAL_5_MINUTES)
    d15,p15,r15,_,_ = get_tf_signal_strong(symbol, Interval.INTERVAL_15_MINUTES)
    d30,p30,r30,_,_ = get_tf_signal_strong(symbol, Interval.INTERVAL_30_MINUTES)
    if "ERROR" in [d5,d15,d30]: return "NO_TRADE",0,"❌ خطأ بيانات TradingView"
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
    d1,p1,r1,_,_ = get_tf_signal_strong(symbol, Interval.INTERVAL_1_MINUTE)
    d5,p5,r5,_,_ = get_tf_signal_strong(symbol, Interval.INTERVAL_5_MINUTES)
    d15,p15,r15,_,_ = get_tf_signal_strong(symbol, Interval.INTERVAL_15_MINUTES)
    if "ERROR" in [d1,d5,d15]: return "NO_TRADE",0,"❌ خطأ بيانات TradingView"
    if d1==d5==d15 and d1 in ["BUY","SELL"]:
        base=int(p1*0.40+p5*0.35+p15*0.25)
        diff=max(p1,p5,p15)-min(p1,p5,p15)
        if diff>20: base-=12
        elif diff>12: base-=6
        if min(p1,p5,p15)<65: base-=15
        if min(p1,p5,p15)<75: base-=7
        if r1>75 and d1=="BUY": base-=12
        if r1<25 and d1=="SELL": base-=12
        base=max(0,min(95,base))
        if base>=82:
            return d1,base,"TV OTC 1m:%s%% 5m:%s%% 15m:%s%% | RSI:%s - مباشر TradingView" % (p1,p5,p15,int(r1))
        else:
            return "NO_TRADE",base,"⚠️ OTC ضعيف %s%% - انتظر | 1m:%s%% 5m:%s%% 15m:%s%%" % (base,p1,p5,p15)
    return "NO_TRADE",0,"❌ OTC متذبذب %s/%s/%s - لا تدخل" % (d1,d5,d15)

# ... باقي الكود (main_menu, Flask, MAD_HTML مع المربع الأسود والعداد) موجود كامل في الملف فوق
# انسخ الملف كامل من الرابط عشان MAD_HTML 240 سطر
