"""
Database Module for User Management
===================================
SQLite by default (DB_PATH). If DATABASE_URL is set, PostgreSQL is used instead,
so several frontend replicas can share one database.
"""

import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.environ.get('DB_PATH', 'database.db')
DATABASE_URL = os.environ.get('DATABASE_URL')
USE_PG = bool(DATABASE_URL)

if USE_PG:
    import psycopg2
    IntegrityError = psycopg2.IntegrityError
else:
    IntegrityError = sqlite3.IntegrityError


def _conn():
    return psycopg2.connect(DATABASE_URL) if USE_PG else sqlite3.connect(DB_PATH)


def _q(sql):
    return sql.replace('?', '%s') if USE_PG else sql


def init_db():
    """Initialize database tables"""
    pk = 'SERIAL PRIMARY KEY' if USE_PG else 'INTEGER PRIMARY KEY AUTOINCREMENT'
    conn = _conn()
    c = conn.cursor()
    if USE_PG:  # serialize concurrent replicas/workers starting at the same time
        c.execute('SELECT pg_advisory_xact_lock(727001)')
    c.execute(f'''
        CREATE TABLE IF NOT EXISTS users (
            id {pk},
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute(f'''
        CREATE TABLE IF NOT EXISTS predictions (
            id {pk},
            user_id INTEGER,
            rainfall REAL,
            temperature REAL,
            humidity REAL,
            ces REAL,
            climate_condition TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized successfully (%s)" % ('postgresql' if USE_PG else 'sqlite'))


def register_user(username, email, password):
    """Register a new user"""
    conn = None
    try:
        conn = _conn()
        c = conn.cursor()
        hashed_password = generate_password_hash(password)
        if USE_PG:
            c.execute('INSERT INTO users (username, email, password) VALUES (%s, %s, %s) RETURNING id',
                      (username, email, hashed_password))
            user_id = c.fetchone()[0]
        else:
            c.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                      (username, email, hashed_password))
            user_id = c.lastrowid
        conn.commit()
        conn.close()
        return {'success': True, 'user_id': user_id}
    except IntegrityError as e:
        if conn:
            conn.close()
        return {'success': False, 'error': str(e)}


def authenticate_user(username, password):
    """Authenticate user login"""
    conn = _conn()
    c = conn.cursor()
    c.execute(_q('SELECT id, username, email, password FROM users WHERE username = ?'), (username,))
    user = c.fetchone()
    conn.close()
    if user and check_password_hash(user[3], password):
        return {'success': True, 'user_id': user[0], 'username': user[1], 'email': user[2]}
    return {'success': False, 'error': 'Invalid credentials'}


def save_prediction(user_id, rainfall, temperature, humidity, ces, climate_condition):
    """Save prediction to database"""
    conn = _conn()
    c = conn.cursor()
    c.execute(_q('''
        INSERT INTO predictions (user_id, rainfall, temperature, humidity, ces, climate_condition)
        VALUES (?, ?, ?, ?, ?, ?)
    '''), (user_id, rainfall, temperature, humidity, ces, climate_condition))
    conn.commit()
    conn.close()


def get_user_predictions(user_id, limit=10):
    """Get user's prediction history"""
    conn = _conn()
    c = conn.cursor()
    c.execute(_q('''
        SELECT rainfall, temperature, humidity, ces, climate_condition, timestamp
        FROM predictions
        WHERE user_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    '''), (user_id, limit))
    rows = c.fetchall()
    conn.close()
    if USE_PG:  # keep timestamps as strings like SQLite so templates behave identically
        rows = [r[:5] + (str(r[5])[:19],) for r in rows]
    return rows


def get_user_by_id(user_id):
    """Get user by ID"""
    conn = _conn()
    c = conn.cursor()
    c.execute(_q('SELECT id, username, email FROM users WHERE id = ?'), (user_id,))
    user = c.fetchone()
    conn.close()
    return user


def get_all_users():
    """Get all users (for admin purposes)"""
    conn = _conn()
    c = conn.cursor()
    c.execute('SELECT id, username, email, created_at FROM users')
    users = c.fetchall()
    conn.close()
    return users


def delete_prediction(prediction_id, user_id):
    """Delete a prediction (user can only delete their own)"""
    conn = _conn()
    c = conn.cursor()
    c.execute(_q('DELETE FROM predictions WHERE id = ? AND user_id = ?'), (prediction_id, user_id))
    conn.commit()
    affected = c.rowcount
    conn.close()
    return affected > 0
