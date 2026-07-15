import os
import asyncio
from flask import Flask
from threading import Thread
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from tradingview_ta import TA_Handler, Interval

TOKEN = os.environ.get('BOT_TOKEN')

MARKETS = {
    "EURUSD": "🇪🇺 EUR/USD 🇺🇸",
    "USDCAD": "🇺🇸 USD/CAD 🇨🇦",
    "USDCHF": "🇺🇸 USD/CHF 🇨🇭",
    "USDJPY": "🇺🇸 USD/JPY 🇯🇵",
    "EURJPY": "🇪🇺 EUR/JPY 🇯🇵",
    "AUDCAD": "🇦🇺 AUD/CAD 🇨🇦",
    "AUDCHF": "🇦🇺 AUD/CHF 🇨🇭",
    "AUDJPY": "🇦🇺 AUD/JPY 🇯🇵",
    "AUDUSD": "🇦🇺 AUD/USD 🇺🇸",
    "CADCHF": "🇨🇦 CAD/CHF 🇨🇭",
    "CADJPY": "🇨🇦 CAD/JPY 🇯🇵",
    "CHFJPY": "🇨🇭 CHF/JPY 🇯🇵",
    "EURAUD": "🇪🇺 EUR/AUD 🇦🇺",
    "EURCAD": "🇪🇺 EUR/CAD 🇨🇦",
    "EURCHF": "🇪🇺 EUR/CHF 🇨🇭",
    "EURGBP": "🇪🇺 EUR/GBP 🇬🇧",
    "GBPAUD": "🇬🇧 GBP/AUD 🇦🇺",
    "GBPCAD": "🇬🇧 GBP/CAD 🇨🇦",
    "GBPCHF": "🇬🇧 GBP/CHF 🇨🇭",
    "GBPJPY": "🇬🇧 GBP/JPY 🇯🇵",
    "GBPUSD": "🇬🇧 GBP/USD 🇺🇸",
    "NZDCAD": "🇳🇿 NZD/CAD 🇨🇦",
    "NZDCHF": "🇳🇿 NZD/CHF 🇨🇭",
    "NZDJPY": "🇳🇿 NZD/JPY 🇯🇵",
    "NZDUSD": "🇳🇿 NZD/USD 🇺🇸",
    # 4 اسواق OTC لبوكت اوبشن
    "EURUSD_OTC": "🇪🇺 EUR/USD OTC 🇺🇸",
    "GBPUSD_OTC": "🇬🇧 GBP/USD OTC 🇺🇸",
    "AUDUSD_OTC": "🇦🇺 AUD/USD OTC 🇺🇸",
    "USDJPY_OTC": "🇺🇸 USD/JPY OTC 🇯🇵",
}

FLAGS = {
    "USD":"🇺🇸","EUR":"🇪🇺","GBP":"🇬🇧","JPY":"🇯🇵",
    "AUD":"🇦🇺","CAD":"🇨🇦","CHF":"🇨🇭","NZD":"🇳🇿"
}

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is alive - MAD-TRADER"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

async def start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بك في بوت MAD-TRADER 🔥\nاستخدم /signal لعرض كل الأزواج")

async def signal_cmd(update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        keyboard = []
        for symbol, name in MARKETS.items():
            keyboard.append([InlineKeyboardButton(name, callback_data=f"sig_{symbol}")])
        await update.message.reply_text("📊 اختر السوق:", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    symbol = context.args[0].upper().replace("/","")
    await do_analysis(update, symbol, False)

async def btn_handler(update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    symbol = q.data.replace("sig_", "")
    await do_analysis(q, symbol, True)

async def do_analysis(obj, symbol, is_callback):
    send_func = obj.edit_message_text if is_callback else obj.message.reply_text
    # لو OTC نشيل كلمة _OTC عشان التحليل
    real_symbol = symbol.replace("_OTC","").replace("_otc","")
    base = real_symbol[:3]
    quote = real_symbol[3:]
    full_name = MARKETS.get(symbol, f"{FLAGS.get(base,'🏳️')} {symbol} {FLAGS.get(quote,'🏳️')}")
    try:
        await send_func(f"🔍 جاري تحليل {full_name}...")
        handler = TA_Handler(symbol=real_symbol, screener="forex", exchange="FX_IDC", interval=Interval.INTERVAL_1_MINUTE)
        analysis = handler.get_analysis().summary
        rec = analysis["RECOMMENDATION"]
        buy = analysis["BUY"]
        sell = analysis["SELL"]
        neutral = analysis["NEUTRAL"]
        total = buy + sell + neutral

        if "BUY" in rec:
            confidence = int((buy / total) * 100 + (buy - sell) * 1.5)
        elif "SELL" in rec:
            confidence = int((sell / total) * 100 + (sell - buy) * 1.5)
        else:
            confidence = int((max(buy,sell) / total) * 100)
        confidence = max(65, min(97, confidence))

        if "BUY" in rec:
            msg = f"""🟢 إشارة شراء

💱 {full_name}
📊 الفريم: M1
⏳ الدخول: الآن
🎯 الثقة: {confidence}%

🔥 MAD TRADER"""
        elif "SELL" in rec:
            msg = f"""🔴 إشارة بيع

💱 {full_name}
📊 الفريم: M1
⏳ الدخول: الآن
🎯 الثقة: {confidence}%

🔥 MAD TRADER"""
        else:
            msg = f"""🟡 إشارة انتظار

💱 {full_name}
📊 الفريم: M1
⏸️ القرار: انتظار
🎯 الثقة: {confidence}%

🔥 MAD TRADER"""
        await send_func(msg)
    except Exception as e:
        await send_func(f"❌ خطأ في تحليل {full_name}: {e}")

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("signal", signal_cmd))
    application.add_handler(CallbackQueryHandler(btn_handler))
    Thread(target=run_flask, daemon=True).start()
    print("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
