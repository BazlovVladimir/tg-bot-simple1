import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from typing import List
import telebot
from telebot import types
import time
import requests

load_dotenv()
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError("Токен не найден")

# Настройка логирования
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"logs/bot_{datetime.now().strftime('%Y-%m-%d')}.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

bot = telebot.TeleBot(TOKEN)
BOT_INFO = {"version": "1", "author": "Базлов Владимир Андреевич", "purpose": "Обучение"}


def fetch_weather_moscow_open_meteo() -> str:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 55.7558,
        "longitude": 37.6173,
        "current": "temperature_2m",
        "timezone": "Europe/Moscow"
    }
    try:
        r = requests.get(url, params=params, timeout=5)
        r.raise_for_status()
        t = r.json()["current"]["temperature_2m"]
        return f"Москва: сейчас {round(t)}°C"
    except Exception:
        return "Не удалось получить погоду."


def parse_ints_from_text(text: str) -> List[int]:
    """Выделяет из текста целые числа: нормализует запятые, игнорирует токены-команды."""
    text = text.replace(",", " ")
    tokens = [tok for tok in text.split() if not tok.startswith("/")]
    return [int(tok) for tok in tokens if is_int_token(tok)]


def is_int_token(t: str) -> bool:
    """Проверка токена на целое число (с поддержкой знака минус)."""
    if not t:
        return False
    t = t.strip()
    if t in {"-", ""}:
        return False
    return t.lstrip("-").isdigit()


def log_message(message, command=None):
    user = message.from_user
    user_info = f"ID: {user.id}, Имя: {user.first_name or ''} {user.last_name or ''}"
    if user.username: user_info += f" (@{user.username})"
    logging.info(f"Пользователь: {user_info}, Команда: {command or 'текст'}, Текст: '{message.text}'")


def make_main_kb():
    """Создает главную клавиатуру"""
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("about", "sum", "show")
    kb.row("О боте", "Сумма")
    kb.row("Погода")
    kb.row("/help", "hide")
    return kb


@bot.message_handler(commands=["start"])
def start(message):
    log_message(message, "/start")
    bot.reply_to(message, "Привет! Я твой первый бот! Напиши /help", reply_markup=make_main_kb())


@bot.message_handler(commands=["help"])
def help_cmd(message):
    log_message(message, "/help")
    bot.reply_to(message, """Доступные команды:
/start - начать работу
/help - справка
/about - информация о боте
/ping - проверка работоспособности
/sum - сложить числа
/max - найти максимальное число
/hide - скрыть клавиатуру
/confirm - подтверждение действия
/weather - погода в Москве""")


@bot.message_handler(commands=["sum"])
def cmd_sum(message):
    nums = parse_ints_from_text(message.text)
    logging.info("Sum cmd from id=%s text=%r -> %r", message.from_user.id if message.from_user else "?", message.text,
                 nums)
    if not nums:
        bot.reply_to(message, "Нужно написать числа. Пример: /sum 2 3 10 или /sum 2, 3, -5")
        return
    bot.reply_to(message, f"Сумма: {sum(nums)}")


@bot.message_handler(commands=["max"])
def cmd_max(message):
    log_message(message, "/max")
    bot.send_message(message.chat.id, "Введите числа через пробел или запятую для поиска максимума:")
    bot.register_next_step_handler(message, on_max_numbers)


def on_max_numbers(message):
    nums = parse_ints_from_text(message.text)
    logging.info("Max next step from id=%s text=%r -> %r", message.from_user.id if message.from_user else "?",
                 message.text, nums)
    if not nums:
        bot.reply_to(message, "Не вижу чисел. Пример: 2 3 10")
    else:
        bot.reply_to(message, f"Максимум: {max(nums)}")


@bot.message_handler(commands=["about"])
def about(message):
    log_message(message, "/about")
    bot.reply_to(message,
                 f"Версия: {BOT_INFO['version']}\nАвтор: {BOT_INFO['author']}\nНазначение: {BOT_INFO['purpose']}")


@bot.message_handler(commands=["ping"])
def ping(message):
    log_message(message, "/ping")
    start = time.time()
    msg = bot.reply_to(message, "Время ответа")
    bot.edit_message_text(f"Время ответа: {round((time.time() - start) * 1000, 2)} мс", msg.chat.id, msg.message_id)


@bot.message_handler(commands=['hide'])
def hide_kb(message):
    log_message(message, "/hide")
    rm = types.ReplyKeyboardRemove()
    bot.send_message(message.chat.id, "Спрятал клавиатуру.", reply_markup=rm)


@bot.message_handler(commands=['confirm'])
def confirm_cmd(message):
    log_message(message, "/confirm")
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("Да", callback_data="confirm:yes"),
        types.InlineKeyboardButton("Нет", callback_data="confirm:no"),
    )
    bot.send_message(message.chat.id, "Подтвердить действие?", reply_markup=kb)


@bot.message_handler(commands=['weather'])
def weather_cmd(message):
    log_message(message, "/weather")
    weather_info = fetch_weather_moscow_open_meteo()
    bot.reply_to(message, weather_info)


@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm:"))
def on_confirm(c):
    # Извлекаем выбор пользователя
    choice = c.data.split(":", 1)[1]  # "yes" или "no"

    # Показываем "тик" на нажатой кнопке
    bot.answer_callback_query(c.id, "Принято")

    # Убираем inline-кнопки
    bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=None)

    # Отправляем результат
    bot.send_message(c.message.chat.id, "Готово!" if choice == "yes" else "Отменено.")

    # Логируем действие
    logging.info(f"Пользователь {c.from_user.id} выбрал: {choice}")


@bot.message_handler(func=lambda m: m.text == "Сумма")
def kb_sum(message):
    log_message(message, "Кнопка Сумма")
    bot.send_message(message.chat.id, "Введите числа через пробел или запятую:")
    bot.register_next_step_handler(message, on_sum_numbers)


@bot.message_handler(func=lambda m: m.text == "Погода")
def kb_weather(message):
    log_message(message, "Кнопка Погода")
    weather_info = fetch_weather_moscow_open_meteo()
    bot.reply_to(message, weather_info)


def on_sum_numbers(message):
    nums = parse_ints_from_text(message.text)
    logging.info("KB-sum next step from id=%s text=%r -> %r", message.from_user.id if message.from_user else "?",
                 message.text, nums)
    if not nums:
        bot.reply_to(message, "Не вижу чисел. Пример: 2 3 10")
    else:
        bot.reply_to(message, f"Сумма: {sum(nums)}")


@bot.message_handler(func=lambda m: m.text == "О боте")
def about_button(message):
    log_message(message, "Кнопка О боте")
    about(message)


# Новые обработчики для добавленных кнопок
@bot.message_handler(func=lambda m: m.text == "about")
def about_button_en(message):
    log_message(message, "Кнопка about")
    about(message)


@bot.message_handler(func=lambda m: m.text == "sum")
def sum_button_en(message):
    log_message(message, "Кнопка sum")
    kb_sum(message)


@bot.message_handler(func=lambda m: m.text == "show")
def show_button(message):
    log_message(message, "Кнопка show")
    bot.send_message(message.chat.id, "Показываю клавиатуру:", reply_markup=make_main_kb())


@bot.message_handler(func=lambda m: m.text == "hide")
def hide_button(message):
    log_message(message, "Кнопка hide")
    hide_kb(message)


@bot.message_handler(func=lambda m: True)
def handle_all(message):
    log_message(message)
    bot.reply_to(message, "Я понимаю только команды. Напиши /help для списка команд.")


if __name__ == "__main__":
    logging.info("Бот запущен")
    bot.infinity_polling()