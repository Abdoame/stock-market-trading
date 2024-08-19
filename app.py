import numpy as np
import yfinance as yf
from tradingview_ta import TA_Handler, Interval, Exchange
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
import logging
import time
import threading

# Replace with your own Telegram Bot token
TELEGRAM_BOT_TOKEN = '7107415911:AAGWjZlYEkfIHbUS6f9lqe6HEy5ijGcpIBw'
CHAT_ID = '1006163916'  # Replace with your chat ID

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
company_symbols = []  # List of companies to analyze
intervals = [Interval.INTERVAL_15_MINUTES, Interval.INTERVAL_30_MINUTES, Interval.INTERVAL_1_HOUR, Interval.INTERVAL_4_HOURS, Interval.INTERVAL_1_DAY]
bot_active = False
company_entry_allowed = False
analyzing_thread = None

# Function to send a message via the Telegram bot
def send_telegram_message(context: CallbackContext, chat_id: int, message: str):
    context.bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML')

# Function to fetch data from TradingView
def fetch_tradingview_data(symbol: str, interval: Interval):
    handler = TA_Handler(
        symbol=symbol,
        screener="america",
        exchange="NASDAQ",  # Adjust for different exchanges as needed
        interval=interval
    )
    analysis = handler.get_analysis()
    return analysis

# Function to fetch data from Yahoo Finance
def fetch_yahoo_data(symbol: str):
    ticker = yf.Ticker(symbol)
    data = ticker.history(period="1d")
    return data

# Function to analyze data and generate signals
def analyze_data(symbol: str):
    messages = []
    for interval in intervals:
        try:
            analysis = fetch_tradingview_data(symbol, interval)
            close_price = analysis.indicators["close"]
            recommendation = analysis.summary["RECOMMENDATION"]
            entry_price = close_price  # Adjust this based on your strategies
            exit_price = entry_price * 1.05  # Example exit price strategy

            if recommendation != "NEUTRAL":
                messages.append(f"<b>{symbol} ({interval})</b>: {recommendation}\nسعر الدخول: {entry_price}\nسعر الخروج: {exit_price}")

        except Exception as e:
            logger.error(f"Error analyzing {symbol} for interval {interval}: {e}")
            messages.append(f"خطأ في تحليل {symbol} للفاصل {interval}: {e}")

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

# Callback handler for buttons
def button(update: Update, context: CallbackContext):
    global bot_active, company_entry_allowed, analyzing_thread

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
            send_telegram_message(context, chat_id, "تم إيقاف الروبوت. توقف التحليل.")

    elif query.data == 'enter_company':
        if bot_active:
            company_entry_allowed = True
            query.message.reply_text("يرجى إرسال رمز الشركة للتحليل.")
        else:
            query.message.reply_text("الروبوت غير نشط. يرجى بدء الروبوت أولاً.")

    elif query.data == 'finish_company':
        if bot_active:
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
    global company_entry_allowed

    if bot_active:
        if company_entry_allowed:
            company_symbols.append(update.message.text.upper())
            update.message.reply_text(f"تمت إضافة {update.message.text.upper()} إلى قائمة التحليل.")
        else:
            update.message.reply_text("يرجى الضغط على زر 'إدخال الشركة' قبل إدخال رمز الشركة.")
    else:
        update.message.reply_text("الروبوت غير نشط. يرجى الضغط على زر 'بدء الروبوت' أولاً.")

# Start the analysis process
def start_analysis(chat_id: int, context: CallbackContext):
    while bot_active:
        if company_symbols:
            for symbol in company_symbols:
                signals = analyze_data(symbol)
                if signals:
                    for signal in signals:
                        send_telegram_message(context, chat_id, signal)
                else:
                    send_telegram_message(context, chat_id, f"لا توجد إشارات لـ {symbol}. يتم مواصلة التحليل.")
        else:
            send_telegram_message(context, chat_id, "لم يتم إدخال أي شركات للتحليل.")
        time.sleep(3600)  # Wait for an hour before the next check

# View signal report
def view_report(chat_id: int, context: CallbackContext):
    if not company_symbols:
        send_telegram_message(context, chat_id, "لم يتم إدخال أي شركات. يرجى إدخال رمز الشركة أولاً.")
        return

    for symbol in company_symbols:
        signals = analyze_data(symbol)
        if signals:
            for signal in signals:
                send_telegram_message(context, chat_id, signal)
        else:
            send_telegram_message(context, chat_id, f"لا توجد إشارات لـ {symbol}. يتم مواصلة التحليل.")

def main():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CallbackQueryHandler(button))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
