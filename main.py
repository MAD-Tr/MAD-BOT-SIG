import os
import time
import threading
from datetime import datetime, timedelta
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from tradingview_ta import TA_Handler, Interval

TOKEN = os.environ.get("TOKEN") or "8828337019:AAHgUTyjrxMk7IkJpMZzseKbroltKInaCes"
PASSWORD = os.environ.get("PASSWORD") or "7154"
bot = telebot.TeleBot(TOKEN, threaded=False)

MARKETS = {
    "🇪🇺/🇺🇸 EUR/USD": "EURUSD", "🇬🇧/🇺🇸 GBP/USD": "GBPUSD", "🇺🇸/🇯🇵 USD/JPY": "USDJPY",
    "🇦🇺/🇺🇸 AUD/USD": "AUDUSD", "🇺🇸/🇨🇦 USD/CAD": "USDCAD", "🇪🇺/🇯🇵 EUR/JPY": "EURJPY",
    "🇨🇦/🇯🇵 CAD/JPY": "CADJPY", "🇪🇺/🇬🇧 EUR/GBP": "EURGBP", "🇦🇺/🇯🇵 AUD/JPY": "AUDJPY",
    "🇳🇿/🇺🇸 NZD/USD": "NZDUSD", "🇪🇺/🇨🇭 EUR/CHF": "EURCHF", "🇬🇧/🇯🇵 GBP/JPY": "GBPJPY",
    "🇦🇺/🇨🇦 AUD/CAD": "AUDCAD", "🇪🇺/🇦🇺 EUR/AUD": "EURAUD", "🇬🇧/🇨🇭 GBP/CHF": "GBPCHF",
    "🇺🇸/🇨🇭 USD/CHF": "USDCHF", "🇪🇺/🇨🇦 EUR/CAD": "EURCAD", "🇦🇺/🇨🇭 AUD/CHF": "AUDCHF",
    "🇬🇧/🇦🇺 GBP/AUD": "GBPAUD", "🇨🇦/🇨🇭 CAD/CHF": "CADCHF", "🇪🇺/🇳🇿 EUR/NZD": "EURNZD",
    "🇬🇧/🇳🇿 GBP/NZD": "GBPNZD",
}

user_data = {}
last_request = {}
authorized = set()

# ===== نظام قفل الأسواق 30 دقيقة بعد الربح/الخسارة =====
locked_markets = {}  # {user_id: {market_name: unlock_timestamp}}
trade_stats = {}  # {user_id: {"wins": 0, "losses": 0}}

# ===== توقيت الجلسات - نفس الصورة بالضبط =====
def get_all_banks_status():
    now_utc = datetime.utcnow()
    now_ny = now_utc - timedelta(hours=4)
    h = now_ny.hour
    m = now_ny.minute
    s = now_ny.second
    now_total = h*3600 + m*60 + s
    
    banks = []
    
    # آسيا: 8م - 12ص = 20:00 - 24:00
    asia_start = 20*3600
    asia_end = 24*3600
    asia_open = now_total >= asia_start and now_total < asia_end
    if asia_open:
        remain = asia_end - now_total
        banks.append({"name": "آسيا", "flag": "🇯🇵", "open": True, "remain": remain, "time": "8م - 12ص"})
    else:
        # عداد لآسيا
        if now_total < asia_start:
            remain = asia_start - now_total
        else:
            remain = (24*3600 - now_total) + asia_start
        banks.append({"name": "آسيا", "flag": "🇯🇵", "open": False, "remain": remain, "time": "8م - 12ص"})
    
    # لندن: 2ص - 5ص = 02:00 - 05:00
    london_start = 2*3600
    london_end = 5*3600
    london_open = now_total >= london_start and now_total < london_end
    if london_open:
        remain = london_end - now_total
        banks.append({"name": "لندن", "flag": "🇬🇧", "open": True, "remain": remain, "time": "2ص - 5ص"})
    else:
        if now_total < london_start:
            remain = london_start - now_total
        elif now_total < london_end:
            remain = 0
        elif now_total < 24*3600:
            # بعد 5ص تفتح بعد 21 ساعة
            remain = (24*3600 - now_total) + london_start
        else:
            remain = 0
        if now_total >= 5*3600 and now_total < 7*3600:
            remain = (7*3600 - now_total) + (london_start - 7*3600 + 24*3600) # سيحسب لآسيا بعدين
            # نعيد حساب بسيط: لندن تفتح 2ص اليوم الجاي
            remain = (24*3600 - now_total) + london_start
        banks.append({"name": "لندن", "flag": "🇬🇧", "open": False if not london_open else True, "remain": remain if not london_open else london_end - now_total, "time": "2ص - 5ص"})
        # تصحيح منطقي
        if london_open:
            banks[-1] = {"name": "لندن", "flag": "🇬🇧", "open": True, "remain": london_end - now_total, "time": "2ص - 5ص"}
        else:
            if now_total < london_start:
                r = london_start - now_total
            else:
                r = (24*3600 - now_total) + london_start
            banks[-1] = {"name": "لندن", "flag": "🇬🇧", "open": False, "remain": r, "time": "2ص - 5ص"}
    
    # نيويورك: 7ص - 10ص = 07:00 - 10:00
    ny_start = 7*3600
    ny_end = 10*3600
    ny_open = now_total >= ny_start and now_total < ny_end
    if ny_open:
        remain = ny_end - now_total
        banks.append({"name": "نيويورك", "flag": "🇺🇸", "open": True, "remain": remain, "time": "7ص - 10ص"})
    else:
        if now_total < ny_start:
            r = ny_start - now_total
        else:
            r = (24*3600 - now_total) + ny_start
        banks.append({"name": "نيويورك", "flag": "🇺🇸", "open": False, "remain": r, "time": "7ص - 10ص"})
    
    return banks

def format_countdown(seconds):
    if seconds <= 0:
        return "00:00:00"
    hh = seconds // 3600
    mm = (seconds % 3600) // 60
    ss = seconds % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}"

# ===== تطبيق مصغر HTML للبنوك =====
BANKS_HTML = """
<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>البنوك</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#000;color:#fff;font-family:-apple-system,Arial;min-height:100vh;padding:16px}
.header{text-align:center;margin:20px 0}
.title{font-size:24px;font-weight:900;color:#ffcc00}
.subtitle{font-size:12px;color:#888;margin-top:4px}
.card{background:linear-gradient(135deg,#1a1a1a,#0a0a0a);border:1px solid #333;border-radius:18px;padding:16px;margin:12px 0;display:flex;justify-content:space-between;align-items:center;transition:all .3s}
.card.open{border-color:#00ff00;box-shadow:0 0 20px rgba(0,255,0,.3);background:linear-gradient(135deg,#0a1a0a,#000)}
.card.closed{border-color:#ff3333;box-shadow:0 0 15px rgba(255,0,0,.2)}
.bank-info{display:flex;align-items:center;gap:12px}
.flag{font-size:32px}
.bank-name{font-size:16px;font-weight:800}
.bank-time{font-size:11px;color:#888;margin-top:2px}
.status{font-size:13px;font-weight:800;padding:6px 12px;border-radius:20px}
.status.open{background:#00ff00;color:#000}
.status.closed{background:#ff0000;color:#fff}
.countdown{font-size:11px;color:#ffcc00;margin-top:4px;font-family:monospace}
.live-dot{display:inline-block;width:8px;height:8px;background:#00ff00;border-radius:50%;animation:blink 1s infinite;margin-left:4px}
@keyframes blink{0%,50%{opacity:1}51%,100%{opacity:0}}
.ny-time{text-align:center;background:#111;border-radius:12px;padding:10px;margin:16px 0;font-size:12px;color:#aaa}
.ny-time b{color:#fff;font-size:14px}
</style></head><body>
<div class="header">
<div class="title">🏦 عداد البنوك LIVE</div>
<div class="subtitle">بتوقيت نيويورك - يتحرك كل ثانية</div>
</div>
<div class="ny-time">🕐 نيويورك الآن: <b id="nyNow">--:--:--</b></div>
<div id="banks"></div>
<script>
function formatSec(sec){
  let h=Math.floor(sec/3600);
  let m=Math.floor((sec%3600)/60);
  let s=sec%60;
  return String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
}
function update(){
  let now=new Date();
  // نيويورك = UTC-4
  let ny=new Date(now.toLocaleString("en-US",{timeZone:"America/New_York"}));
  let h=ny.getHours();
  let m=ny.getMinutes();
  let s=ny.getSeconds();
  let total=h*3600+m*60+s;
  document.getElementById('nyNow').innerText=String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
  
  let banks=[
    {name:"آسيا",flag:"🇯🇵",start:20*3600,end:24*3600,time:"8م - 12ص"},
    {name:"لندن",flag:"🇬🇧",start:2*3600,end:5*3600,time:"2ص - 5ص"},
    {name:"نيويورك",flag:"🇺🇸",start:7*3600,end:10*3600,time:"7ص - 10ص"}
  ];
  
  let html='';
  banks.forEach(b=>{
    let isOpen=total>=b.start && total<b.end;
    let remain, countdownText;
    if(isOpen){
      remain=b.end-total;
      countdownText='مفتوحة - متبقي '+formatSec(remain);
    }else{
      let r;
      if(total<b.start) r=b.start-total;
      else r=(24*3600-total)+b.start;
      remain=r;
      countdownText='تفتح بعد '+formatSec(r);
    }
    let cardClass=isOpen?'open':'closed';
    let statusClass=isOpen?'open':'closed';
    let statusText=isOpen?'مفتوحة ✅':'مقفلة ❌';
    let liveDot=isOpen?'<span class="live-dot"></span>':'';
    
    html+='<div class="card '+cardClass+'">';
    html+='<div class="bank-info"><div class="flag">'+b.flag+'</div>';
    html+='<div><div class="bank-name">'+liveDot+b.name+'</div><div class="bank-time">'+b.time+'</div>';
    if(!isOpen) html+='<div class="countdown">⏰ '+countdownText+'</div>';
    else html+='<div class="countdown" style="color:#00ff00">'+countdownText+'</div>';
    html+='</div></div>';
    html+='<div class="status '+statusClass+'">'+statusText+'</div>';
    html+='</div>';
  });
  document.getElementById('banks').innerHTML=html;
}
update();
setInterval(update,1000);
</script></body></html>
"""

def get_tf_signal(symbol, interval):
    try:
        h = TA_Handler(symbol=symbol, screener="forex", exchange="FX", interval=interval)
        s = h.get_analysis().summary
        buys, sells = s['BUY'], s['SELL']
        if buys+sells == 0: return "NEUTRAL", 50
        direction = "BUY" if buys > sells else "SELL"
        percent = int((max(buys, sells) / (buys + sells)) * 100)
        return direction, percent
    except:
        return "ERROR", 0

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
        if base > 92: base = 92
        if base < 0: base = 0
        final = base
        if final >= 85:
            decision = "🔥🔥 ممتاز جدا - TOP ادخل 2% 🔥🔥"
        elif final >= 78:
            decision = "✅ ممتاز - ادخل 1.5%"
        elif final >= 70:
            decision = "✅ جيد - ادخل 1%"
        else:
            decision = "⚠️ متوسط - لا تدخل"
        return d5, final, f"H1:{p1h}% | 15m:{p15}% | 5m:{p5}%\n{decision}"
    return "NO_TRADE", 0, f"H1:{p1h}% {d1h} | 15m:{p15}% {d15} | 5m:{p5}% {d5}\n\n❌ متضارب"

def main_menu(chat_id):
    banks = get_all_banks_status()
    open_banks = [b for b in banks if b['open']]
    closed_banks = [b for b in banks if not b['open']]
    
    # عدد الأسواق المقفلة عند المستخدم
    user_locked_count = 0
    if chat_id in locked_markets:
        now = time.time()
        # نظف المنتهية
        to_del = [m for m, ut in locked_markets[chat_id].items() if now >= ut]
        for m in to_del:
            del locked_markets[chat_id][m]
        user_locked_count = len(locked_markets[chat_id])
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔥 البحث عن الفرصة الذهبية (22 سوق)", callback_data="golden"))
    markup.add(InlineKeyboardButton("📊 فحص سوق واحد", callback_data="single"))
    
    # زر التطبيق المصغر - البنوك
    base_url = os.environ.get("RENDER_EXTERNAL_URL") or "https://mad-bot.onrender.com"
    webapp_url = base_url.rstrip("/") + "/banks"
    markup.add(InlineKeyboardButton("🏦 تطبيق مصغر - عداد البنوك LIVE", web_app=WebAppInfo(url=webapp_url)))
    
    if user_locked_count > 0:
        markup.add(InlineKeyboardButton(f"🔒 أسواقك المقفلة ({user_locked_count}) - 30د", callback_data="locked_list"))
    
    # أزرار حالة سريعة
    for b in banks:
        if b['open']:
            markup.add(InlineKeyboardButton(f"{b['flag']} {b['name']} مفتوحة ✅ {format_countdown(b['remain'])}", callback_data="bank_info"))
        else:
            markup.add(InlineKeyboardButton(f"{b['flag']} {b['name']} مقفلة ❌ تفتح بعد {format_countdown(b['remain'])}", callback_data="bank_info"))
    
    if open_banks:
        text = f"💰 بوت احترافي\n\n"
        text += f"🏦 البنوك المفتوحة الآن:\n"
        for b in open_banks:
            text += f"{b['flag']} {b['name']} مفتوحة ✅ - متبقي {format_countdown(b['remain'])}\n"
        if closed_banks:
            text += f"\n⏳ البنوك المقفلة:\n"
            for b in closed_banks:
                text += f"{b['flag']} {b['name']} مقفلة ❌ - تفتح بعد {format_countdown(b['remain'])}\n"
        if user_locked_count > 0:
            text += f"\n🔒 أسواقك المقفلة: {user_locked_count} (30د)"
        text += f"\n\n👆 اضغط تطبيق مصغر لمشاهدة العداد يتحرك LIVE"
    else:
        text = f"💰 بوت احترافي\n\n⏳ كل البنوك مقفلة الآن\n\n"
        for b in banks:
            text += f"{b['flag']} {b['name']} مقفلة - تفتح بعد {format_countdown(b['remain'])}\n"
        if user_locked_count > 0:
            text += f"\n🔒 أسواقك المقفلة: {user_locked_count}"
        text += f"\n\n👆 اضغط تطبيق مصغر للعداد LIVE"
    
    bot.send_message(chat_id, text, reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id not in authorized:
        bot.send_message(msg.chat.id, "🔒 ارسل كلمة السر:")
        return
    main_menu(msg.chat.id)

@bot.message_handler(func=lambda m: m.from_user.id not in authorized)
def check_pass(m):
    if m.text.strip() == PASSWORD:
        authorized.add(m.from_user.id)
        bot.send_message(m.chat.id, "✅ تم فتح البوت")
        main_menu(m.chat.id)
    else:
        bot.send_message(m.chat.id, "❌ كلمة سر غلط")

@bot.callback_query_handler(func=lambda c: c.data=="single")
def single(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup(row_width=2)
    for name in MARKETS:
        markup.add(InlineKeyboardButton(name, callback_data=f"market_{name}"))
    bot.send_message(call.message.chat.id, "اختر السوق:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data=="bank_info")
def bank_info(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    banks = get_all_banks_status()
    text = f"🏦 حالة البنوك LIVE\n\n"
    for b in banks:
        if b['open']:
            text += f"{b['flag']} {b['name']}: مفتوحة ✅ - متبقي {format_countdown(b['remain'])}\n"
        else:
            text += f"{b['flag']} {b['name']}: مقفلة ❌ - تفتح بعد {format_countdown(b['remain'])}\n"
    text += f"\nتوقيت الجلسات (نيويورك):\n🇯🇵 آسيا: 8م-12ص\n🇬🇧 لندن: 2ص-5ص\n🇺🇸 نيويورك: 7ص-10ص"
    bot.send_message(call.message.chat.id, text)

@bot.callback_query_handler(func=lambda c: c.data=="golden")
def golden(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id, "⏳ افحص 22 سوق...")
    loading = bot.send_message(call.message.chat.id, f"⏳ افحص {len(MARKETS)} سوق...")
    goldens = []
    start_t = time.time()
    for name, sym in MARKETS.items():
        try:
            d, p, details = get_confluence_signal(sym)
            if d!= "NO_TRADE" and p >= 70:
                emoji = "🟢 BUY" if d=="BUY" else "🔴 SELL"
                goldens.append((p, f"{emoji} {name} - {p}%\n{details}\n"))
        except: continue
    goldens.sort(key=lambda x: x[0], reverse=True)
    elapsed = round(time.time() - start_t, 1)
    banks = get_all_banks_status()
    open_names = ", ".join([f"{b['flag']}{b['name']}" for b in banks if b['open']]) or "كلها مقفلة"
    if not goldens:
        bot.edit_message_text(f"🏦 {open_names}\n\n❌ فحصت {len(MARKETS)} سوق في {elapsed}ث - لا يوجد موثوق", call.message.chat.id, loading.message_id)
    else:
        best = goldens[0]
        text = f"🏦 {open_names}\n\n🏆 أفضل صفقة {best[0]}% 🏆\n{best[1]}\n"
        text += f"━━━━━━━━━━━━\n{len(goldens)} فرص في {elapsed}ث\n\n"
        for i, (p, detail) in enumerate(goldens, 1):
            crown = "👑" if i==1 else f"{i}."
            text += f"{crown} {detail}\n"
        bot.edit_message_text(text, call.message.chat.id, loading.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("market_"))
def choose_market(call):
    if call.from_user.id not in authorized: return
    bot.answer_callback_query(call.id)
    name = call.data.replace("market_", "")
    user_data[call.from_user.id] = MARKETS[name], name
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔍 فحص شامل H1+15m+5m", callback_data="time_ALL"))
    markup.add(InlineKeyboardButton("5m فقط", callback_data="time_5"), InlineKeyboardButton("15m فقط", callback_data="time_15"))
    bot.send_message(call.message.chat.id, f"📊 {name}\n\nاختر الفحص:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("time_"))
def choose_time(call):
    if call.from_user.id not in authorized: return
    user_id = call.from_user.id
    now = time.time()
    
    # فحص القفل
    symbol_check, name_check = user_data.get(user_id, (None, None))
    if name_check and user_id in locked_markets and name_check in locked_markets[user_id]:
        unlock_time = locked_markets[user_id][name_check]
        if now < unlock_time:
            remain = int(unlock_time - now)
            mm = remain // 60
            ss = remain % 60
            bot.answer_callback_query(call.id, f"🔒 {name_check} مقفل - يفتح بعد {mm}:{ss:02d}")
            bot.send_message(call.message.chat.id, f"🔒 {name_check} مقفل حاليا\n⏰ يفتح بعد {mm} دقيقة و {ss} ثانية\n\nلا تتداول عليه عشان ما تخسر")
            return
        else:
            # انتهى القفل
            del locked_markets[user_id][name_check]
    
    if user_id in last_request and now - last_request[user_id] < 3:
        bot.answer_callback_query(call.id, "⏳ انتظر 3 ثواني")
        return
    last_request[user_id] = now
    bot.answer_callback_query(call.id)
    mode = call.data.replace("time_", "")
    symbol, name = user_data.get(user_id, (None, None))
    if not symbol: return
    loading = bot.send_message(call.message.chat.id, f"⏳ فحص {name}...")
    if mode == "ALL":
        direction, percent, details = get_confluence_signal(symbol)
        if direction == "NO_TRADE":
            bot.edit_message_text(f"📊 {name}\n\n{details}", call.message.chat.id, loading.message_id)
            return
        emoji = "🟢 BUY صعود" if direction == "BUY" else "🔴 SELL هبوط"
        # أزرار ربح/خسارة بعد الإشارة
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("✅ ربح - اقفل 30د", callback_data=f"win_{name}"),
            InlineKeyboardButton("❌ خسارة - اقفل 30د", callback_data=f"loss_{name}")
        )
        markup.add(InlineKeyboardButton("🔒 الأسواق المقفلة", callback_data="locked_list"))
        bot.edit_message_text(f"📊 {name}\n{emoji}\n💪 {percent}%\n\n{details}\n\n👇 بعد التداول اضغط ربح أو خسارة ليقفل 30 دقيقة", call.message.chat.id, loading.message_id, reply_markup=markup)
    else:
        tf_map = {"5": Interval.INTERVAL_5_MINUTES, "15": Interval.INTERVAL_15_MINUTES}
        d, p = get_tf_signal(symbol, tf_map[mode])
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("✅ ربح - اقفل 30د", callback_data=f"win_{name}"),
            InlineKeyboardButton("❌ خسارة - اقفل 30د", callback_data=f"loss_{name}")
        )
        bot.edit_message_text(f"📊 {name} {mode}m\n{'🟢 BUY' if d=='BUY' else '🔴 SELL'}\n💪 {p}%\n\n{'✅ ادخل' if p>=70 else '❌ لا تدخل'}\n\n👇 بعد التداول اضغط ربح أو خسارة", call.message.chat.id, loading.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("win_") or c.data.startswith("loss_"))
def handle_win_loss(call):
    if call.from_user.id not in authorized: return
    user_id = call.from_user.id
    is_win = call.data.startswith("win_")
    market_name = call.data.replace("win_", "").replace("loss_", "")
    
    now = time.time()
    unlock_time = now + 30*60  # 30 دقيقة
    
    if user_id not in locked_markets:
        locked_markets[user_id] = {}
    locked_markets[user_id][market_name] = unlock_time
    
    if user_id not in trade_stats:
        trade_stats[user_id] = {"wins": 0, "losses": 0}
    
    if is_win:
        trade_stats[user_id]["wins"] += 1
        emoji = "✅"
        result = "ربح"
        color = "🟢"
    else:
        trade_stats[user_id]["losses"] += 1
        emoji = "❌"
        result = "خسارة"
        color = "🔴"
    
    # عداد تنازلي للقفل
    def format_lock(sec):
        m = sec // 60
        s = sec % 60
        return f"{m:02d}:{s:02d}"
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔒 شوف الأسواق المقفلة", callback_data="locked_list"))
    markup.add(InlineKeyboardButton("🔥 فرصة ذهبية جديدة", callback_data="golden"))
    
    wins = trade_stats[user_id]["wins"]
    losses = trade_stats[user_id]["losses"]
    total = wins + losses
    win_rate = int((wins/total)*100) if total>0 else 0
    
    text = f"{color} {emoji} سجلت {result} في {market_name}\n\n"
    text += f"🔒 {market_name} مقفل الآن 30 دقيقة\n"
    text += f"⏰ يفتح بعد: 30:00\n\n"
    text += f"📊 إحصائياتك:\n"
    text += f"✅ أرباح: {wins}\n"
    text += f"❌ خسائر: {losses}\n"
    text += f"📈 نسبة الربح: {win_rate}%\n\n"
    text += f"💡 لا تتداول على نفس السوق لمدة 30 دقيقة عشان ما تخسر"
    
    bot.answer_callback_query(call.id, f"{emoji} {market_name} مقفل 30د")
    bot.send_message(call.message.chat.id, text, reply_markup=markup)
    
    # عداد لايف للقفل يتحرك
    sent = bot.send_message(call.message.chat.id, f"🔒 {market_name} مقفل ⏰ 30:00 - يتحرك LIVE")
    
    def live_lock_countdown(chat_id, msg_id, market, unlock):
        while True:
            time.sleep(1)
            now2 = time.time()
            remain = int(unlock - now2)
            if remain <= 0:
                try:
                    bot.edit_message_text(f"🔓 {market} انفتح الآن ✅\nتقدر تتداول عليه", chat_id, msg_id)
                except:
                    pass
                # احذف القفل
                if chat_id in locked_markets and market in locked_markets.get(chat_id, {}):
                    try:
                        del locked_markets[chat_id][market]
                    except:
                        pass
                break
            try:
                mm = remain // 60
                ss = remain % 60
                bot.edit_message_text(f"🔒 {market} مقفل ⏰ {mm:02d}:{ss:02d} - يتحرك LIVE 🔴", chat_id, msg_id)
            except:
                break
    
    threading.Thread(target=live_lock_countdown, args=(call.message.chat.id, sent.message_id, market_name, unlock_time), daemon=True).start()

@bot.callback_query_handler(func=lambda c: c.data=="locked_list")
def locked_list(call):
    if call.from_user.id not in authorized: return
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)
    
    if user_id not in locked_markets or not locked_markets[user_id]:
        bot.send_message(call.message.chat.id, "🔓 لا يوجد أسواق مقفلة حاليا\nتقدر تتداول على كل الأسواق ✅")
        return
    
    now = time.time()
    text = "🔒 الأسواق المقفلة (30 دقيقة):\n\n"
    has_locked = False
    to_remove = []
    
    for market, unlock_time in locked_markets[user_id].items():
        remain = int(unlock_time - now)
        if remain <= 0:
            to_remove.append(market)
        else:
            mm = remain // 60
            ss = remain % 60
            text += f"🔒 {market} - يفتح بعد {mm:02d}:{ss:02d}\n"
            has_locked = True
    
    for m in to_remove:
        del locked_markets[user_id][m]
    
    if not has_locked:
        text = "🔓 كل الأسواق مفتوحة الآن ✅\nتقدر تتداول"
    
    if user_id in trade_stats:
        wins = trade_stats[user_id]["wins"]
        losses = trade_stats[user_id]["losses"]
        total = wins + losses
        win_rate = int((wins/total)*100) if total>0 else 0
        text += f"\n\n📊 إحصائياتك:\n✅ {wins} ربح\n❌ {losses} خسارة\n📈 {win_rate}% نسبة ربح"
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔓 فتح الكل الآن", callback_data="unlock_all"))
    
    bot.send_message(call.message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data=="unlock_all")
def unlock_all(call):
    if call.from_user.id not in authorized: return
    user_id = call.from_user.id
    if user_id in locked_markets:
        locked_markets[user_id].clear()
    bot.answer_callback_query(call.id, "🔓 فتحت كل الأسواق")
    bot.send_message(call.message.chat.id, "🔓 فتحت كل الأسواق المقفلة ✅\nتقدر تتداول الآن")

app = Flask(__name__)
@app.route('/')
def home(): return "Bot Live - Banks + Lock 30m"
@app.route('/health')
def health(): return "OK"
@app.route('/banks')
def banks_page(): return BANKS_HTML

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

threading.Thread(target=run_flask, daemon=True).start()
bot.remove_webhook()
time.sleep(2)
while True:
    try:
        bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)
