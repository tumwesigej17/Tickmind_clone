import threading
from flask import Flask
import os
import logging
import pandas as pd
import yfinance as yf
import ta
# Render web service health check
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Gold and BTC Telegram Bot is running!", 200

@web_app.route("/health")
def health():
    return "OK", 200

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

# BOTH TELEGRAM CHANNELS
CHANNEL_IDS = [
    -1004318804875,
    -1003988456999
]

ASSETS = {
    "gold": {
        "symbol": "GC=F",
        "name": "GOLD",
        "decimals": 2
    },
    "btc": {
        "symbol": "BTC-USD",
        "name": "BITCOIN",
        "decimals": 2
    }
}

DATA = {
    "5m": ("5d", "5m"),
    "15m": ("60d", "15m"),
    "1h": ("730d", "1h"),
    "1d": ("5y", "1d")
}


def get_data(symbol, timeframe):
    period, interval = DATA[timeframe]

    df = yf.Ticker(symbol).history(
        period=period,
        interval=interval,
        auto_adjust=False
    )

    if df is None or df.empty or len(df) < 60:
        return None

    df = df.copy()
    df.index = pd.to_datetime(df.index)

    if df.index.tz is not None:
        df.index = df.index.tz_convert("UTC").tz_localize(None)

    return df.dropna()


def make_h4(df):
    if df is None or df.empty:
        return None

    h4 = df.resample(
        "4h",
        label="right",
        closed="right"
    ).agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum"
    }).dropna()

    if len(h4) > 1:
        h4 = h4.iloc[:-1]

    return h4 if len(h4) >= 60 else None


def add_indicators(df):
    df = df.copy()
    close = df["Close"]

    df["EMA9"] = ta.trend.ema_indicator(close, 9)
    df["EMA21"] = ta.trend.ema_indicator(close, 21)
    df["EMA50"] = ta.trend.ema_indicator(close, 50)

    df["RSI"] = ta.momentum.rsi(close, 14)

    df["ATR"] = ta.volatility.average_true_range(
        df["High"],
        df["Low"],
        close,
        14
    )

    macd = ta.trend.MACD(close)

    df["MACD"] = macd.macd()
    df["MACD_SIGNAL"] = macd.macd_signal()

    df["ADX"] = ta.trend.adx(
        df["High"],
        df["Low"],
        close,
        14
    )

    return df.dropna()


def get_bias(row):
    if (
        row["EMA9"] > row["EMA21"] > row["EMA50"]
        and row["Close"] > row["EMA21"]
    ):
        return "BUY"

    if (
        row["EMA9"] < row["EMA21"] < row["EMA50"]
        and row["Close"] < row["EMA21"]
    ):
        return "SELL"

    return "NEUTRAL"


def score_setup(df, direction):
    row = df.iloc[-1]
    previous = df.iloc[-2]

    if direction == "BUY":
        checks = [
            (row["EMA9"] > row["EMA21"] > row["EMA50"], "Bullish EMA alignment"),
            (row["Close"] > row["EMA21"], "Price above EMA21"),
            (50 <= row["RSI"] <= 70, "Bullish RSI"),
            (row["MACD"] > row["MACD_SIGNAL"], "Bullish MACD"),
            (row["ADX"] >= 18, "Adequate trend strength"),
            (row["Close"] > previous["Close"], "Latest candle higher")
        ]
    else:
        checks = [
            (row["EMA9"] < row["EMA21"] < row["EMA50"], "Bearish EMA alignment"),
            (row["Close"] < row["EMA21"], "Price below EMA21"),
            (30 <= row["RSI"] <= 50, "Bearish RSI"),
            (row["MACD"] < row["MACD_SIGNAL"], "Bearish MACD"),
            (row["ADX"] >= 18, "Adequate trend strength"),
            (row["Close"] < previous["Close"], "Latest candle lower")
        ]

    passed = [
        description
        for condition, description in checks
        if condition
    ]

    return len(passed), passed


def fmt(value, decimals):
    return f"{value:,.{decimals}f}"


def analyse(asset_key, mode):
    asset = ASSETS[asset_key]
    symbol = asset["symbol"]
    decimals = asset["decimals"]

    if mode == "scalp":
        entry_data = get_data(symbol, "5m")
        confirm_data = get_data(symbol, "15m")

        entry_label = "M5"
        confirm_label = "M15"
        stop_multiplier = 1.5

    else:
        hourly = get_data(symbol, "1h")

        entry_data = (
            make_h4(hourly)
            if hourly is not None
            else None
        )

        confirm_data = get_data(symbol, "1d")

        entry_label = "H4"
        confirm_label = "DAILY"
        stop_multiplier = 2.0

    if entry_data is None or confirm_data is None:
        return "Market data unavailable. Please try again later."

    entry_df = add_indicators(entry_data)
    confirm_df = add_indicators(confirm_data)

    if len(entry_df) < 3 or len(confirm_df) < 3:
        return "Not enough completed candles for analysis."

    row = entry_df.iloc[-1]

    price = float(row["Close"])
    atr = float(row["ATR"])

    if pd.isna(atr) or atr <= 0:
        return "ATR unavailable. No trade setup generated."

    entry_bias = get_bias(row)
    confirm_bias = get_bias(confirm_df.iloc[-1])

    if entry_bias == "NEUTRAL":
        direction = "NEUTRAL"
        score = 0
        reasons = []
    else:
        direction = entry_bias
        score, reasons = score_setup(entry_df, direction)

    confirmed = (
        direction in ("BUY", "SELL")
        and confirm_bias == direction
    )

    actionable = confirmed and score >= 4

    support = float(entry_df.tail(30)["Low"].min())
    resistance = float(entry_df.tail(30)["High"].max())

    if actionable:
        entry = price
        risk_distance = atr * stop_multiplier

        if direction == "BUY":
            sl = entry - risk_distance
            tp1 = entry + risk_distance
            tp2 = entry + risk_distance * 2
            tp3 = entry + risk_distance * 3

        else:
            sl = entry + risk_distance
            tp1 = entry - risk_distance
            tp2 = entry - risk_distance * 2
            tp3 = entry - risk_distance * 3

        verdict = direction + " SETUP"

        levels = (
            f"\nENTRY: {fmt(entry, decimals)}"
            f"\nSL: {fmt(sl, decimals)}"
            f"\nTP1: {fmt(tp1, decimals)} (1R)"
            f"\nTP2: {fmt(tp2, decimals)} (2R)"
            f"\nTP3: {fmt(tp3, decimals)} (3R)"
        )

    else:
        verdict = "WAIT - NO CONFIRMED SETUP"

        if direction == "NEUTRAL":
            reason = "Entry timeframe trend is unclear."

        elif not confirmed:
            reason = (
                f"{entry_label} and {confirm_label} "
                "trends disagree."
            )

        else:
            reason = f"Setup score is only {score}/6."

        levels = f"\nReason: {reason}"

    timestamp = entry_df.index[-1].strftime(
        "%Y-%m-%d %H:%M UTC"
    )

    reason_text = (
        "\n".join(f"- {item}" for item in reasons)
        if reasons
        else "- No qualifying confirmations"
    )

    return (
        f"{asset['name']} {mode.upper()} ANALYSIS\n"
        f"Entry: {entry_label} | Confirmation: {confirm_label}\n"
        f"Last candle: {timestamp}\n\n"
        f"Price: {fmt(price, decimals)}\n"
        f"RSI: {float(row['RSI']):.1f}\n"
        f"ADX: {float(row['ADX']):.1f}\n"
        f"EMA9: {fmt(float(row['EMA9']), decimals)}\n"
        f"EMA21: {fmt(float(row['EMA21']), decimals)}\n"
        f"EMA50: {fmt(float(row['EMA50']), decimals)}\n"
        f"ATR: {fmt(atr, decimals)}\n\n"
        f"Support: {fmt(support, decimals)}\n"
        f"Resistance: {fmt(resistance, decimals)}\n\n"
        f"Entry trend: {entry_bias}\n"
        f"Confirmation trend: {confirm_bias}\n"
        f"Setup quality: {score}/6\n"
        f"Confirmations:\n{reason_text}\n\n"
        f"{verdict}{levels}\n\n"
        "Setup score is not a win probability. "
        "Levels are estimates, not guaranteed fills. "
        "Check your broker's live price and spread."
    )


# PUBLISH ANALYSIS TO BOTH CHANNELS
async def publish_to_channels(bot, message):
    for channel_id in CHANNEL_IDS:
        try:
            await bot.send_message(
                chat_id=channel_id,
                text=message
            )

            logger.info(
                "Published analysis to channel %s",
                channel_id
            )

        except Exception:
            logger.exception(
                "Could not publish to channel %s",
                channel_id
            )


async def send_analysis(update, context, asset_key, mode):
    await update.message.reply_text(
        f"Analysing {ASSETS[asset_key]['name']} {mode}..."
    )

    try:
        message = analyse(asset_key, mode)

        # Reply to the person who requested the analysis.
        await update.message.reply_text(message)

        # Also publish the same result to both channels.
        await publish_to_channels(
            context.bot,
            message
        )

    except Exception:
        logger.exception("Analysis error")

        await update.message.reply_text(
            "Analysis error. Please try again later."
        )


async def start(update, context):
    await update.message.reply_text(
        "GOLD & BTC TRADING ANALYSIS BOT\n\n"
        "/gold - Gold scalping\n"
        "/btc - Bitcoin scalping\n"
        "/scalp gold - Gold M5/M15\n"
        "/scalp btc - BTC M5/M15\n"
        "/swing gold - Gold H4/Daily\n"
        "/swing btc - BTC H4/Daily\n\n"
        "Balanced mode: BUY, SELL or WAIT."
    )


async def gold(update, context):
    await send_analysis(
        update, context, "gold", "scalp"
    )


async def btc(update, context):
    await send_analysis(
        update, context, "btc", "scalp"
    )


async def scalp(update, context):
    if not context.args:
        await update.message.reply_text(
            "Use: /scalp gold or /scalp btc"
        )
        return

    asset = context.args[0].lower()

    if asset not in ASSETS:
        await update.message.reply_text(
            "Choose gold or btc."
        )
        return

    await send_analysis(
        update, context, asset, "scalp"
    )


async def swing(update, context):
    if not context.args:
        await update.message.reply_text(
            "Use: /swing gold or /swing btc"
        )
        return

    asset = context.args[0].lower()

    if asset not in ASSETS:
        await update.message.reply_text(
            "Choose gold or btc."
        )
        return

    await send_analysis(
        update, context, asset, "swing"
    )


async def post_init(app):
    await app.bot.delete_webhook(
        drop_pending_updates=True
    )


def main():
    if not TOKEN:
        logger.error(
            "BOT_TOKEN environment variable is missing."
        )
        return

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gold", gold))
    app.add_handler(CommandHandler("btc", btc))
    app.add_handler(CommandHandler("scalp", scalp))
    app.add_handler(CommandHandler("swing", swing))

    logger.info("Gold and BTC bot starting...")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
if __name__ == "__main__":
    logging.info("Gold and BTC bot starting...")

    web_thread = threading.Thread(
        target=run_web_server,
        daemon=True
    )
    web_thread.start()

    application.run_polling()
