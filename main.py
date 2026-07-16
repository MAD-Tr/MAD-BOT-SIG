import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tradingview_ta import TA_Handler, Interval

TOKEN = "8828337019:AAGBSoxz8K-3QjNTGX5OXHIV5og3_wANB58"
bot = telebot.TeleBot(TOKEN)

MARKETS = {
    # كل الاسواق الحقيقية
    "🇪🇺/🇺🇸 EUR/USD": "EURUSD",
    "🇬🇧/🇺🇸 GBP/USD": "GBPUSD",
    "🇺🇸/🇯🇵 USD/JPY": "USDJPY",
    "🇦🇺/🇺🇸 AUD/USD": "AUDUSD",
    "🇺🇸/🇨🇦 USD/CAD": "USDCAD",
    "🇪🇺/🇯🇵 EUR/JPY": "EURJPY",
    "🇨🇦/🇯🇵 CAD/JPY": "CADJPY",
    "🇪🇺/🇬🇧 EUR/GBP": "EURGBP",
    "🇦🇺/🇯🇵 AUD/JPY": "AUDJPY",
    "🇳🇿/🇺🇸 NZD/USD": "NZDUSD",
    "🇪🇺/🇨🇭 EUR/CHF": "EURCHF",
    "🇬🇧/🇯🇵 GBP/JPY": "GBPJPY",
    "🇦🇺/🇨🇦 AUD/CAD": "AUDCAD",
    "🇪🇺/🇦🇺 EUR/AUD": "EURAUD",
    "🇬🇧/🇨🇭 GBP/CHF": "GBPCHF",
    "🇺🇸/🇨🇭 USD/CHF": "USDCHF",
    "🇪🇺/🇨🇦 EUR/CAD": "EURCAD",
    "🇦🇺/🇨🇭 AUD/CHF": "AUDCHF",
    "🇬🇧/🇦🇺 GBP/AUD": "GBPAUD",
    "🇨🇦/🇨🇭 CAD/CHF": "CADCHF",
    "🇪🇺/🇳🇿 EUR/NZD": "EURNZD",
    "🇬🇧/🇳🇿 GBP/NZD": "GBPNZD",
    # 3 OTC فقط
    "🇪🇺/🇺🇸 EUR/USD OTC": "EURUSD",
    "🇬🇧/🇺🇸 GBP/USD OTC": "GBPUSD",
    "🇺🇸/🇯🇵 USD/JPY OTC": "USDJPY"
}

user_data = {}

def get_signal(symbol, tf):
    intervals = {"5": Interval.INTERVAL_5_MINUTES, "15": Interval.INTERVAL_15_MINUTES, "H1": Interval.INTERVAL_1_HOUR}
    handler = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=intervals[tf])
    s = handler.get_analysis().summary
    buy, sell, neu = s['BUY'], s['SELL'], s['NEUTRAL']
    total = buy + sell + neu
    direction = "BUY" if buy > sell else "SELL"
    percent = int((max(buy, sell) / total) * 100) if total > 0 else 0
    return direction, percent

@bot.message_handler(commands=['start'])
def start(msg):
    markup = InlineKeyboardMarkup(row_width=2)
    for name in MARKETS:
        markup.add(InlineKeyboardButton(name, callback_data=f"market_{name}"))
    bot.send_message(msg.chat.id, "اختر السوق:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_"))
def choose_market(call):
    name = call.data.replace("market_", "")
    user_data[call.from_user.id] = MARKETS[name], name
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("5m", callback_data="time_5"), InlineKeyboardButton("15m", callback_data="time_15"), InlineKeyboardButton("H1", callback_data="time_H1"))
    bot.send_message(call.message.chat.id, f"اخترت {name}\nاختر الفريم:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("time_"))
def choose_time(call):
    tf = call.data.replace("time_", "")
    symbol, name = user_data[call.from_user.id]
    bot.send_message(call.message.chat.id, f"⏳ جاري سحب اشارة {name} {tf} من TradingView...")
    direction, percent = get_signal(symbol, tf)
    emoji = "🟢" if direction == "BUY" else "🔴"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"قوة الاشارة: {percent}%", callback_data="x"))
    bot.send_message(call.message.chat.id, f"📊 {name} {tf}\n{emoji} {direction}\n💪 {percent}%", reply_markup=markup)

bot.polling()
