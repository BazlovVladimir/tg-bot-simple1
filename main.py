import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from typing import List
import telebot
from telebot import types
import time
import requests
import sqlite3
from db import init_db
from openrouter_client import OpenRouterClient, OpenRouterError

load_dotenv()
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError("Токен не найден")

# Инициализация базы данных при запуске
init_db()

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

# Глобальная переменная для хранения активной модели
ACTIVE_MODEL = None
MODELS_DATA = [
    {"id": 1, "label": "GPT-3.5 Turbo", "key": "openai/gpt-3.5-turbo", "active": True},
    {"id": 2, "label": "GPT-4", "key": "openai/gpt-4", "active": False},
    {"id": 3, "label": "GPT-4 Turbo", "key": "openai/gpt-4-turbo", "active": False},
    {"id": 4, "label": "Claude-3 Opus", "key": "anthropic/claude-3-opus", "active": False},
    {"id": 5, "label": "Claude-3 Sonnet", "key": "anthropic/claude-3-sonnet", "active": False},
    {"id": 6, "label": "Claude-3 Haiku", "key": "anthropic/claude-3-haiku", "active": False},
    {"id": 7, "label": "Gemini Pro", "key": "google/gemini-pro", "active": False},
    {"id": 8, "label": "Llama 2 70B", "key": "meta-llama/llama-2-70b-chat", "active": False},
    {"id": 9, "label": "Mistral 7B", "key": "mistralai/mistral-7b-instruct", "active": False},
    {"id": 10, "label": "Mixtral 8x7B", "key": "mistralai/mixtral-8x7b-instruct", "active": False},
]

# Инициализация клиента OpenRouter
try:
    openrouter_client = OpenRouterClient()
    logging.info("OpenRouter клиент успешно инициализирован")
except RuntimeError as e:
    logging.error(f"Ошибка инициализации OpenRouter клиента: {e}")
    openrouter_client = None


def _setup_bot_commands() -> None:
    """Регистрирует команды в меню клиента Telegram (удобно для новичков)."""
    cmds = [
        types.BotCommand(command="start", description="🚀 Приветствие и справка"),
        types.BotCommand(command="note_add", description="📝 Добавить новую заметку"),
        types.BotCommand(command="note_list", description="📋 Показать мои заметки"),
        types.BotCommand(command="note_find", description="🔍 Найти заметки по тексту"),
        types.BotCommand(command="note_edit", description="✏️ Изменить существующую заметку"),
        types.BotCommand(command="note_del", description="🗑️ Удалить заметку"),
        types.BotCommand(command="note_count", description="📊 Количество заметок"),
        types.BotCommand(command="note_export", description="💾 Экспорт заметок в файл"),
        types.BotCommand(command="note_stats", description="📈 Статистика заметок"),
        types.BotCommand(command="model", description="🤖 Выбрать активную модель"),
        types.BotCommand(command="models", description="📚 Список доступных моделей"),
        types.BotCommand(command="ask", description="💬 Задать вопрос AI-модели"),
        types.BotCommand(command="sum", description="➕ Вычислить сумму чисел"),
        types.BotCommand(command="max", description="📈 Найти максимальное число"),
        types.BotCommand(command="weather", description="🌤️ Погода в Москве"),
        types.BotCommand(command="about", description="ℹ️ Информация о боте"),
        types.BotCommand(command="ping", description="⚡ Проверить скорость ответа"),
        types.BotCommand(command="hide", description="⌨️ Скрыть клавиатуру"),
    ]
    bot.set_my_commands(cmds)


def _build_messages(user_id: int, user_text: str) -> List[dict]:
    """Строит список сообщений для запроса к модели"""
    system = (
        f"Ты отвечаешь кратко и по-существу.\n"
        "Правила:\n"
        "1) Технические ответы давай корректно и по пунктам.\n"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_text},
    ]


def chat_once(messages: List[dict], model: str, temperature: float = 0.2, max_tokens: int = 400) -> tuple:
    """Отправляет запрос к модели и возвращает ответ"""
    if openrouter_client is None:
        raise OpenRouterError(500, "OpenRouter клиент не инициализирован. Проверьте OPENROUTER_API_KEY.")

    return openrouter_client.chat_once(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens
    )


def list_models():
    """Функция для получения списка моделей"""
    return MODELS_DATA


def get_active_model():
    """Получает активную модель"""
    global ACTIVE_MODEL
    if ACTIVE_MODEL is None:
        # Находим первую активную модель
        for model in MODELS_DATA:
            if model['active']:
                ACTIVE_MODEL = model
                break
    return ACTIVE_MODEL


def set_active_model(model_id: int):
    """Устанавливает активную модель по ID"""
    global ACTIVE_MODEL, MODELS_DATA

    # Сбрасываем активность у всех моделей
    for model in MODELS_DATA:
        model['active'] = False

    # Находим и активируем нужную модель
    for model in MODELS_DATA:
        if model['id'] == model_id:
            model['active'] = True
            ACTIVE_MODEL = model
            return model

    raise ValueError("Модель с таким ID не найдена")


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


def save_note(user_id: int, text: str):
    """Сохраняет заметку в базу данных"""
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO notes (user_id, text) VALUES (?, ?)', (user_id, text))
    conn.commit()
    conn.close()


def get_user_notes(user_id: int) -> List[tuple]:
    """Получает все заметки пользователя"""
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()
    cursor.execute('SELECT text, created_at FROM notes WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    notes = cursor.fetchall()
    conn.close()
    return notes


def make_main_kb():
    """Создает главную клавиатуру"""
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("about", "sum", "show")
    kb.row("О боте", "Сумма")
    kb.row("Погода", "Добавить заметку")
    kb.row("/help", "hide")
    return kb


@bot.message_handler(commands=["start", "help"])
def cmd_start(message: types.Message) -> None:
    """Приветствует пользователя и кратко описать команды."""
    log_message(message, "/start" if message.text.startswith("/start") else "/help")

    text = (
        "Привет! Это умный бот с функциями заметок и AI-ассистента.\n\n"
        "📝 **Команды для заметок:**\n"
        " /note_add <текст> - добавить новую заметку\n"
        " /note_list [N] - показать последние N заметок (или все)\n"
        " /note_find <подстрока> - найти заметки по тексту\n"
        " /note_edit <id> <текст> - изменить существующую заметку\n"
        " /note_del <id> - удалить заметку по ID\n"
        " /note_count - посчитать количество заметок\n"
        " /note_export - экспортировать все заметки в файл\n"
        " /note_stats [days] - статистика заметок за период\n\n"
        "🤖 **Команды для AI-моделей:**\n"
        " /models - показать список доступных моделей\n"
        " /model <id> - выбрать активную модель по ID\n"
        " /ask <вопрос> - задать вопрос выбранной модели\n\n"
        "🔧 **Другие команды:**\n"
        " /sum <числа> - вычислить сумму чисел\n"
        " /max <числа> - найти максимальное число\n"
        " /weather - узнать погоду в Москве\n"
        " /about - информация о боте\n"
        " /ping - проверить скорость ответа\n"
        " /hide - скрыть клавиатуру\n"
    )

    if message.text.startswith("/start"):
        bot.reply_to(message, text, reply_markup=make_main_kb(), parse_mode='Markdown')
    else:
        bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=["ask"])
def cmd_ask(message: types.Message) -> None:
    """Команда для опроса модели"""
    log_message(message, "/ask")

    if openrouter_client is None:
        bot.reply_to(message, "❌ OpenRouter недоступен. Проверьте настройки API ключа.")
        return

    q = message.text.replace('/ask', '', 1).strip()
    if not q:
        bot.reply_to(message, "Использование: /ask <вопрос>")
        return

    msg = _build_messages(message.from_user.id, q[:600])
    active_model = get_active_model()
    if not active_model:
        bot.reply_to(message, "❌ Нет активной модели. Сначала выберите модель через /models")
        return

    model_key = active_model['key']

    try:
        text, ms = chat_once(msg, model=model_key, temperature=0.2, max_tokens=400)
        out = (text or '').strip()[:4000]  # не переполняем сообщение Telegram
        bot.reply_to(message, f"{out}\n\n({ms} мс; модель: {model_key})")
    except OpenRouterError as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")
    except Exception as e:
        logging.error(f"Непредвиденная ошибка в /ask: {e}")
        bot.reply_to(message, "❌ Непредвиденная ошибка.")


@bot.message_handler(commands=["models"])
def cmd_models(message: types.Message) -> None:
    """Команда для получения списка моделей"""
    log_message(message, "/models")
    items = list_models()
    if not items:
        bot.reply_to(message, 'Список моделей пуст.')
        return
    lines = ['📋 Доступные модели:']
    for m in items:
        star = '✅' if m['active'] else '  '
        lines.append(f"{star} {m['id']}. {m['label']} ({m['key']})")
    lines.append("\n🔄 Активировать: /model <ID>")
    bot.reply_to(message, "\n".join(lines))


@bot.message_handler(commands=["model"])
def cmd_model(message: types.Message) -> None:
    """Команда для выбора активной модели"""
    log_message(message, "/model")
    arg = message.text.replace('/model', '', 1).strip()

    if not arg:
        # Если аргументов нет - показываем текущую активную модель
        active = get_active_model()
        if active:
            bot.reply_to(message,
                         f"✅ Текущая активная модель: {active['label']} ({active['key']})\n\nИспользование: /model <ID> или /models")
        else:
            bot.reply_to(message, "❌ Нет активной модели.\n\nИспользование: /model <ID> или /models")
        return

    if not arg.isdigit():
        bot.reply_to(message, "❌ Использование: /model <ID из /models>")
        return

    try:
        model_id = int(arg)
        active = set_active_model(model_id)
        bot.reply_to(message, f"✅ Активная модель переключена: {active['label']} ({active['key']})")
        logging.info(f"Пользователь {message.from_user.id} установил активную модель: {active['label']}")
    except ValueError:
        bot.reply_to(message, "❌ Неизвестный ID модели. Сначала /models.")


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


# Команды для работы с заметками
@bot.message_handler(commands=['note_add'])
def note_add_cmd(message):
    log_message(message, "/note_add")
    bot.send_message(message.chat.id, "Введите текст заметки:")
    bot.register_next_step_handler(message, save_note_handler)


def save_note_handler(message):
    user_id = message.from_user.id
    text = message.text
    save_note(user_id, text)
    bot.reply_to(message, "Заметка сохранена!")
    logging.info(f"Пользователь {user_id} добавил заметку: {text}")


@bot.message_handler(commands=['note_list'])
def note_list_cmd(message):
    log_message(message, "/note_list")
    user_id = message.from_user.id
    notes = get_user_notes(user_id)

    if not notes:
        bot.reply_to(message, "У вас пока нет заметок.")
        return

    response = "Ваши заметки:\n\n"
    for i, (text, created_at) in enumerate(notes, 1):
        response += f"{i}. {text}\n   📅 {created_at}\n\n"

    bot.reply_to(message, response)


# Заглушки для остальных команд заметок
@bot.message_handler(commands=['note_find'])
def note_find_cmd(message):
    log_message(message, "/note_find")
    bot.reply_to(message, "Функция поиска заметок будет реализована в будущем.")


@bot.message_handler(commands=['note_edit'])
def note_edit_cmd(message):
    log_message(message, "/note_edit")
    bot.reply_to(message, "Функция редактирования заметок будет реализована в будущем.")


@bot.message_handler(commands=['note_del'])
def note_del_cmd(message):
    log_message(message, "/note_del")
    bot.reply_to(message, "Функция удаления заметок будет реализована в будущем.")


@bot.message_handler(commands=['note_count'])
def note_count_cmd(message):
    log_message(message, "/note_count")
    user_id = message.from_user.id
    notes = get_user_notes(user_id)
    bot.reply_to(message, f"У вас {len(notes)} заметок.")


@bot.message_handler(commands=['note_export'])
def note_export_cmd(message):
    log_message(message, "/note_export")
    bot.reply_to(message, "Функция экспорта заметок будет реализована в будущем.")


@bot.message_handler(commands=['note_stats'])
def note_stats_cmd(message):
    log_message(message, "/note_stats")
    bot.reply_to(message, "Функция статистики заметок будет реализована в будущем.")


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


# Обработчики кнопок
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


@bot.message_handler(func=lambda m: m.text == "Добавить заметку")
def kb_add_note(message):
    log_message(message, "Кнопка Добавить заметку")
    note_add_cmd(message)


@bot.message_handler(func=lambda m: m.text == "show")
def show_button(message):
    log_message(message, "Кнопка show")
    note_list_cmd(message)


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


@bot.message_handler(func=lambda m: m.text == "about")
def about_button_en(message):
    log_message(message, "Кнопка about")
    about(message)


@bot.message_handler(func=lambda m: m.text == "sum")
def sum_button_en(message):
    log_message(message, "Кнопка sum")
    kb_sum(message)


@bot.message_handler(func=lambda m: m.text == "hide")
def hide_button(message):
    log_message(message, "Кнопка hide")
    hide_kb(message)


@bot.message_handler(func=lambda m: True)
def handle_all(message):
    log_message(message)
    bot.reply_to(message, "Я понимаю только команды. Напиши /help для списка команд.")


if __name__ == "__main__":
    # Настройка команд бота перед запуском
    _setup_bot_commands()

    logging.info("Бот запущен")
    logging.info(f"Доступно моделей: {len(MODELS_DATA)}")
    active_model = get_active_model()
    if active_model:
        logging.info(f"Активная модель: {active_model['label']} ({active_model['key']})")

    bot.infinity_polling()