import os, threading
from flask import Flask
import yfinance as yf
import pandas as pd
import numpy as np
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Tiker AI FULL INSTITUTIONAL ANALYSIS LIVE ✅"
def run_web():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_web, daemon=True).start()

def full_analysis(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="6mo")
        info = stock.info
        if df.empty: return None, "Ticker not found", False
        
        price = df['Close'].iloc[-1]
        open_p = df['Open'].iloc[-1]
        high = df['High'].iloc[-1]
        low = df['Low'].iloc[-1]
        prev = df['Close'].iloc[-2]
        change = ((price - prev) / prev) * 100
        vol = df['Volume'].iloc[-1]
        avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
        vol_ratio = vol / avg_vol if avg_vol else 1

        # SMA / EMA
        df['SMA20'] = df['Close'].rolling(20).mean()
        df['SMA50'] = df['Close'].rolling(50).mean()
        df['SMA200'] = df['Close'].rolling(200).mean()
        df['EMA12'] = df['Close'].ewm(span=12).mean()
        df['EMA26'] = df['Close'].ewm(span=26).mean()
        sma20 = df['SMA20'].iloc[-1]
        sma50 = df['SMA50'].iloc[-1]
        sma200 = df['SMA200'].iloc[-1]

        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_val = rsi.iloc[-1]

        # MACD
        df['MACD'] = df['EMA12'] - df['EMA26']
        df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
        macd = df['MACD'].iloc[-1]
        macd_sig = df['MACD_Signal'].iloc[-1]
        macd_hist = macd - macd_sig

        # Bollinger
        df['BB_Mid'] = df['Close'].rolling(20).mean()
        df['BB_Std'] = df['Close'].rolling(20).std()
        df['BB_Upper'] = df['BB_Mid'] + (df['BB_Std'] * 2)
        df['BB_Lower'] = df['BB_Mid'] - (df['BB_Std'] * 2)
        bb_upper = df['BB_Upper'].iloc[-1]
        bb_lower = df['BB_Lower'].iloc[-1]
        bb_pos = (price - bb_lower) / (bb_upper - bb_lower) * 100 if bb_upper != bb_lower else 50

        # ATR & Support/Resistance
        high_low = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close = (df['Low'] - df['Close'].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        support = df['Low'].rolling(20).min().iloc[-1]
        resistance = df['High'].rolling(20).max().iloc[-1]

        # Fundamentals
        name = info.get('shortName', ticker.upper())
        market_cap = info.get('marketCap', 0)
        pe = info.get('trailingPE', 0)
        forward_pe = info.get('forwardPE', 0)
        week_52_high = info.get('fiftyTwoWeekHigh', df['High'].max())
        week_52_low = info.get('fiftyTwoWeekLow', df['Low'].min())
        avg_52 = (price / week_52_high * 100) if week_52_high else 0

        # === STRONG LOGIC ===
        is_strong = False
        if price > sma20 > sma50 and rsi_val < 68 and macd > macd_sig and change > 1.0 and vol_ratio > 1.1:
            signal = "🟢🟢 STRONG BUY - All Confluence"
            is_strong = True
            sl = price - (atr * 1.5)
            tp1 = price + (atr * 1.5)
            tp2 = price + (atr * 3.0)
            tp3 = resistance
        elif rsi_val < 30 and price < bb_lower * 1.02:
            signal = "🔵🔵 STRONG BUY - Oversold + BB Bounce"
            is_strong = True
            sl = price - (atr * 1.0)
            tp1 = sma20
            tp2 = sma50
            tp3 = bb_upper
        elif price < sma20 and sma20 < sma50 and macd < macd_sig and change < -1.0:
            signal = "🔴🔴 STRONG SELL - Bearish Confluence"
            is_strong = True
            sl = price + (atr * 1.5)
            tp1 = price - (atr * 1.5)
            tp2 = price - (atr * 3.0)
            tp3 = support
        elif rsi_val > 75 and price > bb_upper * 0.98:
            signal = "🟠🟠 STRONG SELL - Overbought + BB Top"
            is_strong = True
            sl = price + (atr * 1.0)
            tp1 = sma20
            tp2 = sma50
            tp3 = bb_lower
        else:
            signal = "⚪ NO STRONG SETUP - Wait"
            sl = price - (atr * 1.5)
            tp1 = price + (atr * 1.5)
            tp2 = price + (atr * 2.5)
            tp3 = resistance

        risk = abs(price - sl)
        rr1 = abs(tp1 - price) / risk if risk else 0
        rr2 = abs(tp2 - price) / risk if risk else 0

        # Build FULL Message
        msg = f"""
🚨 *{name} ({ticker.upper()}) - FULL ANALYSIS* 🚨

*💰 PRICE ACTION*
Price: ${price:.2f} ({change:+.2f}%)
Open: ${open_p:.2f} | High: ${high:.2f} | Low: ${low:.2f}
Day Range: {(high-low)/price*100:.1f}% | ATR: ${atr:.2f}

*📊 VOLUME ANALYSIS*
Vol: {vol:,.0f} | Avg20: {avg_vol:,.0f}
Vol Ratio: {vol_ratio:.2f}x {'🔥 High Vol' if vol_ratio>1.5 else '💤 Low Vol' if vol_ratio<0.8 else 'Normal'}
Buy/Sell Pressure: {'🟢 Accumulation' if price>open_p and vol_ratio>1 else '🔴 Distribution' if price<open_p and vol_ratio>1 else 'Neutral'}

*📈 TREND & MA*
SMA20: ${sma20:.2f} ({'Above' if price>sma20 else 'Below'})
SMA50: ${sma50:.2f} ({'Above' if price>sma50 else 'Below'})
SMA200: ${sma200:.2f} ({'Bullish LT' if price>sma200 else 'Bearish LT'})
Trend: {'🟢 Uptrend' if sma20>sma50 else '🔴 Downtrend'} | Golden/Death: {'Golden Cross' if sma20>sma50 and df['SMA20'].iloc[-2]<df['SMA50'].iloc[-2] else 'Death Cross' if sma20<sma50 and df['SMA20'].iloc[-2]>df['SMA50'].iloc[-2] else 'None'}

*📉 MOMENTUM*
RSI(14): {rsi_val:.1f} - {'Overbought >70' if rsi_val>70 else 'Oversold <30' if rsi_val<30 else 'Neutral 30-70'}
MACD: {macd:.3f} | Signal: {macd_sig:.3f} | Hist: {macd_hist:+.3f} ({'Bullish' if macd>macd_sig else 'Bearish'})
BB: Upper ${bb_upper:.2f} | Lower ${bb_lower:.2f} | Position: {bb_pos:.0f}% {'🔥 Near Top' if bb_pos>80 else '💧 Near Bottom' if bb_pos<20 else ''}

*🎯 KEY LEVELS*
Support: ${support:.2f} ({(support-price)/price*100:+.1f}%)
Resistance: ${resistance:.2f} ({(resistance-price)/price*100:+.1f}%)
52W High: ${week_52_high:.2f} | 52W Low: ${week_52_low:.2f}
From 52W High: {100-avg_52:+.1f}%

*🏢 FUNDAMENTALS*
Mkt Cap: ${market_cap/1e9:.1f}B | PE: {pe:.1f} | Fwd PE: {forward_pe:.1f}

*🚀 SIGNAL + RISK MANAGEMENT*
{signal}
{'✅ STRONG' if is_strong else '❌ WEAK - Filtered'}

🛑 STOP LOSS: ${sl:.2f} ({(sl-price)/price*100:+.1f}%)
🎯 TP1 (Scalp): ${tp1:.2f} (+{(tp1-price)/price*100:.1f}%) | R:R 1:{rr1:.1f}
🎯 TP2 (Swing): ${tp2:.2f} (+{(tp2-price)/price*100:.1f}%) | R:R 1:{rr2:.1f}
🎯 TP3 (Resistance): ${tp3:.2f}

💡 Position Size: Risk max 1-2% of account
"""
        return msg, None, is_strong
    except Exception as e:
        return None, str(e), False

async def strong_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /strong AAPL")
        return
    ticker = context.args[0].upper()
    await update.message.reply_text(f"⏳ FULL INSTITUTIONAL ANALYSIS for {ticker}... (20 indicators)")
    msg, err, is_strong = full_analysis(ticker)
    if err:
        await update.message.reply_text(f"❌ {err}")
        return
    # Telegram limit 4096 chars - split if needed
    if len(msg) > 4000:
        for i in range(0, len(msg), 4000):
            await update.message.reply_text(msg[i:i+4000], parse_mode='Markdown')
    else:
        await update.message.reply_text(msg, parse_mode='Markdown')

async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    watchlist = ["AAPL", "TSLA", "NVDA", "MSFT", "BTC-USD", "ETH-USD", "SOL-USD", "GOOGL"]
    await update.message.reply_text(f"🔎 FULL SCAN {len(watchlist)} tickers for STRONG setups...")
    for t in watchlist:
        msg, err, is_strong = full_analysis(t)
        if is_strong and msg:
            await update.message.reply_text(msg, parse_mode='Markdown')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 *FULL ANALYSIS MODE LIVE!*\n/strong AAPL - 20+ data points\n/scan - scan all", parse_mode='Markdown')

if TOKEN:
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("strong", strong_cmd))
    app.add_handler(CommandHandler("scan", scan_cmd))
    app.add_handler(CommandHandler

