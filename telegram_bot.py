import os
import logging
import yfinance as yf
import ta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN")

MAP = {"XAUUSD=X": "GC=F", "XAUUSD": "GC=F", "GOLD": "GC=F"}

def clean(s):
    s = s.strip().upper().replace(" ", "").replace("/", "")
    return MAP.get(s, s)

def get_data(sym):
    df = yf.Ticker(sym).history(period="2d", interval="5m", auto_adjust=True)
    if df.empty or len(df) < 60:
        return None
    return df

def calc(df):
    c = df['Close']
    df['EMA9'] = ta.trend.ema_indicator(c, 9)
    df['EMA21'] = ta.trend.ema_indicator(c, 21)
    df['EMA50'] = ta.trend.ema_indicator(c, 50)
    df['RSI'] = ta.momentum.rsi(c, 14)
    df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], c, 14)
    return df

async def scalp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /scalp GC=F")
        return
    raw = " ".join(context.args)
    sym = clean(raw)
    await update.message.reply_text(f"Analyzing {sym} 5m...")
    try:
        df = get_data(sym)
        if df is None:
            await update.message.reply_text(f"No 5m data for {sym}")
            return
        df = calc(df)
        last = df.iloc[-1]
        price = float(last['Close'])
        ema9 = float(last['EMA9'])
        ema21 = float(last['EMA21'])
        ema50 = float(last['EMA50'])
        rsi = float(last['RSI'])
        atr = float(last['ATR'])
        prev = float(df.iloc[-2]['Close'])
        pct = (price - prev) / prev * 100

        bear = price < ema9 and price < ema21
        if bear:
            side = "SCALP SELL - EMA BEAR"
            e1 = price
            e2 = ema9
            e3 = ema21
            sl = max(ema50, ema21, e3) + atr * 1.2
            tp1 = price - atr * 1.2
            tp2 = price - atr * 2.2
        else:
            side = "SCALP BUY - EMA BULL" if price > ema9 and price > ema21 else "NEUTRAL"
            e1 = price
            e2 = ema9
            e3 = ema21
            sl = min(ema50, ema21, e3) - atr * 1.2 if price > ema9 else price - atr
            tp1 = price + atr * 1.2 if price > ema9 else price + atr
            tp2 = price + atr * 2.2 if price > ema9 else price - atr

        risk = abs(sl - e1)
        rr = abs(tp1 - e1) / risk if risk > 0 else 0
        msg = f"XAUUSD - SCALP 5M\n\nPrice ${price:.2f} ({pct:+.2f}%) RSI {rsi:.1f}\nEMA9 ${ema9:.2f} EMA21 ${ema21:.2f} EMA50 ${ema50:.2f}\nATR ${atr:.2f}\n\n{side}\n\nENTRY 1: ${e1:.2f} MARKET\nENTRY 2: ${e2:.2f} LIMIT\nENTRY 3: ${e3:.2f} LIMIT MAIN\n\nSL: ${sl:.2f}\nTP1: ${tp1:.2f} 1:{rr:.1f}\nTP2: ${tp2:.2f}"
        await update.message.reply_text(msg)
    except Exception as e:
        logging.exception(e)
        await update.message.reply_text(f"Error: {e}")

async def start(update: Update, ctx):
    await update.message.reply_text("Live OK /scalp GC=F")

async def post_init(app):
    await app.bot.delete_webhook(drop_pending_updates=True)

def main():
    if not TOKEN:
        print("No BOT_TOKEN")
        return
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scalp", scalp))
    app.add_handler(CommandHandler("swing", scalp))
    print("Bot starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
