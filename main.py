import os
import logging
import random
from datetime import datetime
from dotenv import load_dotenv
from typing import List
import telebot
from telebot import types
import time
import requests
import sqlite3
from db import init_db, get_user_character, list_characters, set_user_character, get_character_by_id
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
        types.BotCommand(command="start", description="Приветствие и помощь"),
        types.BotCommand(command="note_add", description="Добавить заметку"),
        types.BotCommand(command="note_list", description="Список заметок"),
        types.BotCommand(command="note_find", description="Поиск заметок"),
        types.BotCommand(command="note_edit", description="Изменить заметку"),
        types.BotCommand(command="note_del", description="Удалить заметку"),
        types.BotCommand(command="note_count", description="Сколько заметок"),
        types.BotCommand(command="note_export", description="Экспорт заметок в .txt"),
        types.BotCommand(command="note_stats", description="Статистика по датам"),
        types.BotCommand(command="model", description="Установить активную модель"),
        types.BotCommand(command="models", description="Получить список моделей"),
        types.BotCommand(command="ask", description="Задать вопрос модели"),
        types.BotCommand(command="ask_random", description="Задать вопрос случайной модели"),
        types.BotCommand(command="character", description="Установить активного персонажа"),
        types.BotCommand(command="characters", description="Получить список персонажей"),
        types.BotCommand(command="whoami", description="Получить активную модель и активного персонажа"),
    ]
    bot.set_my_commands(cmds)


def update_character_name(character_id: int, new_name: str) -> bool:
    """Обновляет имя персонажа в базе данных"""
    try:
        conn = sqlite3.connect('characters.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE characters SET name = ? WHERE id = ?', (new_name, character_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Ошибка при обновлении имени персонажа: {e}")
        return False


def _build_messages_for_character(character: dict, user_text: str) -> List[dict]:
    """Строит список сообщений для запроса к модели для конкретного персонажа"""
    system = (
        f"Ты отвечаешь строго в образе персонажа: {character['name']}.\n"
        f"{character['prompt']}\n"
        "Правила:\n"
        "1) Всегда держи стиль и манеру речи выбранного персонажа. При необходимости – переформулируй.\n"
        "2) Технические ответы давай корректно и по пунктам, но в характерной манере.\n"
        "3) Не раскрывай, что ты 'играешь роль'.\n"
        "4) Не используй длинные дословные цитаты из фильмов/книг (>10 слов).\n"
        "5) Если стиль персонажа выражен слабо – переформулируй ответ и усили характер персонажа, сохраняя фактическую точность.\n"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_text},
    ]


def _build_messages(user_id: int, user_text: str) -> List[dict]:
    """Строит список сообщений для запроса к модели"""
    p = get_user_character(user_id)
    return _build_messages_for_character(p, user_text)


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


def get_model_by_id(model_id: int):
    """Получает модель по ID"""
    for model in MODELS_DATA:
        if model['id'] == model_id:
            return model
    return None


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


@bot.message_handler(commands=['start', 'help'])
def cmd_start(message: types.Message) -> None:
    """Приветствует пользователя и кратко описать команды."""
    log_message(message, "/start" if message.text.startswith("/start") else "/help")

    text = (
        "Привет! Это заметочник на SQLite.\n\n"
        "Команды:\n"
  " /start - Приветствие и помощь\n"
        " /note_add - Добавить заметку\n"
        " /note_list - Список заметок\n"
        " /note_find - Поиск заметок\n"
        " /note_edit - Изменить заметку\n"
        " /note_del - Удалить заметку\n"
        " /note_count - Сколько заметок\n"
        " /note_export - Экспорт заметок в .txt\n"
        " /note_stats - Статистика по датам\n"
        " /model - Установить активную модель\n"
        " /models - Получить список моделей\n"
        " /ask - Задать вопрос модели\n"
        " /ask_random - Задать вопрос случайной модели\n"
        " /character - Установить активного персонажа\n"
        " /characters - Получить список персонажей\n"
        " /character - поменять имя персонажа\n"
        " /whoami - Получить активную модель и активного персонажа\n"
    )

    bot.reply_to(message, text)


@bot.message_handler(commands=["character_name"])
def cmd_character_name(message: types.Message) -> None:
    """Изменить имя персонажа по ID"""
    log_message(message, "/character_name")

    # Извлекаем аргументы команды
    args = message.text.replace('/character_name', '', 1).strip()

    if not args:
        bot.reply_to(message, "Использование: /character_name <ID> >новое_имя>\n\nПример: /character_name 1 >Новое имя")
        return

    # Разделяем ID и новое имя по символу >
    parts = args.split('>', 1)
    if len(parts) < 2:
        bot.reply_to(message,
                     "Использование: /character_name <ID> >новое_имя>\n\nНе забудьте символ '>' перед новым именем")
        return

    id_part = parts[0].strip()
    new_name = parts[1].strip()

    if not id_part.isdigit():
        bot.reply_to(message, "ID должен быть числом. Использование: /character_name <ID> >новое_имя>")
        return

    if not new_name:
        bot.reply_to(message, "Новое имя не может быть пустым. Использование: /character_name <ID> >новое_имя>")
        return

    character_id = int(id_part)

    # Проверяем, существует ли персонаж с таким ID
    try:
        character = get_character_by_id(character_id)
        if not character:
            bot.reply_to(message, f"Персонаж с ID {character_id} не найден.")
            return

        old_name = character['name']

        # Обновляем имя персонажа
        success = update_character_name(character_id, new_name)
        if success:
            bot.reply_to(message, f"Имя персонажа изменено:\nID: {character_id}\nБыло: {old_name}\nСтало: {new_name}")
            logging.info(
                f"Пользователь {message.from_user.id} изменил имя персонажа {character_id} с '{old_name}' на '{new_name}'")
        else:
            bot.reply_to(message, "Ошибка при изменении имени персонажа в базе данных.")

    except Exception as e:
        logging.error(f"Ошибка в команде /character_name: {e}")
        bot.reply_to(message, "Произошла ошибка при изменении имени персонажа.")


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


@bot.message_handler(commands=["ask_model"])
def cmd_ask_model(message: types.Message) -> None:
    """Задать вопрос конкретной модели по ID без смены активной модели"""
    log_message(message, "/ask_model")

    if openrouter_client is None:
        bot.reply_to(message, "❌ OpenRouter недоступен. Проверьте настройки API ключа.")
        return

    # Извлекаем аргументы команды
    args = message.text.replace('/ask_model', '', 1).strip().split(' ', 1)

    if len(args) < 2 or not args[0].isdigit():
        bot.reply_to(message, "Использование: /ask_model <ID> <вопрос>\n\nПример: /ask_model 7 Погода в Москве")
        return

    model_id = int(args[0])
    q = args[1].strip()

    if not q:
        bot.reply_to(message, "Использование: /ask_model <ID> <вопрос>\n\nВопрос не может быть пустым.")
        return

    # Находим модель по ID
    target_model = get_model_by_id(model_id)
    if not target_model:
        bot.reply_to(message, f"❌ Модель с ID={model_id} не найдена. Используйте /models для списка моделей.")
        return

    # Строим сообщение с текущим персонажем пользователя
    msg = _build_messages(message.from_user.id, q[:600])
    model_key = target_model['key']

    try:
        text, ms = chat_once(msg, model=model_key, temperature=0.2, max_tokens=400)
        out = (text or '').strip()[:4000]

        # Получаем текущую активную модель для информации
        active_model = get_active_model()
        active_info = f" (активная: {active_model['label']})" if active_model else ""

        bot.reply_to(message, f"{out}\n\n({ms} мс; модель: {target_model['label']}{active_info})")
    except OpenRouterError as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")
    except Exception as e:
        logging.error(f"Непредвиденная ошибка в /ask_model: {e}")
        bot.reply_to(message, "❌ Непредвиденная ошибка.")


@bot.message_handler(commands=["ask_random"])
def cmd_ask_random(message: types.Message) -> None:
    """Задать вопрос случайной LLP модели"""
    log_message(message, "/ask_random")

    if openrouter_client is None:
        bot.reply_to(message, "❌ OpenRouter недоступен. Проверьте настройки API ключа.")
        return

    q = message.text.replace('/ask_random', '', 1).strip()
    if not q:
        bot.reply_to(message, "Использование: /ask_random <вопрос>")
        return
    q = q[:600]

    # Если случайный персонаж из таблицы (не сохраняем в user_character)
    items = list_characters()
    if not items:
        bot.reply_to(message, "Каталог персонажей пуст.")
        return
    chosen = random.choice(items)
    character = get_character_by_id(chosen['id'])  # получаем prompt

    msgs = _build_messages_for_character(character, q)
    model_key = get_active_model()['key']

    try:
        text, ns = chat_once(msgs, model=model_key, temperature=0.2, max_tokens=400)
        out = (text or '').strip()[:4000]
        bot.reply_to(message, f"{out}\n\n({ns} мс; модель: {model_key}; персонаж: {character['name']})")
    except OpenRouterError as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")
    except Exception as e:
        logging.error(f"Непредвиденная ошибка в /ask_random: {e}")
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
    lines.append("❓ Задать вопрос: /ask_model <ID> <вопрос>")
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


@bot.message_handler(commands=["characters"])
def cmd_characters(message: types.Message) -> None:
    """
    Показать список персонажей
    """
    log_message(message, "/characters")
    user_id = message.from_user.id
    items = list_characters()
    if not items:
        bot.reply_to(message, "Каталог персонажей пуст.")
        return

    # Текущий персонаж пользователя
    try:
        current = get_user_character(user_id)["id"]
    except Exception:
        current = None

    lines = ["Доступные персонажи:"]
    for p in items:
        star = "*" if current is not None and p["id"] == current else " "
        lines.append(f"{star} {p['id']}. {p['name']}")
    lines.append("\nВыбор: /character <ID>")
    lines.append("Изменить имя: /character_name <ID> >новое_имя>")
    bot.reply_to(message, "\n".join(lines))


@bot.message_handler(commands=["character"])
def cmd_character(message: types.Message) -> None:
    """
    Установить активным персонаж
    """
    log_message(message, "/character")
    user_id = message.from_user.id
    arg = message.text.replace("/character", "", 1).strip()

    if not arg:
        p = get_user_character(user_id)
        bot.reply_to(message, f"Текущий персонаж: {p['name']} \n(смотрите: /characters, затем /character <ID>)")
        return

    if not arg.isdigit():
        bot.reply_to(message, "Использование: /character <ID из /characters>")
        return

    try:
        p = set_user_character(user_id, int(arg))
        bot.reply_to(message, f"Персонаж установлен: {p['name']}")
    except ValueError:
        bot.reply_to(message, "Неизвестный ID персонажа. Сначала /characters.")


@bot.message_handler(commands=["whoami"])
def cmd_whoami(message: types.Message) -> None:
    """
    Показать активную модель и активного персонажа
    """
    log_message(message, "/whoami")
    character = get_user_character(message.from_user.id)
    model = get_active_model()
    bot.reply_to(message, f"Модель: {model['label']} [{model['key']}]\nПерсонаж: {character['name']}")


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