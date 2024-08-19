import numpy as np
import yfinance as yf
from tradingview_ta import TA_Handler, Interval, Exchange, TradingView
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
import logging
import time
import threading

# Replace with your own Telegram Bot token and chat ID
TELEGRAM_BOT_TOKEN = '7107415911:AAGWjZlYEkfIHbUS6f9lqe6HEy5ijGcpIBw'
CHAT_ID = '1006163916'  # Replace with your chat ID

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
company_symbols = {}  # Dictionary to store company symbols and their corresponding exchanges
intervals = [Interval.INTERVAL_15_MINUTES, Interval.INTERVAL_30_MINUTES, Interval.INTERVAL_1_HOUR, Interval.INTERVAL_4_HOURS, Interval.INTERVAL_1_DAY]
bot_active = False
company_entry_allowed = False
finish_company_allowed = False
analyzing_thread = None

# Saudi and American markets only
markets = {
    "america": ["NASDAQ", "NYSE", "AMEX"],
    "middle_east": ["TADAWUL"]
}

# Function to send a message via the Telegram bot
def send_telegram_message(context: CallbackContext, chat_id: int, message: str):
    context.bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML')

# Function to determine the correct screener based on the exchange
def determine_screener(exchange: str) -> str:
    for screener, exchanges in markets.items():
        if exchange in exchanges:
            return screener
    return "middle_east"  # Default to Middle East if not found

# Function to fetch data from TradingView
def fetch_tradingview_data(symbol: str, interval: Interval, exchange: str):
    try:
        screener = determine_screener(exchange)
        handler = TA_Handler(
            symbol=symbol,
            screener=screener,
            exchange=exchange,
            interval=interval
        )
        analysis = handler.get_analysis()
        return analysis
    except Exception as e:
        logger.error(f"Can't access TradingView's API for {symbol}. Error: {e}")
        return None

# Function to fetch data from Yahoo Finance
def fetch_yahoo_data(symbol: str):
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d")
        return data
    except Exception as e:
        logger.error(f"Can't fetch Yahoo Finance data for {symbol}. Error: {e}")
        return None

# Function to analyze data and generate signals
def analyze_data(symbol: str, exchange: str):
    messages = []

    # Analyze using TradingView
    for interval in intervals:
        analysis = fetch_tradingview_data(symbol, interval, exchange)
        if analysis:
            close_price = analysis.indicators["close"]
            recommendation = analysis.summary["RECOMMENDATION"]
            entry_price = close_price  # Adjust this based on your strategies
            exit_price = entry_price * 1.05  # Example exit price strategy

            if recommendation != "NEUTRAL":
                messages.append(f"<b>{symbol} ({interval}) - TradingView</b>: {recommendation}\nسعر الدخول: {entry_price}\nسعر الخروج: {exit_price}")
        else:
            messages.append(f"لم يتم العثور على بيانات لـ {symbol} من TradingView للفاصل الزمني {interval}.")

    # Analyze using Yahoo Finance
    yahoo_data = fetch_yahoo_data(symbol)
    if yahoo_data is not None and not yahoo_data.empty:
        latest_close = yahoo_data['Close'].iloc[-1]
        messages.append(f"<b>{symbol} - Yahoo Finance</b>\nأحدث سعر إغلاق: {latest_close}")
    else:
        messages.append(f"لم يتم العثور على بيانات لـ {symbol} من Yahoo Finance.")

    return messages

# Start command handler
def start(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton("بدء الروبوت", callback_data='start_bot')],
        [InlineKeyboardButton("إيقاف الروبوت", callback_data='stop_bot')],
        [InlineKeyboardButton("إدخال الشركة", callback_data='enter_company')],
        [InlineKeyboardButton("إنهاء الشركة", callback_data='finish_company')],
        [InlineKeyboardButton("عرض تقرير الإشارة", callback_data='view_report')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_message = """
    مرحبًا بك في روبوت تحليل الأسهم! هنا الأوامر المتاحة:
    - بدء الروبوت: بدء التحليل
    - إيقاف الروبوت: إيقاف التحليل
    - إدخال الشركة: إضافة شركة للتحليل
    - إنهاء الشركة: إيقاف تحليل شركة معينة
    - عرض تقرير الإشارة: الحصول على أحدث تقرير للإشارات لجميع الشركات
    """
    context.bot.send_message(chat_id=chat_id, text=welcome_message, reply_markup=reply_markup, parse_mode='HTML')

    # Sending the top 20 companies to analyze
    top_saudi_companies = ["2222", "2010", "1120", "1080", "1211", "2280", "4190", "5110", "7030", "8311",
                           "4030", "4230", "8200", "1060", "1180", "4005", "1120", "6010", "3050", "2290"]
    message = "الشركات السعودية المختارة للتحليل:\n" + "\n".join(top_saudi_companies)
    send_telegram_message(context, chat_id, message)

# Callback handler for buttons
def button(update: Update, context: CallbackContext):
    global bot_active, company_entry_allowed, finish_company_allowed, analyzing_thread

    query = update.callback_query
    query.answer()
    chat_id = query.message.chat_id

    if query.data == 'start_bot':
        if not bot_active:
            bot_active = True
            company_entry_allowed = True
            send_telegram_message(context, chat_id, "تم بدء الروبوت. يمكنك الآن إدخال رموز الشركات للتحليل.")
            analyzing_thread = threading.Thread(target=start_analysis, args=(chat_id, context), daemon=True)
            analyzing_thread.start()

    elif query.data == 'stop_bot':
        if bot_active:
            bot_active = False
            company_entry_allowed = False
            finish_company_allowed = False
            send_telegram_message(context, chat_id, "تم إيقاف الروبوت. توقف التحليل.")

    elif query.data == 'enter_company':
        if bot_active:
            company_entry_allowed = True
            finish_company_allowed = False
            query.message.reply_text("يرجى إرسال رمز الشركة. مثال: 2222 أو AAPL.")
        else:
            query.message.reply_text("الروبوت غير نشط. يرجى بدء الروبوت أولاً.")

    elif query.data == 'finish_company':
        if bot_active:
            finish_company_allowed = True
            company_entry_allowed = False
            query.message.reply_text("يرجى إرسال اسم الشركة التي ترغب في إيقاف تحليلها.")
        else:
            query.message.reply_text("الروبوت غير نشط. يرجى بدء الروبوت أولاً.")

    elif query.data == 'view_report':
        if bot_active:
            view_report(chat_id, context)
        else:
            query.message.reply_text("الروبوت غير نشط. يرجى بدء الروبوت أولاً.")

# Handle text messages (used to add or stop analyzing a company)
def handle_message(update: Update, context: CallbackContext):
    global company_entry_allowed, finish_company_allowed

    if bot_active:
        if company_entry_allowed:
            symbol = update.message.text.upper()
            exchange = "TADAWUL" if symbol.isdigit() else "NASDAQ"
            company_symbols[symbol] = exchange
            update.message.reply_text(f"تمت إضافة {symbol} في {exchange} إلى قائمة التحليل.")
        elif finish_company_allowed:
            symbol = update.message.text.upper()
            if symbol in company_symbols:
                del company_symbols[symbol]
                update.message.reply_text(f"تم إيقاف تحليل {symbol}.")
            else:
                update.message.reply_text(f"الشركة {symbol} غير موجودة في قائمة التحليل.")
        else:
            update.message.reply_text("يرجى الضغط على الزر المناسب قبل إدخال رمز الشركة.")
    else:
        update.message.reply_text("الروبوت غير نشط. يرجى الضغط على زر 'بدء الروبوت' أولاً.")

# Start the analysis process
def start_analysis(chat_id: int, context: CallbackContext):
    while bot_active:
        if company_symbols:
            for symbol, exchange in company_symbols.items():
                signals = analyze_data(symbol, exchange)
                if signals:
                    for signal in signals:
                        send_telegram_message(context, chat_id, signal)
                else:
                    send_telegram_message(context, chat_id, f"لا توجد إشارات لـ {symbol}. يتم مواصلة التحليل.")
        else:
            send_telegram_message(context, chat_id, "لا توجد شركات مضافة للتحليل حاليًا.")
        
        # Sleep for 10 minutes before next analysis round
        time.sleep(600)

# View report of all companies being analyzed
def view_report(chat_id: int, context: CallbackContext):
    if company_symbols:
        for symbol, exchange in company_symbols.items():
            signals = analyze_data(symbol, exchange)
            if signals:
                for signal in signals:
                    send_telegram_message(context, chat_id, signal)
            else:
                send_telegram_message(context, chat_id, f"لا توجد إشارات لـ {symbol}.")
    else:
        send_telegram_message(context, chat_id, "لا توجد شركات مضافة للتحليل حاليًا.")

# Main function to start the bot
def main():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()

