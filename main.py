import os
import asyncio
from flask import Flask
from threading import Thread
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from tradingview_ta import TA_Handler, Interval

# التوكن من Render
TOKEN = os.environ.get('BOT_TOKEN')

# الأزواج
PAIRS = ["EURUSD","USDCAD","USDCHF","USDJPY","EURJPY","AUDCAD","AUDCHF","AUDJPY","AUDUSD","CADCHF","CADJPY","CHFJPY","EURAUD","EURCAD","EURCHF","EURGBP","EURUSD","GBPAUD","GBPCAD","GBPCHF","GBPJPY","GBPUSD","NZDCAD","NZDCHF","NZDJPY","NZDUSD","USDCAD"]

# Flask عشان Render ما يطفي الخدمة
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is alive - MAD-TRADER"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# أوامر البوت
async def start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بك في بوت MAD-TRADER!\nاستخدم /pairs لعرض الأزواج\n/stopsignal لإيقاف الإشعارات")

async def pairs(update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    row = []
    for i, pair in enumerate(PAIRS):
        row.append(InlineKeyboardButton(pair, callback_data=f"sig_{pair}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    await update.message.reply_text("اختر الزوج:", reply_markup=InlineKeyboardMarkup(keyboard))

async def btn_handler(update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    symbol = q.data.replace("sig_", "")
    await do_analysis(q, symbol, True)

async def signal_cmd(update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("استخدم: /signal EURUSD")
        return
    symbol = context.args[0].upper()
    await do_analysis(update, symbol, False)

async def do_analysis(obj, symbol, is_callback):
    send_func = obj.edit_message_text if is_callback else obj.message.reply_text
    try:
        await send_func(f"🔍 جاري تحليل {symbol} على فريم 1 دقيقة...")
        handler = TA_Handler(symbol=symbol, screener="forex", exchange="FX_IDC", interval=Interval.INTERVAL_1_MINUTE)
        analysis = handler.get_analysis().summary
        rec = analysis["RECOMMENDATION"]
        buy = analysis["BUY"]
        sell = analysis["SELL"]
        neutral = analysis["NEUTRAL"]

        if "BUY" in rec:
            msg = f"📈 {symbol} - إشارة شراء\n{rec}\nBUY: {buy} SELL: {sell} NEUTRAL: {neutral}"
        elif "SELL" in rec:
            msg = f"📉 {symbol} - إشارة بيع\n{rec}\nBUY: {buy} SELL: {sell} NEUTRAL: {neutral}"
        else:
            msg = f"⏸️ {symbol} - انتظار\n{rec}\nBUY: {buy} SELL: {sell} NEUTRAL: {neutral}"
        await send_func(msg)
    except Exception as e:
        await send_func(f"❌ خطأ في تحليل {symbol}: {e}")

def main():
    # هذا السطر يحل مشكلة no current event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("pairs", pairs))
    application.add_handler(CommandHandler("signal", signal_cmd))
    application.add_handler(CallbackQueryHandler(btn_handler))

    # شغل Flask في الخلفية
    Thread(target=run_flask, daemon=True).start()

    print("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
