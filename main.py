import ccxt
import pandas as pd
import pandas_ta as ta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = "8828337019:AAHu5HxEgw5qFTeOd7DTWA1ELJXDH00yK1E"
GOLD_CONFIDENCE = 80

# كل الاسواق مع اعلامها
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
    "🇨🇦/🇯🇵 CAD/JPY": "CAD/JPY",
    "🇨🇭/🇯🇵 CHF/JPY": "CHF/JPY",

    "🇪🇺/🇬🇧 EUR/GBP": "EUR/GBP",
    "🇪🇺/🇦🇺 EUR/AUD": "EUR/AUD",
    "🇪🇺/🇨🇦 EUR/CAD": "EUR/CAD",
    "🇬🇧/🇦🇺 GBP/AUD": "GBP/AUD",
    "🇬🇧/🇨🇦 GBP/CAD": "GBP/CAD",
    "🇦🇺/🇨🇦 AUD/CAD": "AUD/CAD",

    # OTC بوكت اوبشن 24 ساعة
    "🇪🇺/🇺🇸 EUR/USD OTC": "EUR/USD_otc",
    "🇬🇧/🇺🇸 GBP/USD OTC": "GBP/USD_otc",
    "🇺🇸/🇯🇵 USD/JPY OTC": "USD/JPY_otc",
    "🇦🇺/🇺🇸 AUD/USD OTC": "AUD/USD_otc",
    "🇪🇺/🇯🇵 EUR/JPY OTC": "EUR/JPY_otc",
    "🇬🇧/🇯🇵 GBP/JPY OTC": "GBP/JPY_otc",
    "🇦🇺/🇯🇵 AUD/JPY OTC": "AUD/JPY_otc",
    "🪙 GOLD OTC": "GOLD_otc",

    "🪙 GOLD": "XAU/USD",
    "₿ BTC/USD": "BTC/USD",
    "Ξ ETH/USD": "ETH/USD"
}

exchange = ccxt.binance()

def get_analysis(symbol):
    real_symbol = symbol.replace("_otc", "").replace("/", "").replace("XAU/USD", "XAUUSD")
    if "GOLD" in symbol:
        real_symbol = "PAXG/USDT"
    if "BTC" in symbol:
        real_symbol = "BTC/USDT"
    if "ETH" in symbol:
        real_symbol = "ETH/USDT"

    timeframes = ['5m', '15m', '1h']
    results = {}

    for tf in timeframes:
        try:
            ohlcv = exchange.fetch_ohlcv(real_symbol, tf, limit=100)
            df = pd.DataFrame(ohlcv, columns=['t','o','h','l','c','v'])

            df['rsi'] = ta.rsi(df['c'], length=14)
            df['ema20'] = ta.ema(df['c'], length=20)
            df['ema50'] = ta.ema(df['c'], length=50)
            macd_data = ta.macd(df['c'])
            df['macd'] = macd_data['MACD_12_26_9']

            last = df.iloc[-1]

            score = 0
            direction = "NONE"

            if last['c'] > last['ema20'] > last['ema50']:
                score += 40
                direction = "BUY"
            elif last['c'] < last['ema20'] < last['ema50']:
                score += 40
                direction = "SELL"
            else:
                score += 10

            if direction == "BUY" and last['rsi'] > 55:
                score += 30
            elif direction == "SELL" and last['rsi'] < 45:
                score += 30
            elif last['rsi'] > 50 and direction == "BUY":
                score += 15
            elif last['rsi'] < 50 and direction == "SELL":
                score += 15

            if direction == "BUY" and last['macd'] > 0:
                score += 30
            elif direction == "SELL" and last['macd'] < 0:
                score += 30

            results[tf] = {"percent": min(score, 95), "dir": direction}

        except Exception as e:
            print(f"خطأ {real_symbol} {tf}: {e}")
            results[tf] = {"percent": 0, "dir": "NONE"}

    return results

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    row = []
    for display_name, sym in MARKETS.items():
        row.append(InlineKeyboardButton(display_name, callback_data=f"market_{sym}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    await update.message.reply_text(
        "👋 البوت الاسطوري Triple TF + فلتر النوم\nاختر السوق:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("market_"):
        symbol = data.replace("market_", "")
        context.user_data["symbol"] = symbol

        # عرض الاسم مع العلم
        display_name = [k for k,v in MARKETS.items() if v == symbol][0]

        keyboard = [[InlineKeyboardButton("🔍 فحص شامل", callback_data="check_all")]]
        await query.edit_message_text(
            f"اخترت {display_name}\nاضغط فحص:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "check_all":
        symbol = context.user_data.get("symbol", "EUR/USD")
        display_name = [k for k,v in MARKETS.items() if v == symbol]
        display_name = display_name[0] if display_name else symbol

        await query.edit_message_text(f"⏳ جاري فحص {display_name} على 3 فريمات...")

        res = get_analysis(symbol)
        p5 = res['5m']['percent']
        p15 = res['15m']['percent']
        p1h = res['1h']['percent']
        d5 = res['5m']['dir']
        d15 = res['15m']['dir']
        d1h = res['1h']['dir']

        avg = int((p5 + p15 + p1h) / 3)

        # 1. فلتر النوم
        if p5 < 55 and p15 < 55 and p1h < 55:
            msg = f"😴 السوق نايم\n📊 {display_name}\n5m:{p5}% | 15m:{p15}% | H1:{p1h}%\nلا تدخل - ما في حركة"
            keyboard = [[InlineKeyboardButton("🔍 فحص شامل", callback_data="check_all")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # 2. فلتر التضارب
        dirs = [d5, d15, d1h]
        if not (dirs.count("BUY") >= 2 or dirs.count("SELL") >= 2):
            msg = f"❌ لا تدخل السوق متضارب\n📊 {display_name}\n5m:{d5} {p5}% | 15m:{d15} {p15}% | H1:{d1h} {p1h}%"
            keyboard = [[InlineKeyboardButton("🔍 فحص شامل", callback_data="check_all")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        main_dir = "BUY" if dirs.count("BUY") >= 2 else "SELL"
        emoji = "🟢 صعود BUY" if main_dir == "BUY" else "🔴 هبوط SELL"

        # 3. التصحيح الجديد - ذهبية حقيقية
        if p5 >= 80 and p15 >= 80 and p1h >= 80:
            final_percent = min(94, avg + 12)
            is_gold = final_percent >= GOLD_CONFIDENCE
        else:
            final_percent = avg
            is_gold = False

        if is_gold:
            msg = f"""🔥🔥🔥 صفقة ذهبية 🔥🔥🔥
📊 {display_name}

{emoji}
💎 الثقة: {final_percent}%
5m:{p5}% | 15m:{p15}% | H1:{p1h}% - تطابق كامل ✅

⏰ مدة الصفقة في بوكت اوبشن: 15 دقيقة
💰 هذي هي ادخل وانت مغمض"""
        else:
            weak = ""
            if p1h < 75:
                weak = f" - H1 ضعيف {p1h}% ⚠️"
            elif p15 < 75:
                weak = f" - 15m ضعيف {p15}% ⚠️"
            elif p5 < 75:
                weak = f" - 5m ضعيف {p5}% ⚠️"

            msg = f"""📊 {display_name} - فحص شامل
{emoji}
💪 الثقة: {final_percent}%{weak}

5m:{p5}% | 15m:{p15}% | H1:{p1h}%

⏰ مدة الصفقة: 15 دقيقة
⚠️ لا تدخل - انتظر ذهبية فوق 80% في كل الفريمات"""

        keyboard = [[InlineKeyboardButton("🔍 فحص شامل", callback_data="check_all")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.run_polling()
