# ========== ADD THESE ENV VARS IN RENDER ==========
# GC_TO_SPOT_OFFSET = 9.55 (your $3923-$3913 gap)
# PRIVATE_CHANNEL_ID = -100xxxxxxxxxx
# PUBLIC_CHANNEL_ID = -100yyyyyyyyyy or @YourPublic

GC_TO_SPOT_OFFSET = float(os.environ.get("GC_TO_SPOT_OFFSET", "9.55"))
PRIVATE_CHANNEL_ID = os.environ.get("PRIVATE_CHANNEL_ID")
PUBLIC_CHANNEL_ID = os.environ.get("PUBLIC_CHANNEL_ID")

# ========== REPLACE get_scalp FUNCTION WITH THIS ==========
def get_scalp(ticker):
    if ticker.upper() == "NVDIA": ticker = "NVDA"
    orig_ticker = ticker.upper()
    
    df = fetch_direct(ticker, "5d", "5m")
    if df.empty: df = fetch_direct(ticker, "1d", "5m")
    if df.empty:
        return f"❌ Scalp: No 5m data for {ticker}. Try /scalp NVDA", False
    
    price_raw = float(df['Close'].iloc[-1])
    
    # FIX FOR RENDER: Convert GC=F futures to XAUUSD spot
    is_gold = orig_ticker in ["GC=F", "XAUUSD", "GOLD", "XAUUSD=X"]
    if orig_ticker == "GC=F":
        price = price_raw - GC_TO_SPOT_OFFSET
        display_ticker = "XAUUSD (from GC=F)"
    else:
        price = price_raw
        display_ticker = orig_ticker

    df['EMA9'] = df['Close'].ewm(span=9).mean()
    df['EMA21'] = df['Close'].ewm(span=21).mean()
    df['EMA50'] = df['Close'].ewm(span=50).mean()
    ema9_raw = float(df['EMA9'].iloc[-1])
    ema21_raw = float(df['EMA21'].iloc[-1])
    ema50_raw = float(df['EMA50'].iloc[-1])

    # Adjust EMAs to spot too if GC=F
    if orig_ticker == "GC=F":
        ema9 = ema9_raw - GC_TO_SPOT_OFFSET
        ema21 = ema21_raw - GC_TO_SPOT_OFFSET
        ema50 = ema50_raw - GC_TO_SPOT_OFFSET
    else:
        ema9, ema21, ema50 = ema9_raw, ema21_raw, ema50_raw

    delta = df['Close'].diff()
    gain = delta.where(delta>0,0).rolling(14).mean()
    loss = -delta.where(delta<0,0).rolling(14).mean()
    rsi = 100 - (100/(1+gain/loss))
    rsi_val = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
    atr = float((df['High']-df['Low']).rolling(14).mean().iloc[-1])
    change = float((price_raw - df['Close'].iloc[-2])/df['Close'].iloc[-2]*100)

    if ema9 > ema21 > ema50 and rsi_val > 45 and rsi_val < 70 and price_raw > ema9_raw:
        sig="🟢 SCALP BUY - EMA BULL"; strong=True; sl=price-atr*1.2; tp1=price+atr*1.0; tp2=price+atr*2.0
        entry1 = price
        entry2 = ema9
        entry3 = ema21
    elif ema9 < ema21 < ema50 and rsi_val < 55 and price_raw < ema9_raw:
        sig="🔴 SCALP SELL - EMA BEAR"; strong=True; sl=price+atr*1.2; tp1=price-atr*1.0; tp2=price-atr*2.0
        entry1 = price
        entry2 = ema9
        entry3 = ema21
    elif rsi_val < 28:
        sig="🔵 SCALP BUY - OVERSOLD 5M"; strong=True; sl=price-atr; tp1=price+atr*1.5; tp2=price+atr*2.5
        entry1 = price; entry2 = price-atr*0.5; entry3 = price-atr
    elif rsi_val > 72:
        sig="🟠 SCALP SELL - OVERBOUGHT 5M"; strong=True; sl=price+atr; tp1=price-atr*1.5; tp2=price-atr*2.5
        entry1 = price; entry2 = price+atr*0.5; entry3 = price+atr
    else:
        sig=f"⚪ SCALP WAIT - RSI {rsi_val:.1f}"; strong=False; sl=price-atr; tp1=price+atr; tp2=price+atr*2
        entry1 = price; entry2 = ema9; entry3 = ema21

    rr = abs(tp1-price)/abs(price-sl) if price!=sl else 0
    # 3 ENTRY POINTS ADDED
    msg = (
        f"⚡ *{display_ticker} - SCALP 5M* ⚡\n\n"
        f"💰 ${price:.2f} ({change:+.2f}%) RSI {rsi_val:.1f}\n"
        f"EMA9 ${ema9:.2f} EMA21 ${ema21:.2f} EMA50 ${ema50:.2f}\nATR ${atr:.2f}\n\n"
        f"🚀 {sig}\n\n"
        f"📍 ENTRY 1: ${entry1:.2f} MARKET\n"
        f"📍 ENTRY 2: ${entry2:.2f} LIMIT (EMA9) ⭐ MAIN\n"
        f"📍 ENTRY 3: ${entry3:.2f} LIMIT (EMA21)\n\n"
        f"🛑 SL: ${sl:.2f}\n"
        f"🎯 TP1: ${tp1:.2f} 1:{rr:.1f}\n"
        f"🎯 TP2: ${tp2:.2f}\n\n"
        f"⏱️ Hold 5-60 min"
    )
    return msg, strong

# ========== ADD THIS HANDLER FOR PRIVATE -> PUBLIC FORWARDING ==========
async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This fires when message is posted in private channel
    if not PRIVATE_CHANNEL_ID or not PUBLIC_CHANNEL_ID:
        return
    chat_id = str(update.channel_post.chat_id)
    if chat_id == str(PRIVATE_CHANNEL_ID):
        try:
            # Copy to public channel
            await context.bot.copy_message(
                chat_id=PUBLIC_CHANNEL_ID,
                from_chat_id=PRIVATE_CHANNEL_ID,
                message_id=update.channel_post.message_id
            )
            print(f"Forwarded {update.channel_post.message_id} private -> public")
        except Exception as e:
            print(f"Forward fail: {e} - Check bot is admin in BOTH channels with Post permission")

# Then in main() add:
# from telegram.ext import MessageHandler, filters
# app.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, channel_post_handler))
