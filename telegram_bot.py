import os
import yfinance as yf
import ta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import logging

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN")

# Auto-fix gold symbols that have no 5m data
SYMBOL_MAP = {
    "XAUUSD=X": "GC=F",
    "XAUUSD": "GC=F",
    "GOLD": "GC=F",
    "XAUUSDX": "GC=F",
}

def clean_symbol(sym: str):
    s = sym.strip().upper().replace(" ", "").replace("/", "")
    # keep =F
    if s.endswith("=F"):
        base = s[:-2].replace("=", "")
        s = base + "=F"
    return SYMBOL_MAP.get(s, s)

def get_data(symbol, period="2d", interval="5m"):
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval, auto_adjust=True)
    if df.empty or len(df) < 60:
        return None
    return df

def calc_indicators(df):
    close = df['Close']
    df['EMA9'] = ta.trend.ema_indicator(close, window=9)
    df['EMA21'] = ta.trend.ema_indicator(close, window=21)
    df['EMA50'] = ta.trend.ema_indicator(close, window=50)
    df['RSI'] = ta.momentum.rsi(close, window=14)
    df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], close, window=14)
    return df

def format_scalp(symbol, df):
    last = df.iloc[-1]
    price = float(last['Close'])
    ema9 = float(last['EMA9'])
    ema21 = float(last['EMA21'])
    ema50 = float(last['EMA50'])
    rsi = float(last['RSI'])
    atr = float(last['ATR'])
    
    prev = float(df.iloc[-2]['Close'])
    pct = ((price - prev) / prev * 100) if prev else 0

    bear = price < ema9 and price < ema21
    bull = price > ema9 and price > ema21

    if bear:
        side = "SCALP SELL - EMA BEAR"
        entry1 = price
        entry2 = ema9
        entry3 = ema21
        # FIXED: SL ABOVE for SELL
        sl_base = max(ema50, ema21, entry3)
        sl = sl_base + atr * 1.2
        tp1 = price - atr * 1.2
        tp2 = price - atr * 2.2
    elif bull:
        side = "SCALP BUY - EMA BULL"
        entry1 = price
        entry2 = ema9
        entry3 = ema21
        # FIXED: SL BELOW for BUY
        sl_base = min(ema50, ema21, entry3)
        sl = sl_base - atr * 1.2
        tp1 = price + atr * 1.2
        tp2 = price + atr * 2.2
    else:
        side = "SCALP NEUTRAL - WAIT"
        entry1 = price
        entry2 = ema9
        entry3 = ema21
        sl = price + atr * 1.5 if bear else price - atr * 1.5
        tp1 = price - atr
        tp2 = price + atr

    # Risk Reward from ENTRY 1
    risk = abs(sl - entry1)
    reward1 = abs(tp1 - entry1)
    rr1 = reward1 / risk if risk > 0 else 0

    msg = (
        f"⚡️ XAUUSD - SCALP 5M ⚡️\n\n"
        f"💰 ${price:.2f} ({pct:+.2f}%) RSI {rsi:.1f}\n"
        f"EMA9 ${ema9:.2f} EMA21 ${ema21:.2f}\n"
        f"EMA50 ${ema50:.2f}\n"
        f"ATR ${atr:.2f}\n\n"
        f"🚀 🔴 {side}\n\n"
        f"📍 ENTRY 1: ${entry1:.2f} MARKET\n"
        f"📍 ENTRY 2: ${entry2:.2f} LIMIT (EMA9)\n"
        f"⭐ MAIN\n"
        f"📍 ENTRY 3: ${entry3:.2f} LIMIT (EMA21)\n\n"
        f"🛑 SL: ${sl:.2f}\n"
        f"🎯 TP1: ${tp1:.2f} 1:{rr1:.1f}\n"
        f"🎯 TP2: ${tp2:.2f}\n\n"
        f"⏱ Hold 5-60 min"
    )
    return msg

async def scalp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /scalp GC=F or /scalp NVDA or /scalp XAUUSD")
        return
    raw = " ".join(context.args)
    symbol = clean_symbol(raw)
    
    # Show what we analyze
    display_sym = "XAUUSD (GC=F)" if symbol == "GC=F" else symbol
    await update.message.reply_text(f"⚡️ Scalp Analyzing {display_sym} (5m)...")
    
    try:
        df = get_data(symbol)
        if df is None:
            await update.message.reply_text(f"❌ No 5m data for {symbol}. Try /scalp GC=F for gold or /scalp NVDA")
            return
        df = calc_indicators(df)
        msg = format_scalp(symbol, df)
        await update.message.reply_text(msg)
    except Exception as e:
        logging.exception(e)
        await update.message.reply_text(f"Error: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Tiker AI Live ✅\n\n"
        "Commands:\n"
        "/scalp GC=F - Gold scalp (use this)\n"
        "/scalp XAUUSD - auto fixed to GC=F\n"
        "/scalp NVDA - stocks\n"
        "/swing GC=F - swing (same as scalp for now)"
    )

# This kills Conflict error forever
async def post_init(app):
    await app.bot.delete_webhook(drop_pending_updates=True)
    print("Webhook deleted, polling starts - Conflict fixed")

def main():
    if not TOKEN:
        print("Missing BOT_TOKEN env var")
        return
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scalp", scalp))
    app.add_handler(CommandHandler("swing", scalp))
    print("Bot SCALP+SWING starting...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
