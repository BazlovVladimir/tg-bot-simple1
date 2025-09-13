import os
from dotenv import load_dotenv
import telebot

# Загрузка переменных окружения
load_dotenv()

# Получение токена бота
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError("В .env файле нет TOKEN")

# Создание объекта бота
bot = telebot.TeleBot(TOKEN)

# Информация о боте
BOT_INFO = {
    "version": "1",
    "author": "Базлов Владимир Андреевич",
    "purpose": "Обучение созданию телеграм бота"
}

@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(message, "Привет! Я твой первый бот! Напиши /help")

@bot.message_handler(commands=["help"])
def help_cmd(message):
    help_text = """
Доступные команды:
/start - начать работу с ботом
/help - показать справку по командам
/about - информация о боте
"""
    bot.reply_to(message, help_text)

@bot.message_handler(commands=["about"])
def about(message):
    about_text = f"""
 Информация о боте:

Версия: {BOT_INFO['version']}
Автор: {BOT_INFO['author']}
Назначение: {BOT_INFO['purpose']}
"""
    bot.reply_to(message, about_text)

if __name__ == "__main__":
    print("Бот запускается...")
    bot.infinity_polling(skip_pending=True)