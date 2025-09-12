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

@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(message, "Привет! Я твой первый бот! Напиши /help")

@bot.message_handler(commands=["help"])
def help_cmd(message):
    bot.reply_to(message, "/start — начать\n/help — помощь")

if __name__ == "__main__":
    print("Бот запускается...")
    bot.infinity_polling(skip_pending=True)