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
locked_markets = {}
trade_stats = {}

def get_all_banks_status():
    now_utc = datetime.utcnow()
    now_sa = now_utc + timedelta(hours=3)
    now_total = now_sa.hour*3600 + now_sa.minute*60 + now_sa.second
    banks = []
    for name, flag, s_h, e_h, t in [("آسيا","🇯🇵",3,7,"3ص-7ص"),("لندن","🇬🇧",9,12,"9ص-12ظ"),("نيويورك","🇺🇸",14,17,"2م-5م")]:
        s,e = s_h*3600, e_h*3600
        open_ = now_total >= s and now_total < e
        r = e-now_total if open_ else (s-now_total if now_total < s else (24*3600-now_total)+s)
        banks.append({"name": name, "flag": flag, "open": open_, "remain": r, "time": t})
    return banks

def format_countdown(s):
    if s<=0: return "00:00:00"
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

# ===== تطبيق مصغر Mr.Pocket Style - أحسن وأفضل =====
BANKS_HTML = """
<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MAD-BOT - Mr.Pocket Pro</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0a0a;color:#fff;font-family:Consolas,Monaco,monospace;min-height:100vh;padding:10px}
.header{text-align:center;margin:10px 0;background:linear-gradient(135deg,#1a1a00,#000);border:1px solid #ffcc00;border-radius:12px;padding:12px}
.title{font-size:22px;font-weight:900;color:#ffcc00;text-shadow:0 0 10px #ffcc00}
.crown{font-size:28px}
.sa-time{display:flex;justify-content:space-between;background:#111;border-radius:10px;padding:10px;margin:10px 0;font-size:11px}
.sa-time b{color:#00ff00;font-size:14px}
.mt4-panel{background:#000;border:1px solid #333;border-radius:8px;padding:8px;margin:8px 0}
.mt4-header{display:flex;justify-content:space-between;font-size:10px;color:#888;border-bottom:1px solid #222;padding-bottom:4px}
.candle{display:flex;align-items:center;gap:4px;margin:4px 0;font-size:12px}
.candle.green{color:#00ff00}
.candle.red{color:#ff0000}
.price{font-weight:900;background:#111;padding:2px 6px;border-radius:4px;font-size:13px}
.arrow{font-size:18px}
.bank-card{display:flex;justify-content:space-between;align-items:center;background:linear-gradient(135deg,#1a1a1a,#0a0a0a);border:1px solid #333;border-radius:12px;padding:12px;margin:8px 0}
.bank-card.open{border-color:#00ff00;box-shadow:0 0 15px rgba(0,255,0,.2)}
.bank-card.closed{border-color:#ff3333;opacity:.7}
.live-dot{width:8px;height:8px;background:#00ff00;border-radius:50%;display:inline-block;animation:blink 1s infinite;margin-left:4px}
@keyframes blink{0%,50%{opacity:1}51%,100%{opacity:0}}
.signal-box{background:linear-gradient(135deg,#0a1a0a,#000);border:2px solid #00ff00;border-radius:12px;padding:12px;margin:10px 0;text-align:center}
.signal-box.sell{border-color:#ff0000;background:linear-gradient(135deg,#1a0a0a,#000)}
.entry{font-size:18px;font-weight:900;color:#ffcc00}
.countdown{font-family:monospace;color:#ffcc00;font-size:11px;margin-top:4px}
</style></head><body>
<div class="header">
<div class="crown">👑</div>
<div class="title">MR.POCKET - MAD-BOT PRO</div>
<div style="font-size:10px;color:#888;margin-top:4px">أحسن من الأصلي - بتوقيت السعودية 🇸🇦</div>
</div>

<div class="sa-time">
<div>🇸🇦 <b id="saNow">--:--:--</b><br><span style="font-size:9px;color:#666">السعودية الآن</span></div>
<div style="text-align:center">⏰ شمعة<br><b id="candleTimer" style="color:#ffcc00">00:00</b></div>
<div style="text-align:left">🏦 بنك<br><b id="activeBank" style="color:#00ff00">--</b></div>
</div>

<div class="mt4-panel">
<div class="mt4-header"><span>XM Global - EUR/JPY M1</span><span>AutoTrading</span></div>
<div id="mt4Chart"></div>
</div>

<div id="banks"></div>

<div id="liveSignals"></div>

<script>
function formatSec(sec){
  let h=Math.floor(sec/3600), m=Math.floor((sec%3600)/60), s=sec%60;
  return String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
}
function formatMinSec(sec){
  let m=Math.floor(sec/60), s=sec%60;
  return String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
}
let mockPrice = 185.044;
function update(){
  let now=new Date();
  let sa=new Date(now.toLocaleString("en-US",{timeZone:"Asia/Riyadh"}));
  let h=sa.getHours(), m=sa.getMinutes(), s=sa.getSeconds(), total=h*3600+m*60+s;
  document.getElementById('saNow').innerText=String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
  
  // عداد الشمعة (مثل الصورة 00:29)
  let secInCandle = 60 - s;
  let minInTF = 15 - (m % 15);
  document.getElementById('candleTimer').innerText=String(minInTF-1).padStart(2,'0')+':'+String(secInCandle).padStart(2,'0');
  
  let banks=[
    {name:"آسيا",flag:"🇯🇵",start:3*3600,end:7*3600,time:"3ص-7ص"},
    {name:"لندن",flag:"🇬🇧",start:9*3600,end:12*3600,time:"9ص-12ظ"},
    {name:"نيويورك",flag:"🇺🇸",start:14*3600,end:17*3600,time:"2م-5م"}
  ];
  
  let activeBank = "مقفلة";
  banks.forEach(b=>{
    if(total>=b.start && total<b.end) activeBank=b.name;
  });
  document.getElementById('activeBank').innerText=activeBank;
  
  // محاكاة شارت MT4 مثل الصورة
  mockPrice += (Math.random()-0.5)*0.02;
  let chartHtml='';
  for(let i=0;i<5;i++){
    let isGreen = Math.random()>0.4;
    let cls = isGreen?'green':'red';
    let arrow = i==2 ? (isGreen ? '<span class="arrow">⬆️</span>' : '<span class="arrow">⬇️</span>') : '';
    let price = (mockPrice + (Math.random()-0.5)*0.5).toFixed(3);
    chartHtml+='<div class="candle '+cls+'">'+arrow+'<span class="price">'+price+'</span><span>'+(isGreen?'🟩':'🟥')+'</span></div>';
  }
  document.getElementById('mt4Chart').innerHTML=chartHtml;
  
  let banksHtml='';
  banks.forEach(b=>{
    let isOpen=total>=b.start && total<b.end;
    let remain=isOpen?b.end-total:(total<b.start?b.start-total:(24*3600-total)+b.start);
    let cardClass=isOpen?'open':'closed';
    let statusText=isOpen?'مفتوحة ✅':'مقفلة ❌';
    let liveDot=isOpen?'<span class="live-dot"></span>':'';
    let cd=isOpen?'متبقي '+formatSec(remain):'تفتح بعد '+formatSec(remain);
    banksHtml+='<div class="bank-card '+cardClass+'"><div style="display:flex;align-items:center;gap:8px"><div style="font-size:24px">'+b.flag+'</div><div><div style="font-weight:800;font-size:13px">'+liveDot+b.name+'</div><div style="font-size:10px;color:#888">'+b.time+'</div><div class="countdown">⏰ '+cd+'</div></div></div><div style="font-size:11px;font-weight:800;padding:4px 8px;border-radius:12px;background:'+(isOpen?'#00ff00':'#ff0000')+';color:'+(isOpen?'#000':'#fff')+'">'+statusText+'</div></div>';
  });
  document.getElementById('banks').innerHTML=banksHtml;
  
  // إشارة لايف مثل Mr.Pocket
  let signalsHtml='';
  if(Math.random()>0.7){
    let isBuy = Math.random()>0.5;
    let conf = 78 + Math.floor(Math.random()*15);
    let entry = mockPrice.toFixed(3);
    let target = (isBuy ? mockPrice+0.2 : mockPrice-0.2).toFixed(3);
    let cls = isBuy?'':'sell';
    let emoji = isBuy?'🟢 BUY':'🔴 SELL';
    let priceColor = isBuy?'#00ff00':'#ff0000';
    signalsHtml='<div class="signal-box '+cls+'"><div style="font-size:14px;font-weight:900">'+emoji+' EUR/JPY - '+conf+'%</div><div class="entry" style="color:'+priceColor+'">'+entry+'</div><div style="font-size:11px">دخول: '+entry+' | هدف: '+target+'</div><div style="font-size:10px;color:#888;margin-top:4px">⏰ 00:29 | 🏦 '+activeBank+'</div></div>';
  }
  if(signalsHtml) document.getElementById('liveSignals').innerHTML=signalsHtml;
}
update();
setInterval(update,1000);
// تحديث السعر كل 200ms مثل MT4
setInterval(()=>{ mockPrice += (Math.random()-0.5)*0.01; },200);
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
        if final >= 85: decision = "🔥🔥 ممتاز جدا - TOP ادخل 2% 🔥🔥"
        elif final >= 78: decision = "✅ ممتاز - ادخل 1.5%"
        elif final >= 70: decision = "✅ جيد - ادخل 1%"
        else: decision = "⚠️ متوسط - لا تدخل"
        return d5, final, f"H1:{p1h}% | 15m:{p15}% | 5m:{p5}%\n{decision}", p5, p15, p1h
    return "NO_TRADE", 0, f"H1:{p1h}% {d1h} | 15m:{p15}% {d15} | 5m:{p5}% {d5}\n\n❌ متضارب", p5, p15, p1h

def get_all_banks_status():
    now_utc = datetime.utcnow()
    now_sa = now_utc + timedelta(hours=3)
    now_total = now_sa.hour*3600 + now_sa.minute*60 + now_sa.second
    banks = []
    for name, flag, s_h, e_h, t in [("آسيا","🇯🇵",3,7,"3ص-7ص"),("لندن","🇬🇧",9,12,"9ص-12ظ"),("نيويورك","🇺🇸",14,17,"2م-5م")]:
        s,e = s_h*3600, e_h*3600
        open_ = now_total >= s and now_total < e
        r = e-now_total if open_ else (s-now_total if now_total < s else (24*3600-now_total)+s)
        banks.append({"name": name, "flag": flag, "open": open_, "remain": r, "time": t})
    return banks

def format_countdown(s):
    if s<=0: return "00:00:00"
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

user_data = {}
last_request = {}
authorized = set()
locked_markets = {}
trade_stats = {}

def main_menu(chat_id):
    banks = get_all_banks_status()
    open_banks = [b for b in banks if b['open']]
    user_locked_count = 0
    if chat_id in locked_markets:
        now = time.time()
        to_del = [m for m, ut in locked_markets[chat_id].items() if now >= ut]
        for m in to_del: del locked_markets[chat_id][m]
        user_locked_count = len(locked_markets[chat_id])
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔥 البحث عن الفرصة الذهبية (22 سوق)", callback_data="golden"))
    markup.add(InlineKeyboardButton("📊 فحص سوق واحد", callback_data="single"))
    base_url = os.environ.get("RENDER_EXTERNAL_URL") or "https://mad-bot.onrender.com"
    webapp_url = base_url.rstrip("/") + "/banks"
    markup.add(InlineKeyboardButton("👑 MR.POCKET PRO - تطبيق مصغر MT4 Style", web_app=WebAppInfo(url=webapp_url)))
    if user_locked_count > 0:
        markup.add(InlineKeyboardButton(f"🔒 أسواقك المقفلة ({user_locked_count}) - 30د", callback_data="locked_list"))
    for b in banks:
        if b['open']:
            markup.add(InlineKeyboardButton(f"{b['flag']} {b['name']} مفتوحة ✅ {format_countdown(b['remain'])}", callback_data="bank_info"))
        else:
            markup.add(InlineKeyboardButton(f"{b['flag']} {b['name']} مقفلة ❌ تفتح بعد {format_countdown(b['remain'])}", callback_data="bank_info"))
    now_sa = datetime.utcnow() + timedelta(hours=3)
    time_str = now_sa.strftime("%I:%M %p")
    if open_banks:
        text = f"👑 MAD-BOT PRO - أحسن من Mr.Pocket\n\n🇸🇦 الآن: {time_str}\n\n🏦 المفتوحة:\n"
        for b in open_banks:
            text += f"{b['flag']} {b['name']} مفتوحة ✅ - متبقي {format_countdown(b['remain'])} - {b['time']}\n"
        text += f"\n🔥 أفضل وقت 9ص-5م 🇸🇦"
    else:
        text = f"👑 MAD-BOT PRO 🇸🇦\n\n⏰ الآن: {time_str}\n\n⏳ كل البنوك مقفلة\n"
        for b in banks:
            text += f"{b['flag']} {b['name']} مقفلة - تفتح بعد {format_countdown(b['remain'])} - {b['time']}\n"
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
    text = f"🏦 حالة البنوك - السعودية 🇸🇦\n\n"
    for b in banks:
        if b['open']:
            text += f"{b['flag']} {b['name']}: مفتوحة ✅ - متبقي {format_countdown(b['remain'])} - {b['time']}\n"
        else:
            text += f"{b['flag']} {b['name']}: مقفلة ❌ - تفتح بعد {format_countdown(b['remain'])} - {b['time']}\n"
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
            d, p, details, p5, p15, p1h = get_confluence_signal(sym)
            if d!= "NO_TRADE" and p >= 70:
                emoji = "🟢 BUY" if d=="BUY" else "🔴 SELL"
                # مثل Mr.Pocket مع أسعار
                mock_price = 185.044 + (hash(sym) % 100)/1000
                entry_price = f"{mock_price:.3f}"
                target_price = f"{mock_price + 0.15 if d=='BUY' else mock_price - 0.15:.3f}"
                goldens.append((p, f"{emoji} {name} - {p}%\n💰 دخول: {entry_price} | هدف: {target_price}\n{details}\n"))
        except: continue
    goldens.sort(key=lambda x: x[0], reverse=True)
    elapsed = round(time.time() - start_t, 1)
    banks = get_all_banks_status()
    open_names = ", ".join([f"{b['flag']}{b['name']}" for b in banks if b['open']]) or "كلها مقفلة"
    if not goldens:
        bot.edit_message_text(f"🏦 {open_names}\n\n❌ فحصت {len(MARKETS)} سوق في {elapsed}ث - لا يوجد موثوق", call.message.chat.id, loading.message_id)
    else:
        best = goldens[0]
        text = f"👑 MR.POCKET PRO - {open_names}\n\n🏆 أفضل صفقة {best[0]}% 🏆\n{best[1]}\n━━━━━━━━━━━━\n{len(goldens)} فرص في {elapsed}ث\n\n"
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
    markup.add(InlineKeyboardButton("🔍 فحص شامل H1+15m+5m مثل Mr.Pocket", callback_data="time_ALL"))
    markup.add(InlineKeyboardButton("5m فقط", callback_data="time_5"), InlineKeyboardButton("15m فقط", callback_data="time_15"))
    bot.send_message(call.message.chat.id, f"📊 {name}\nمثل Mr.Pocket - فحص شامل:\n\nاختر الفحص:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("time_"))
def choose_time(call):
    if call.from_user.id not in authorized: return
    user_id = call.from_user.id
    now = time.time()
    symbol_check, name_check = user_data.get(user_id, (None, None))
    if name_check and user_id in locked_markets and name_check in locked_markets[user_id]:
        unlock_time = locked_markets[user_id][name_check]
        if now < unlock_time:
            remain = int(unlock_time - now)
            mm = remain // 60
            ss = remain % 60
            bot.answer_callback_query(call.id, f"🔒 {name_check} مقفل - يفتح بعد {mm}:{ss:02d}")
            bot.send_message(call.message.chat.id, f"🔒 {name_check} مقفل حاليا\n⏰ يفتح بعد {mm} دقيقة و {ss} ثانية")
            return
        else:
            del locked_markets[user_id][name_check]
    if user_id in last_request and now - last_request[user_id] < 3:
        bot.answer_callback_query(call.id, "⏳ انتظر 3 ثواني")
        return
    last_request[user_id] = now
    bot.answer_callback_query(call.id)
    mode = call.data.replace("time_", "")
    symbol, name = user_data.get(user_id, (None, None))
    if not symbol: return
    loading = bot.send_message(call.message.chat.id, f"⏳ فحص {name} مثل Mr.Pocket...")
    if mode == "ALL":
        direction, percent, details, p5, p15, p1h = get_confluence_signal(symbol)
        if direction == "NO_TRADE":
            bot.edit_message_text(f"📊 {name}\n\n{details}\n\n⏰ 00:29 - مثل صورة Mr.Pocket", call.message.chat.id, loading.message_id)
            return
        emoji = "🟢 BUY صعود ⬆️" if direction == "BUY" else "🔴 SELL هبوط ⬇️"
        mock_price = 185.044 + (hash(symbol) % 100)/1000
        entry_price = f"{mock_price:.3f}"
        # مثل صورة Mr.Pocket: 185.138, 12:29, 02:29, 00:29
        now_sa = datetime.utcnow() + timedelta(hours=3)
        time_str = now_sa.strftime("%H:%M:%S")
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(InlineKeyboardButton("✅ ربح - اقفل 30د", callback_data=f"win_{name}"), InlineKeyboardButton("❌ خسارة - اقفل 30د", callback_data=f"loss_{name}"))
        markup.add(InlineKeyboardButton("🔒 الأسواق المقفلة", callback_data="locked_list"))
        text = f"👑 {name}\n{emoji}\n\n💰 دخول: {entry_price}\n💪 ثقة: {percent}%\n\n{details}\n\n⏰ {time_str} - عداد مثل Mr.Pocket\n📍 12:29 | 02:29 | 00:29\n\n👇 بعد التداول اضغط ربح أو خسارة"
        bot.edit_message_text(text, call.message.chat.id, loading.message_id, reply_markup=markup)
    else:
        tf_map = {"5": Interval.INTERVAL_5_MINUTES, "15": Interval.INTERVAL_15_MINUTES}
        d, p = get_tf_signal(symbol, tf_map[mode])
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(InlineKeyboardButton("✅ ربح - اقفل 30د", callback_data=f"win_{name}"), InlineKeyboardButton("❌ خسارة - اقفل 30د", callback_data=f"loss_{name}"))
        bot.edit_message_text(f"📊 {name} {mode}m\n{'🟢 BUY ⬆️' if d=='BUY' else '🔴 SELL ⬇️'}\n💪 {p}%\n\n{'✅ ادخل' if p>=70 else '❌ لا تدخل'}\n\n⏰ 00:29", call.message.chat.id, loading.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("win_") or c.data.startswith("loss_"))
def handle_win_loss(call):
    if call.from_user.id not in authorized: return
    user_id = call.from_user.id
    is_win = call.data.startswith("win_")
    market_name = call.data.replace("win_", "").replace("loss_", "")
    now = time.time()
    unlock_time = now + 30*60
    if user_id not in locked_markets: locked_markets[user_id] = {}
    locked_markets[user_id][market_name] = unlock_time
    if user_id not in trade_stats: trade_stats[user_id] = {"wins": 0, "losses": 0}
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
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔒 شوف الأسواق المقفلة", callback_data="locked_list"))
    markup.add(InlineKeyboardButton("🔥 فرصة ذهبية جديدة", callback_data="golden"))
    wins = trade_stats[user_id]["wins"]
    losses = trade_stats[user_id]["losses"]
    total = wins + losses
    win_rate = int((wins/total)*100) if total>0 else 0
    text = f"{color} {emoji} سجلت {result} في {market_name}\n\n🔒 {market_name} مقفل الآن 30 دقيقة\n⏰ يفتح بعد: 30:00\n\n📊 إحصائياتك:\n✅ أرباح: {wins}\n❌ خسائر: {losses}\n📈 نسبة الربح: {win_rate}%\n\n💡 لا تتداول على نفس السوق لمدة 30 دقيقة"
    bot.answer_callback_query(call.id, f"{emoji} {market_name} مقفل 30د")
    bot.send_message(call.message.chat.id, text, reply_markup=markup)
    sent = bot.send_message(call.message.chat.id, f"🔒 {market_name} مقفل ⏰ 30:00 - يتحرك LIVE")
    def live_lock_countdown(chat_id, msg_id, market, unlock):
        while True:
            time.sleep(1)
            now2 = time.time()
            remain = int(unlock - now2)
            if remain <= 0:
                try: bot.edit_message_text(f"🔓 {market} انفتح الآن ✅\nتقدر تتداول عليه", chat_id, msg_id)
                except: pass
                if chat_id in locked_markets and market in locked_markets.get(chat_id, {}):
                    try: del locked_markets[chat_id][market]
                    except: pass
                break
            try:
                mm = remain // 60
                ss = remain % 60
                bot.edit_message_text(f"🔒 {market} مقفل ⏰ {mm:02d}:{ss:02d} - يتحرك LIVE 🔴", chat_id, msg_id)
            except: break
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
        if remain <= 0: to_remove.append(market)
        else:
            mm = remain // 60
            ss = remain % 60
            text += f"🔒 {market} - يفتح بعد {mm:02d}:{ss:02d}\n"
            has_locked = True
    for m in to_remove: del locked_markets[user_id][m]
    if not has_locked: text = "🔓 كل الأسواق مفتوحة الآن ✅\nتقدر تتداول"
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
    if user_id in locked_markets: locked_markets[user_id].clear()
    bot.answer_callback_query(call.id, "🔓 فتحت كل الأسواق")
    bot.send_message(call.message.chat.id, "🔓 فتحت كل الأسواق المقفلة ✅\nتقدر تتداول الآن")

app = Flask(__name__)
@app.route('/')
def home(): return "Bot Live - Mr.Pocket Pro"
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
