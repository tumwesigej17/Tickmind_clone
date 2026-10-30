import os
import threading
from flask import Flask
import yfinance as yf
import pandas as pd
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# === CONFIG ===
TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Tiker AI FULL Trading Bot LIVE 24/7 ✅"
def run_web():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_web, daemon=True).start()

# === TRADING LOGIC ===
def get_analysis(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="3mo")
        if df.empty:
            return None, "Ticker not found"
        
        price = df['Close'].iloc[-1]
        prev = df['Close'].iloc[-2]
        change = ((price - prev) / prev) * 100
        
        # Indicators
        df['SMA20'] = df['Close'].rolling(20).mean()
        df['SMA50'] = df['Close'].rolling(50).mean()
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_val = rsi.iloc[-1]

        sma20 = df['SMA20'].iloc[-1]
        sma50 = df['SMA50'].iloc[-1]

        # Signal
        if price > sma20 > sma50 and rsi_val < 70:
            signal = "🟢 STRONG BUY - Uptrend"
        elif price > sma20 and rsi_val < 65:
            signal = "🟢 BUY - Momentum"
        elif price < sma20 and rsi_val > 35:
            signal = "🔴 SELL - Downtrend"
        elif rsi_val > 75:
            signal = "🟠 OVERBOUGHT - Wait"
        elif rsi_val < 30:
            signal = "🔵 OVERSOLD - Potential Buy"
        else:
            signal = "⚪ HOLD - Sideways"

        info = stock.info
        name = info.get('shortName', ticker)

        msg = f"""
📊 *{name} ({ticker.upper()})*

💰 Price: ${price:.2f}
📈 Change: {change:+.2f}%
📉 RSI (14): {rsi_val:.1f}

MA20: ${sma20:.2f}
MA50: ${sma50:.2f}

🎯 *SIGNAL:* {signal}

High: ${df['High'].iloc[-1]:.2f}
Low: ${df['Low'].iloc[-1]:.2f}
Vol: {df['Volume'].iloc[-1]:,}
"""
        return msg, None
    except Exception as e:
        return None, str(e)

# === BOT COMMANDS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 *Tiker AI - Full Trading Bot LIVE!* 🚀\n\n"
        "✅ Running 24/7 on Render\n"
        "✅ Tickmind Clone Restored\n\n"
        "*COMMANDS:*\n"
        "/stock AAPL - Stock analysis\n"
        "/crypto BTC-USD - Crypto analysis\n"
        "/analyze TSLA - Deep signal\n"
        "/price EURUSD=X - Quick price\n"
        "/help - All commands\n\n"
        "Try: `/stock AAPL`",
        parse_mode='Markdown'
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 *Tiker AI Commands*\n\n"
        "/stock SYMBOL - e.g. /stock AAPL, /stock NVDA\n"
        "/crypto SYMBOL - e.g. /crypto BTC-USD, /crypto ETH-USD\n"
        "/analyze SYMBOL - Full TA + Signal\n"
        "/price SYMBOL - Quick price check\n\n"
        "*Popular:*\n"
        "Stocks: AAPL, TSLA, NVDA, MSFT, GOOGL\n"
        "Crypto: BTC-USD, ETH-USD, SOL-USD\n"
        "Forex: EURUSD=X, GBPUSD=X\n"
        "Indexes: ^GSPC (S&P), ^IXIC (Nasdaq)",
        parse_mode='Markdown'
    )

async def stock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /stock AAPL\nExample: /stock TSLA")
        return
    ticker = context.args[0].upper()
    await update.message.reply_text(f"⏳ Analyzing {ticker}...")
    msg, err = get_analysis(ticker)
    if msg:
        await update.message.reply_text(msg, parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ Error for {ticker}: {err}")

async def crypto_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /crypto BTC-USD")
        return
    ticker = context.args[0].upper()
    # auto add -USD if needed
    if "-" not in ticker and ticker not in ["BTC", "ETH"]:
        ticker = ticker + "-USD"
    elif ticker in ["BTC", "ETH", "SOL"]:
        ticker = ticker + "-USD"
    await update.message.reply_text(f"⏳ Checking crypto {ticker}...")
    msg, err = get_analysis(ticker)
    if msg:
        await update.message.reply_text(msg, parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ Error: {err}")

async def analyze_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await stock_cmd(update, context)

async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await stock_cmd(update, context)

# === RUN BOT ===
if TOKEN:
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("stock", stock_cmd))
    app.add_handler(CommandHandler("crypto", crypto_cmd))
    app.add_handler(CommandHandler("analyze", analyze_cmd))
    app.add_handler(CommandHandler("price", price_cmd))
    print("Tickmind FULL Bot Starting...")
    app.run_polling()
else:
    print("ERROR: BOT_TOKEN missing!")
    run_web()
