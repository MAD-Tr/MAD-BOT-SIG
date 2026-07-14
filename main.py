import os
import asyncio
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from tradingview_ta import TA_Handler, Interval

TOKEN = os.environ.get('BOT_TOKEN')
# قائمة الأزواج اللي في الصور حقتك
PAIRS = [
    "EURUSD", "USDCAD", "USDCHF", "USDJPY",
    "EURJPY", "AUDCAD", "AUDCHF", "AUDJPY", "AUDUSD",
    "CADCHF", "CADJPY", "CHFJPY", "EURAUD", "EURCAD", "EURCHF"
]

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً! 🤖\n\nالأوامر:\n/pairs - عرض كل الأزواج\n/signal EURUSD - تحليل زوج معين"
    )

async def pairs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    row = []
    for i, pair in enumerate(PAIRS):
        row.append(InlineKeyboardButton(pair, callback_data=f"signal_{pair}"))
        if len(row) == 3: # 3 أزرار في كل سطر
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("اختر الزوج:", reply_markup=reply_markup)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pair = query.data.replace("signal_", "")
    await analyze_pair(query, pair)

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("اكتب الزوج بعد الأمر. مثال: /signal EURUSD\nأو استخدم /pairs")
        return

    symbol = context.args[0].upper()
    await analyze_pair(update, symbol)

async def analyze_pair(update_or_query, symbol):
    is_callback = hasattr(update_or_query, 'edit_message_text')
    send_func = update_or_query.edit_message_text if is_callback else update_or_query.message.reply_text

    await send_func(f"جاري تحليل {symbol}... ⏳")

    try:
        handler = TA_Handler(
            symbol=symbol,
            screener="forex",
            exchange="FX_IDC",
            interval=Interval.INTERVAL_1_MINUTE
        )
        analysis = handler.get_analysis()
        summary = analysis.summary
        recommendation = summary["RECOMMENDATION"]

        if "BUY" in recommendation:
            msg = f"📈 **إشارة {symbol}**\n\nالاتجاه: صعود ✅\nالتوصية: **شراء**\n\nBUY: {summary['BUY']} | SELL: {summary['SELL']} | NEUTRAL: {summary['NEUTRAL']}"
        elif "SELL" in recommendation:
            msg = f"📉 **إشارة {symbol}**\n\nالاتجاه: هبوط ✅\nالتوصية: **بيع**\n\nBUY: {summary['BUY']} | SELL: {summary['SELL']} | NEUTRAL: {summary['NEUTRAL']}"
        else:
            msg = f"⏸️ **إشارة {symbol}**\n\nالاتجاه: محايد\nالتوصية: **انتظار**\n\nBUY: {summary['BUY']} | SELL: {summary['SELL']} | NEUTRAL: {summary['NEUTRAL']}"

        await send_func(msg, parse_mode='Markdown')

    except Exception as e:
        await send_func(f"❌ خطأ: ما قدرت أحلل {symbol}\nتأكد من اسم الزوج")

def run_bot():
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("pairs", pairs))
    application.add_handler(CommandHandler("signal", signal))
    application.add_handler(CallbackQueryHandler(button_click))
    application.run_polling()

if __name__ == '__main__':
    Thread(target=run_flask).start()
    run_bot()
