import os, time, threading
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from tradingview_ta import TA_Handler, Interval
from datetime import datetime, timedelta
import pytz

TOKEN = "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
PASSWORD = os.environ.get("PASSWORD") or "7154"

bot = None
if TOKEN and ":" in TOKEN:
    try:
        bot = telebot.TeleBot(TOKEN, threaded=False)
    except Exception as e:
        print(f"Bot init failed: {e}")
        bot = None
else:
    print("WARNING: TOKEN not set")

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

MAD_HTML = '''<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MAD BOT</title><style>*{box-sizing:border-box;margin:0;padding:0}body{background:#000;color:#fff;font-family:Arial;direction:rtl}.header{background:#111;padding:14px;text-align:center;border-bottom:2px solid #ff0000}.logo{color:#ff0000;font-size:20px;font-weight:900}.bank-bar{background:linear-gradient(135deg,#111 0%,#1a0000 100%);border:2px solid #ff0000;border-radius:12px;margin:10px;padding:12px;text-align:center}.bank-time{font-size:26px;color:#ff0000;font-weight:900}.card{background:#111;border:1px solid #222;border-radius:12px;padding:12px;margin:10px}.tabs{display:flex;gap:8px}.tab{flex:1;padding:10px;border:none;border-radius:8px;font-weight:900}.active{background:#ff0000;color:#fff}.inactive{background:#222;color:#888}select{width:100%;padding:12px;background:#000;color:#fff;border:1px solid #ff0000;border-radius:8px}.signal{border:2px solid #ff0000;border-radius:12px;padding:16px;text-align:center;background:#0a0a0a}.buy{color:#00ff00;font-size:28px;font-weight:900}.sell{color:#ff0000;font-size:28px;font-weight:900}.btn{background:#ff0000;padding:14px;border:none;border-radius:10px;color:#fff;font-size:16px;font-weight:900;width:100%;margin:10px 0}</style></head><body><div class="header"><div class="logo">MAD BOT</div></div><div class="bank-bar"><div style="font-size:12px;color:#888">البنوك الحقيقية</div><div class="bank-time" id="countdown">--:--:--</div><div class="bank-status" id="bankStatus"></div><div style="font-size:10px;color:#666" id="bankNext"></div></div><div class="card"><div class="tabs"><button class="tab active" id="tabReal" onclick="switchTab('real')">حقيقي (19)</button><button class="tab inactive" id="tabOtc" onclick="switchTab('otc')">OTC (8)</button></div><div id="realSection"><select id="pairReal"><option>🇪🇺/🇺🇸 EUR/USD</option><option>🇬🇧/🇺🇸 GBP/USD</option><option>🇺🇸/🇯🇵 USD/JPY</option><option>🇦🇺/🇺🇸 AUD/USD</option><option>🇺🇸/🇨🇦 USD/CAD</option><option>🇪🇺/🇯🇵 EUR/JPY</option><option>🇨🇦/🇯🇵 CAD/JPY</option><option>🇪🇺/🇬🇧 EUR/GBP</option><option>🇦🇺/🇯🇵 AUD/JPY</option><option>🇳🇿/🇺🇸 NZD/USD</option><option>🇪🇺/🇨🇭 EUR/CHF</option><option>🇬🇧/🇯🇵 GBP/JPY</option><option>🇦🇺/🇨🇦 AUD/CAD</option><option>🇪🇺/🇦🇺 EUR/AUD</option><option>🇬🇧/🇨🇭 GBP/CHF</option><option>🇺🇸/🇨🇭 USD/CHF</option><option>🇪🇺/🇨🇦 EUR/CAD</option><option>🇦🇺/🇨🇭 AUD/CHF</option><option>🇬🇧/🇦🇺 GBP/AUD</option></select></div><div id="otcSection" style="display:none"><select id="pairOtc"><option>🟡 EUR/USD OTC</option><option>🟡 GBP/USD OTC</option><option>🟡 GBP/JPY OTC</option><option>🟡 EUR/JPY OTC</option><option>🟡 AUD/USD OTC</option><option>🟡 USD/JPY OTC</option><option>🟡 EUR/GBP OTC</option><option>🟡 USD/CHF OTC</option></select></div></div><div class="card"><div class="signal"><div id="pairName">EUR/USD</div><div id="dir" class="sell">SELL</div></div></div><button class="btn" onclick="getSignal()">GET SIGNAL</button><script>function updateBankCountdown(){const now=new Date();const nyNow=new Date(now.toLocaleString("en-US",{timeZone:"America/New_York"}));const h=nyNow.getHours();let targetHour,status,nextName;if(h>=20||h<2){targetHour=2;status="🌙 آسيا";nextName="لندن تفتح بعد";}else if(h>=2&&h<7){targetHour=7;status="🇬🇧 لندن";nextName="نيويورك تفتح بعد";}else if(h>=7&&h<12){status="🔥 لندن+نيويورك TOP";nextName="آسيا تفتح بعد";targetHour=20;}else{status="🇺🇸 نيويورك";nextName="آسيا تفتح بعد";targetHour=20;}let target=new Date(nyNow);target.setHours(targetHour,0,0,0);if(target<=nyNow)target.setDate(target.getDate()+1);const diff=target-nyNow;const hh=String(Math.floor(diff/1000/3600)).padStart(2,'0');const mm=String(Math.floor((diff/1000%3600)/60)).padStart(2,'0');const ss=String(Math.floor(diff/1000%60)).padStart(2,'0');document.getElementById('countdown').innerText=`${hh}:${mm}:${ss}`;document.getElementById('bankStatus').innerText=status;document.getElementById('bankNext').innerText=`${nextName}: ${hh}:${mm}:${ss}`;}let tab='real';function switchTab(t){tab=t;document.getElementById('tabReal').className=t=='real'?'tab active':'tab inactive';document.getElementById('tabOtc').className=t=='otc'?'tab active':'tab inactive';document.getElementById('realSection').style.display=t=='real'?'block':'none';document.getElementById('otcSection').style.display=t=='otc'?'block':'none';}function getSignal(){const isBuy=Math.random()>0.5;document.getElementById('dir').innerHTML=isBuy?'BUY':'SELL';document.getElementById('dir').className=isBuy?'buy':'sell';}updateBankCountdown();setInterval(updateBankCountdown,1000);</script></body></html>'''

@app.route('/')
def home(): return "MAD BOT Live"
@app.route('/mad')
def mad(): return MAD_HTML
@app.route('/health')
def health(): return "OK"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))

if bot:
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
        bot.send_message(call.message.chat.id, "📉 19 سوق live + OTC:", reply_markup=mk)
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

def run_bot():
    if not bot: return
    try:
        bot.remove_webhook(); time.sleep(1)
        bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(e); time.sleep(5); run_bot()

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    if bot:
        threading.Thread(target=run_bot, daemon=True).start()
    while True: time.sleep(60)
