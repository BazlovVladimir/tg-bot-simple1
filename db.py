# db.py
import sqlite3
from datetime import datetime


def init_db():
    """Инициализация базы данных - создание таблицы, если она не существует"""
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()

    # Создаем таблицу с правильной структурой
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()


# Остальные функции остаются без изменений
def add_note(user_id, text):
    """Добавление новой заметки"""
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO notes (user_id, text) VALUES (?, ?)', (user_id, text))
    note_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return note_id


def list_notes(user_id):
    """Получение всех заметок пользователя"""
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, text FROM notes WHERE user_id = ? ORDER BY id', (user_id,))
    notes = [{'id': row[0], 'text': row[1]} for row in cursor.fetchall()]
    conn.close()
    return notes


def update_note(user_id, note_id, new_text):
    """Обновление заметки"""
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE notes SET text = ? WHERE id = ? AND user_id = ?', (new_text, note_id, user_id))
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0


def delete_note(user_id, note_id):
    """Удаление заметки"""
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM notes WHERE id = ? AND user_id = ?', (note_id, user_id))
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0


def find_notes(user_id, query):
    """Поиск заметок по тексту"""
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, text FROM notes WHERE user_id = ? AND text LIKE ? ORDER BY id', (user_id, f'%{query}%'))
    notes = [{'id': row[0], 'text': row[1]} for row in cursor.fetchall()]
    conn.close()
    return notes


def count_notes(user_id):
    """Подсчет количества заметок пользователя"""
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM notes WHERE user_id = ?', (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count