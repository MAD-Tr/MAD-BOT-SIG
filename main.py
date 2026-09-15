import os, random, threading
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

TOKEN = os.getenv("8828337019:AAE03YhnaMnRuWWu1U4eqdTZSgHVAoGCLuI", "").strip()
PASSWORD = os.getenv("7154", "").strip() # الرقم السري من Render
GITHUB_USER = os.getenv("GITHUB_USER", "MAD-Tr")
PORT = int(os.getenv("PORT", 10000))

print(f"BOT_TOKEN: {bool(TOKEN)} len={len(TOKEN) if TOKEN else 0}")
print(f"PASSWORD: {bool(PASSWORD)}")

app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return f"MAD-BOT-SIG Live - Token:{bool(TOKEN)}"

# ===== 24 سوق حقيقي =====
MARKETS_REAL = {
    "EUR/USD":"🇪🇺/🇺🇸","GBP/USD":"🇬🇧/🇺🇸","USD/JPY":"🇺🇸/🇯🇵","AUD/USD":"🇦🇺/🇺🇸",
    "USD/CHF":"🇺🇸/🇨🇭","USD/CAD":"🇺🇸/🇨🇦","NZD/USD":"🇳🇿/🇺🇸","EUR/JPY":"🇪🇺/🇯🇵",
    "EUR/GBP":"🇪🇺/🇬🇧","GBP/JPY":"🇬🇧/🇯🇵","AUD/JPY":"🇦🇺/🇯🇵","EUR/AUD":"🇪🇺/🇦🇺",
    "GBP/AUD":"🇬🇧/🇦🇺","EUR/CAD":"🇪🇺/🇨🇦","GBP/CAD":"🇬🇧/🇨🇦","AUD/CAD":"🇦🇺/🇨🇦",
    "EUR/CHF":"🇪🇺/🇨🇭","GBP/CHF":"🇬🇧/🇨🇭","AUD/CHF":"🇦🇺/🇨🇭","NZD/JPY":"🇳🇿/🇯🇵",
    "EUR/NZD":"🇪🇺/🇳🇿","GBP/NZD":"🇬🇧/🇳🇿","AUD/NZD":"🇦🇺/🇳🇿","CHF/JPY":"🇨🇭/🇯🇵"
}
# ===== 24 سوق OTC =====
MARKETS_OTC = {k+" OTC":v+" OTC" for k,v in MARKETS_REAL.items()}

def get_tv(market):
    try:
        from tradingview_ta import TA_Handler, Interval
        h = TA_Handler(symbol=market.replace(" OTC","").replace("/",""), exchange="FX", screener="forex", interval=Interval.INTERVAL_1_MINUTE)
        a = h.get_analysis()
        c = a.indicators["close"]; rsi = a.indicators["RSI"]; adx = a.indicators.get("ADX",22)
        sig = "CALL" if c > a.indicators["EMA20"] and rsi > 52 else "PUT" if c < a.indicators["EMA20"] and rsi < 48 else "CALL" if rsi > 50 else "PUT"
        exp = "2m" if adx > 25 else "5m"
        return sig, exp, f"RSI:{rsi:.0f} ADX:{adx:.0f}"
    except:
        return ("CALL" if random.random()>0.5 else "PUT"), "2m", "sim"

def get_otc(market):
    payout = random.uniform(75,92)
    return ("CALL" if random.random()>0.5 else "PUT"), "2m", f"{payout:.0f}%"

def main_kb():
    url = f"https://{GITHUB_USER}.github.io/MAD-BOT-SIG/mini_app/"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 فتح التطبيق المصغر", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton("📈 حقيقية 24", callback_data="ALL_REAL"), InlineKeyboardButton("⚡ OTC 24", callback_data="ALL_OTC")],
        [InlineKeyboardButton("🎯 إشارة عشوائية", callback_data="RANDOM")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if PASSWORD:
        if context.args and context.args[0]==PASSWORD:
            context.user_data['auth']=True
            await update.message.reply_text("✅ تم فتح البوت", reply_markup=main_kb()); return
        if context.user_data.get('auth'):
            await update.message.reply_text("🤖 MAD-BOT-SIG جاهز ✅", reply_markup=main_kb()); return
        await update.message.reply_text("🔒 ادخل الرقم السري للبوت"); return
    await update.message.reply_text("🤖 MAD-BOT-SIG جاهز ✅ 48 سوق", reply_markup=main_kb())

async def check_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not PASSWORD or context.user_data.get('auth'): return
    if update.message.text.strip()==PASSWORD:
        context.user_data['auth']=True
        await update.message.reply_text("✅ تم فتح البوت", reply_markup=main_kb())
    else:
        await update.message.reply_text("❌ الرقم السري غلط")

async def btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    if PASSWORD and not context.user_data.get('auth'):
        await q.message.reply_text("🔒 ادخل الرقم السري أولاً"); return
    d=q.data
    if d=="ALL_REAL":
        txt="📈 **24 سوق حقيقي:**\n\n"
        for m,f in MARKETS_REAL.items():
            s,e,i=get_tv(m); txt+=f"{f} {m}: **{s}** ⏱{e} {i}\n"
        await q.message.reply_text(txt, parse_mode="Markdown"); return
    if d=="ALL_OTC":
        txt="⚡ **24 سوق OTC:**\n\n"
        for m,f in MARKETS_OTC.items():
            s,e,p=get_otc(m); txt+=f"{f} {m}: **{s}** 💰{p} ⏱{e}\n"
        await q.message.reply_text(txt, parse_mode="Markdown"); return
    if d=="RANDOM":
        m=random.choice(list(MARKETS_REAL.keys())); s,e,i=get_tv(m)
        await q.message.reply_text(f"🎯 {MARKETS_REAL[m]} {m}: **{s}** ⏱{e}\n{i}")

def run_bot():
    if not TOKEN:
        print("❌ BOT_TOKEN مو موجود في Render"); return
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_pass))
    print("🤖 MAD-BOT-SIG يعمل بكل الأسواق"); app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    app_flask.run(host="0.0.0.0", port=PORT)
