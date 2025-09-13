import os
import logging
from datetime import datetime
from dotenv import load_dotenv
import telebot
import time

# Загрузка переменных окружения
load_dotenv()

# Получение токена бота
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError("В .env файле нет TOKEN")


# Настройка логирования
def setup_logging():
    # Создаем папку для логов, если ее нет
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Формируем имя файла с текущей датой
    current_date = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"bot_{current_date}.log")

    # Настраиваем логирование
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()  # Также выводим в консоль
        ]
    )
    return logging.getLogger(__name__)


# Инициализация логгера
logger = setup_logging()

# Создание объекта бота
bot = telebot.TeleBot(TOKEN)

# Информация о боте
BOT_INFO = {
    "version": "1",
    "author": "Базлов Владимир Андреевич",
    "purpose": "Обучение созданию телеграм бота"
}


def log_message(message, command=None):
    """Логирует информацию о входящем сообщении"""
    user_info = f"ID: {message.from_user.id}, Имя: {message.from_user.first_name}"
    if message.from_user.last_name:
        user_info += f" {message.from_user.last_name}"
    if message.from_user.username:
        user_info += f" (@{message.from_user.username})"

    log_text = f"Пользователь: {user_info}, Команда: {command or 'текст'}, Сообщение: '{message.text}'"
    logger.info(log_text)


@bot.message_handler(commands=["start"])
def start(message):
    log_message(message, "/start")
    try:
        bot.reply_to(message, "Привет! Я твой первый бот! Напиши /help")
        logger.info("Команда /start успешно обработана")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /start: {e}")


@bot.message_handler(commands=["help"])
def help_cmd(message):
    log_message(message, "/help")
    try:
        help_text = """
Доступные команды:
/start - начать работу с ботом
/help - показать справку по командам
/about - информация о боте
/ping - проверить работоспособность бота
"""
        bot.reply_to(message, help_text)
        logger.info("Команда /help успешно обработана")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /help: {e}")


@bot.message_handler(commands=["about"])
def about(message):
    log_message(message, "/about")
    try:
        about_text = f"""
Информация о боте:

Версия: {BOT_INFO['version']}
Автор: {BOT_INFO['author']}
Назначение: {BOT_INFO['purpose']}
"""
        bot.reply_to(message, about_text)
        logger.info("Команда /about успешно обработана")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /about: {e}")


@bot.message_handler(commands=["ping"])
def ping(message):
    log_message(message, "/ping")
    try:
        start_time = time.time()
        sent_message = bot.reply_to(message, "Время ответа")
        end_time = time.time()

        response_time = round((end_time - start_time) * 1000, 2)
        bot.edit_message_text(
            chat_id=sent_message.chat.id,
            message_id=sent_message.message_id,
            text=f"Время ответа: {response_time} мс"
        )
        logger.info(f"Команда /ping успешно обработана. Время ответа: {response_time} мс")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /ping: {e}")


@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Обрабатывает все текстовые сообщения"""
    log_message(message)
    try:
        bot.reply_to(message, "Я понимаю только команды. Напиши /help для списка команд.")
        logger.info("Текстовое сообщение обработано")
    except Exception as e:
        logger.error(f"Ошибка при обработке текстового сообщения: {e}")


if __name__ == "__main__":
    logger.info("Бот запускается...")
    try:
        bot.infinity_polling(skip_pending=True)
        logger.info("Бот успешно запущен")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        logger.info("Бот завершил работу")