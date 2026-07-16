import ccxt
import pandas as pd
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = "8828337019:AAHu5HxEgw5qFTeOd7DTWA1ELJXDH00yK1E"
GOLD_CONFIDENCE = 80

MARKETS = {
    "🇪🇺/🇺🇸 EUR/USD": "EUR/USD",
    "🇬🇧/🇺🇸 GBP/USD": "GBP/USD",
    "🇺🇸/🇯🇵 USD/JPY": "USD/JPY",
    "🇦🇺/🇺🇸 AUD/USD": "AUD/USD",
    "🇺🇸/🇨🇭 USD/CHF": "USD/CHF",
    "🇺🇸/🇨🇦 USD/CAD": "USD/CAD",
    "🇳🇿/🇺🇸 NZD/USD": "NZD/USD",
    "🇪🇺/🇯🇵 EUR/JPY": "EUR/JPY",
    "🇬🇧/🇯🇵 GBP/JPY": "GBP/JPY",
    "🇦🇺/🇯🇵 AUD/JPY": "AUD/JPY",
    "🇪🇺/🇬🇧 EUR/GBP": "EUR/GBP",
    "🇪🇺/🇦🇺 EUR/AUD": "EUR/AUD",
    "🇬🇧/🇦🇺 GBP/AUD": "GBP/AUD",
    "🇪🇺/🇺🇸 EUR/USD OTC": "EUR/USD_otc",
    "🇬🇧/🇺🇸 GBP/USD OTC": "GBP/USD_otc",
    "🪙 GOLD": "XAU/USD",
    "🪙 GOLD OTC": "GOLD_otc",
    "₿ BTC/USD": "BTC/USD",
}

exchange = ccxt.binance()

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def get_analysis(symbol):
    real_symbol = symbol.replace("_otc","").replace("/","")
    if "GOLD" in symbol or "XAU" in symbol:
        real_symbol = "PAXG/USDT"
    if "BTC" in symbol:
        real_symbol = "BTC/USDT"

    results = {}
    for tf in ['5m','15m','1h']:
        try:
            ohlcv = exchange.fetch_ohlcv(real_symbol, tf, limit=100)
            df = pd.DataFrame(ohlcv, columns=['t','o','h','l','c','v'])
            df['rsi'] = calc_rsi(df['c'],14)
            df['ema20'] = calc_ema(df['c'],20)
            df['ema50'] = calc_ema(df['c'],50)
            df['ema12'] = calc_ema(df['c'],12)
            df['ema26'] = calc_ema(df['c'],26)
            df['macd'] = df['ema12'] - df['ema26']
            last = df.iloc[-1]
            score=0
            direction="NONE"
            if last['c'] > last['ema20'] > last['ema50']:
                score+=40
                direction="BUY"
            elif last['c'] < last['ema20'] < last['ema50']:
                score+=40
                direction="SELL"
            else:
                score+=10
            if direction=="BUY" and last['rsi']>55: score+=30
            elif direction=="SELL" and last['rsi']<45: score+=30
            if direction=="BUY" and last['macd']>0: score+=30
            elif direction=="SELL" and last['macd']<0: score+=30
            results[tf]={"percent":min(score,95),"dir":direction}
        except:
            results[tf]={"percent":0,"dir":"NONE"}
    return results

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard=[]
    row=[]
    for name,sym in MARKETS.items():
        row.append(InlineKeyboardButton(name, callback_data=f"market_{sym}"))
        if len(row)==2:
            keyboard.append(row)
            row=[]
    if row: keyboard.append(row)
    await update.message.reply_text("👋 البوت الاسطوري اختر السوق:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query
    await query.answer()
    data=query.data
    if data.startswith("market_"):
        symbol=data.replace("market_","")
        context.user_data["symbol"]=symbol
        display=[k for k,v in MARKETS.items() if v==symbol][0]
        keyboard=[[InlineKeyboardButton("🔍 فحص شامل", callback_data="check_all")]]
        await query.edit_message_text(f"اخترت {display}\nاضغط فحص:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data=="check_all":
        symbol=context.user_data.get("symbol","EUR/USD")
        display=[k for k,v in MARKETS.items() if v==symbol][0]
        await query.edit_message_text(f"⏳ جاري فحص {display}...")
        res=get_analysis(symbol)
        p5=res['5m']['percent']; p15=res['15m']['percent']; p1h=res['1h']['percent']
        d5=res['5m']['dir']; d15=res['15m']['dir']; d1h=res['1h']['dir']
        avg=int((p5+p15+p1h)/3)
        dirs=[d5,d15,d1h]
        if p5<55 and p15<55 and p1h<55:
            msg=f"😴 السوق نايم\n📊 {display}\n5m:{p5}% | 15m:{p15}% | H1:{p1h}%"
        elif not (dirs.count("BUY")>=2 or dirs.count("SELL")>=2):
            msg=f"❌ متضارب\n📊 {display}\n5m:{d5} {p5}% | 15m:{d15} {p15}% | H1:{d1h} {p1h}%"
        else:
            main_dir="BUY" if dirs.count("BUY")>=2 else "SELL"
            emoji="🟢 BUY" if main_dir=="BUY" else "🔴 SELL"
            if p5>=80 and p15>=80 and p1h>=80:
                final=min(94,avg+12)
                msg=f"🔥🔥🔥 صفقة ذهبية 🔥🔥🔥\n📊 {display}\n\n{emoji}\n💎 الثقة: {final}%\n5m:{p5}% | 15m:{p15}% | H1:{p1h}% ✅\n\n⏰ 15 دقيقة"
            elif p5>=70 and p15>=70 and p1h>=70:
                msg=f"✅ اشارة موثوقة\n📊 {display}\n\n{emoji}\n💪 الثقة: {avg}%\n5m:{p5}% | 15m:{p15}% | H1:{p1h}%\n\n⏰ 15 دقيقة"
            else:
                msg=f"❌ لا تدخل\n📊 {display}\n\n{emoji}\n💪 {avg}%\n5m:{p5}% | 15m:{p15}% | H1:{p1h}%\n⚠️ انتظر ذهبية"
        keyboard=[[InlineKeyboardButton("🔍 فحص شامل", callback_data="check_all")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

app=Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start",start))
app.add_handler(CallbackQueryHandler(button_handler))
app.run_polling()
