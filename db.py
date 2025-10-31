# db.py
import sqlite3
from datetime import datetime
from contextlib import contextmanager


@contextmanager
def _connect():
    """Контекстный менеджер для работы с базой данных"""
    conn = sqlite3.connect('notes.db')
    conn.row_factory = sqlite3.Row  # Позволяет обращаться к колонкам по имени
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Инициализация базы данных - создание таблицы, если она не существует"""
    with _connect() as conn:
        cursor = conn.cursor()

        # Создаем таблицу с правильной структурой
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS models (
                id INTEGER PRIMARY KEY,
                key TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 0 CHECK (active IN (0,1))
            )
        ''')

        # Добавляем уникальный индекс для ограничения только одной активной модели
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS ux_models_single_active 
            ON models(active) WHERE active=1;
        ''')

        # Создаем таблицу notes (если её еще нет)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Добавляем начальные данные моделей
        cursor.execute('''
            INSERT OR IGNORE INTO models(id, key, label, active) VALUES
            (1, 'deepseek/deepseek-chat-v3.1:free', 'DeepSeek V3.1 (free)', 1),
            (2, 'deepseek/deepseek-r1:free', 'DeepSeek R1 (free)', 0),
            (3, 'mistralai/mistral-small-24b-instruct-2501:free', 'Mistral Small 24b (free)', 0),
            (4, 'meta-llama/llama-3.1-8b-instruct:free', 'Llama 3.1 8B (free)', 0)
        ''')

        conn.commit()


def list_models() -> list[dict]:
    """Получение списка всех моделей"""
    with _connect() as conn:
        rows = conn.execute('SELECT id, key, label, active FROM models ORDER BY id').fetchall()
        return [{'id': r['id'], 'key': r['key'], 'label': r['label'], 'active': bool(r['active'])} for r in rows]


def get_active_model() -> dict:
    """Получение активной модели"""
    with _connect() as conn:
        row = conn.execute('SELECT id, key, label FROM models WHERE active=1').fetchone()
        if row:
            return {'id': row['id'], 'key': row['key'], 'label': row['label'], 'active': True}

        row = conn.execute('SELECT id, key, label FROM models ORDER BY id LIMIT 1').fetchone()
        if not row:
            raise RuntimeError('В реестре моделей нет записей')

        conn.execute('UPDATE models SET active=CASE WHEN id=? THEN 1 ELSE 0 END', (row['id'],))
        conn.commit()
        return {'id': row['id'], 'key': row['key'], 'label': row['label'], 'active': True}


def set_active_model(model_id: int) -> dict:
    """Установка признака активности модели"""
    with _connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        exists = conn.execute('SELECT 1 FROM models WHERE id=?', (model_id,)).fetchone()
        if not exists:
            conn.rollback()
            raise ValueError('Несуществующий ID модели')

        conn.execute('UPDATE models SET active=CASE WHEN id=? THEN 1 ELSE 0 END', (model_id,))
        conn.commit()
        return get_active_model()


def add_note(user_id, text):
    """Добавление новой заметки"""
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO notes (user_id, text) VALUES (?, ?)', (user_id, text))
        note_id = cursor.lastrowid
        conn.commit()
        return note_id


def list_notes(user_id):
    """Получение всех заметок пользователя"""
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, text FROM notes WHERE user_id = ? ORDER BY id', (user_id,))
        notes = [{'id': row[0], 'text': row[1]} for row in cursor.fetchall()]
        return notes


def update_note(user_id, note_id, new_text):
    """Обновление заметки"""
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE notes SET text = ? WHERE id = ? AND user_id = ?', (new_text, note_id, user_id))
        rows_affected = cursor.rowcount
        conn.commit()
        return rows_affected > 0


def delete_note(user_id, note_id):
    """Удаление заметки"""
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM notes WHERE id = ? AND user_id = ?', (note_id, user_id))
        rows_affected = cursor.rowcount
        conn.commit()
        return rows_affected > 0


def find_notes(user_id, query):
    """Поиск заметок по тексту"""
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, text FROM notes WHERE user_id = ? AND text LIKE ? ORDER BY id',
                       (user_id, f'%{query}%'))
        notes = [{'id': row[0], 'text': row[1]} for row in cursor.fetchall()]
        return notes


def count_notes(user_id):
    """Подсчет количества заметок пользователя"""
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM notes WHERE user_id = ?', (user_id,))
        count = cursor.fetchone()[0]
        return count


def add_model(key, label, active=False):
    """Добавление новой модели"""
    with _connect() as conn:
        cursor = conn.cursor()

        # Если модель должна быть активной, сначала сбрасываем все активные
        if active:
            cursor.execute('UPDATE models SET active = 0 WHERE active = 1')

        cursor.execute('INSERT INTO models (key, label, active) VALUES (?, ?, ?)',
                       (key, label, 1 if active else 0))
        model_id = cursor.lastrowid

        conn.commit()
        return model_id