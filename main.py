import os, time, threading, random
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval
from concurrent.futures import ThreadPoolExecutor, as_completed

TOKEN = os.environ.get("TOKEN") or "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
PASSWORD = os.environ.get("PASSWORD") or "7154"
bot = telebot.TeleBot(TOKEN, threaded=False)

MARKETS = {
    "🇪🇺/🇺🇸 EUR/USD": "EURUSD", "🇺🇸/🇯🇵 USD/JPY": "USDJPY",
    "🇦🇺/🇺🇸 AUD/USD": "AUDUSD", "🇺🇸/🇨🇦 USD/CAD": "USDCAD",
    "🇪🇺/🇯🇵 EUR/JPY": "EURJPY", "🇨🇦/🇯🇵 CAD/JPY": "CADJPY",
    "🇦🇺/🇯🇵 AUD/JPY": "AUDJPY", "🇪🇺/🇨🇭 EUR/CHF": "EURCHF",
    "🇦🇺/🇨🇦 AUD/CAD": "AUDCAD", "🇪🇺/🇦🇺 EUR/AUD": "EURAUD",
    "🇺🇸/🇨🇭 USD/CHF": "USDCHF", "🇪🇺/🇨🇦 EUR/CAD": "EURCAD",
    "🇦🇺/🇨🇭 AUD/CHF": "AUDCHF", "🇨🇦/🇨🇭 CAD/CHF": "CADCHF",
    "🥇 GOLD OTC": "GOLD",
}
MARKETS_YF = {
    "🇪🇺/🇺🇸 EUR/USD": "EURUSD=X", "🇺🇸/🇯🇵 USD/JPY": "JPY=X",
    "🇦🇺/🇺🇸 AUD/USD": "AUDUSD=X", "🇺🇸/🇨🇦 USD/CAD": "CAD=X",
    "🇪🇺/🇯🇵 EUR/JPY": "EURJPY=X", "🇨🇦/🇯🇵 CAD/JPY": "CADJPY=X",
    "🇦🇺/🇯🇵 AUD/JPY": "AUDJPY=X", "🇪🇺/🇨🇭 EUR/CHF": "EURCHF=X",
    "🇦🇺/🇨🇦 AUD/CAD": "AUDCAD=X", "🇪🇺/🇦🇺 EUR/AUD": "EURAUD=X",
    "🇺🇸/🇨🇭 USD/CHF": "CHF=X", "🇪🇺/🇨🇦 EUR/CAD": "EURCAD=X",
    "🇦🇺/🇨🇭 AUD/CHF": "AUDCHF=X", "🇨🇦/🇨🇭 CAD/CHF": "CADCHF=X",
    "🥇 GOLD OTC": "GC=F",
}
authorized=set()

def calc_tv_conf(symbol_tv):
    # يحسب الثقة من 5 مؤشرات حقيقية مو عشوائي
    configs = [("GOLD","TVC","cfd"), ("XAUUSD","OANDA","forex")] if symbol_tv=="GOLD" else [(symbol_tv,"FX","forex"), (symbol_tv,"OANDA","forex")]
    best = ("SIDE",0,50,"")
    for sym, exch, scr in configs:
        try:
            time.sleep(random.uniform(0.6,1.0))
            h = TA_Handler(symbol=sym, screener=scr, exchange=exch, interval=Interval.INTERVAL_15_MINUTES)
            a = h.get_analysis()
            ind = a.indicators
            close=ind.get("close",0)
            if not close: continue
            ema50=ind.get("EMA50",0); ema200=ind.get("EMA200",0)
            rsi=ind.get("RSI",50); macd=ind.get("MACD.macd",0)
            macd_sig=ind.get("MACD.signal",0); adx=ind.get("ADX",0)
            adx_p=ind.get("ADX+DI",0); adx_m=ind.get("ADX-DI",0)
            stoch_k=ind.get("Stoch.K",50)

            score=0; detail=[]
            # 1- EMA
            if close>ema50>ema200: score+=20; detail.append("EMA صاعد")
            elif close<ema50<ema200: score+=20; detail.append("EMA هابط")
            # 2- RSI
            if 60<rsi<75: score+=20; detail.append(f"RSI {int(rsi)} قوي")
            elif 25<rsi<40: score+=20; detail.append(f"RSI {int(rsi)} قوي")
            elif 45<rsi<55: score+=5
            # 3- MACD
            if macd>macd_sig: score+=20; detail.append("MACD صاعد")
            else: score+=20; detail.append("MACD هابط")
            # 4- ADX
            if adx>25: score+=20; detail.append(f"ADX {int(adx)} ترند قوي")
            elif adx>18: score+=10
            # 5- Stoch
            if stoch_k>50: score+=10

            # تحديد الاتجاه
            is_buy = (close>ema50) and (adx_p>adx_m) and (macd>macd_sig)
            direction = "BUY" if is_buy else "SELL"
            if adx<18: direction="SIDE"; score=int(score*0.4)

            conf = min(96, 60 + score//2 + int((adx-20)/1.5))
            if conf>best[1]: best=(direction, conf, rsi, f"{exch} | {' + '.join(detail[:3])}")
        except: continue
    return best

def get_yf_conf(yf_sym):
    try:
        import yfinance as yf
        df = yf.download(yf_sym, period="3d", interval="15m", progress=False, auto_adjust=True)
        if len(df)<150: return "SIDE",0,50,"yf قليل"
        c=df['Close']; h=df['High']; l=df['Low']
        ema50=c.ewm(span=50).mean().iloc[-1]; ema200=c.ewm(span=200).mean().iloc[-1]
        delta=c.diff(); gain=delta.where(delta>0,0).rolling(14).mean(); loss=-delta.where(delta<0,0).rolling(14).mean()
        rsi=100-(100/(1+gain/loss)); rsi_last=float(rsi.iloc[-1]); last=float(c.iloc[-1])
        # ADX مبسط
        tr = (h-l).abs().rolling(14).mean().iloc[-1]
        up = (h.diff().clip(lower=0)).rolling(14).mean().iloc[-1]
        adx_proxy = min(50, (up/tr*100) if tr else 20)

        score=0
        if last>ema50>ema200: score+=40
        if last<ema50<ema200: score+=40
        if 55<rsi_last<75 or 25<rsi_last<45: score+=30
        if adx_proxy>25: score+=30
        conf=min(92, 55+score//2)
        direction="BUY" if last>ema50 else "SELL"
        if adx_proxy<18: return "SIDE",0,int(rsi_last),"YF متذبذب"
        return direction, conf, int(rsi_last), f"YF EMA+RSI ADX~{int(adx_proxy)}"
    except: return "SIDE",0,50,"YF خطأ"

def get_market_score(name):
    tv=MARKETS[name]; yf=MARKETS_YF[name]
    d,p,r,t = calc_tv_conf(tv)
    if p==0: d,p,r,t = get_yf_conf(yf)
    # احسب 1H للتأكيد
    try:
        h = TA_Handler(symbol=tv if tv!="GOLD" else "GOLD", screener="cfd" if tv=="GOLD" else "forex", exchange="TVC" if tv=="GOLD" else "FX", interval=Interval.INTERVAL_1_HOUR)
        a=h.get_analysis(); ind=a.indicators
        close=ind.get("close",0); ema50=ind.get("EMA50",0); adx=ind.get("ADX",0)
        if (d=="BUY" and close>ema50 and adx>20) or (d=="SELL" and close<ema50 and adx>20):
            p=min(98,p+6)
        elif adx<18:
            p=int(p*0.7); d="SIDE"
    except: pass
    return {"name":name, "dir":d, "conf":p, "rsi":r, "detail":t}

def main_menu(cid):
    m=InlineKeyboardMarkup(row_width=1)
    m.add(InlineKeyboardButton("🏆 افضل 6 فرص مضمونة", callback_data="best6"))
    m.add(InlineKeyboardButton("💎 الذهبية 90%+", callback_data="diamond"))
    m.add(InlineKeyboardButton("🔥 شامل 78%+", callback_data="golden"))
    m.add(InlineKeyboardButton("📊 كل الاسواق بالنسب", callback_data="all"))
    bot.send_message(cid,"🏆 MAD-BOT V3 - 14", reply_markup=m)

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id not in authorized: bot.send_message(msg.chat.id,"🔒 ارسل كلمة السر:"); return
    main_menu(msg.chat.id)

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def pw(m):
    if m.text.strip()==PASSWORD: authorized.add(m.from_user.id); main_menu(m.chat.id)
    else: bot.send_message(m.chat.id,"❌ غلط")

@bot.callback_query_handler(func=lambda c: True)
def cb(call):
    if call.from_user.id not in authorized: return
    if call.data in ["best6","golden","diamond","all"]:
        is_all = call.data=="all"
        need = 90 if call.data=="diamond" else 78 if call.data=="golden" else 0
        title = "📊 كل الاسواق" if is_all else f"🏆 افضل 6 فرص" if call.data=="best6" else f"💎 90%+" if need==90 else "🔥 78%+"
        bot.answer_callback_query(call.id, "⏳ يحلل 15 سوق...")
        load=bot.send_message(call.message.chat.id, f"⏳ {title} - يحلل 15 سوق بمؤشرات حقيقية (25 ثانية)...")

        results=[]
        with ThreadPoolExecutor(max_workers=3) as ex:
            futs={ex.submit(get_market_score, n): n for n in MARKETS}
            for f in as_completed(futs):
                try: results.append(f.result())
                except: pass

        # رتب من الاقوى للاضعف
        results_sorted = sorted([r for r in results if r['dir']!="SIDE"], key=lambda x: x['conf'], reverse=True)
        side_sorted = sorted([r for r in results if r['dir']=="SIDE"], key=lambda x: x['conf'], reverse=True)

        if is_all:
            # اعرض الكل 15 سوق بنسبة الثقة
            txt="📊 **كل الاسواق - مرتبة حسب الثقة:**\n\n"
            for i,r in enumerate(sorted(results, key=lambda x: x['conf'], reverse=True),1):
                emoji="🟢 BUY" if r['dir']=="BUY" else "🔴 SELL" if r['dir']=="SELL" else "⚪ SIDE"
                txt+=f"{i}. {emoji} {r['name']} - **{r['conf']}%**\n {r['detail']} RSI:{r['rsi']}\n\n"
        else:
            if not results_sorted:
                txt="❌ لا يوجد فرص قوية حاليا - السوق متذبذب\nجرب فحص كل الاسواق"
            else:
                # اعرض اكثر من 4 - افضل 6
                top6 = results_sorted[:6]
                txt=f"{title} - اختار الافضل:\n\n"
                for i,r in enumerate(top6,1):
                    emoji="🟢 BUY" if r['dir']=="BUY" else "🔴 SELL"
                    txt+=f"{i}. {emoji} {r['name']} - **{r['conf']}%** 🔥\n {r['detail']} RSI:{r['rsi']}\n ⏱️ دخول 15 دقيقة\n\n"
                if len(results_sorted)>6:
                    txt+=f"---\nفرص اضافية:\n"
                    for r in results_sorted[6:10]:
                        emoji="🟢" if r['dir']=="BUY" else "🔴"
                        txt+=f"{emoji} {r['name']} {r['conf']}%\n"
                # افضل فرصة
                best=top6[0]
                txt+=f"\n🏆 **افضل فرصة:** {best['name']} {best['conf']}% {best['dir']}"

        mk=InlineKeyboardMarkup(row_width=2)
        mk.add(InlineKeyboardButton("🏆 افضل 6", callback_data="best6"), InlineKeyboardButton("📊 كل الاسواق", callback_data="all"))
        mk.add(InlineKeyboardButton("💎 90%+", callback_data="diamond"), InlineKeyboardButton("🔥 78%+", callback_data="golden"))
        bot.edit_message_text(txt, call.message.chat.id, load.message_id, reply_markup=mk, parse_mode="Markdown")

app=Flask(__name__)
@app.route('/')
def h(): return "MAD-BOT V3 - 14 Professional"
def run(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
threading.Thread(target=run, daemon=True).start()
bot.remove_webhook(); time.sleep(2)
while True:
    try: bot.infinity_polling(skip_pending=True, timeout=60)
    except: time.sleep(5)
