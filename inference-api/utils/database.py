import os
"""
Database Module for User Management
===================================
Handles SQLite database operations for user authentication and prediction history
"""

import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

DB_PATH = os.environ.get('DB_PATH', 'database.db')


def init_db():
    """Initialize database tables"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Predictions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    print("Database initialized successfully")


def register_user(username, email, password):
    """Register a new user"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        hashed_password = generate_password_hash(password)
        c.execute(
            'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
            (username, email, hashed_password)
        )
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        return {'success': True, 'user_id': user_id}
    except sqlite3.IntegrityError as e:
        return {'success': False, 'error': str(e)}


def authenticate_user(username, password):
    """Authenticate user login"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, username, email, password FROM users WHERE username = ?', (username,))
    user = c.fetchone()
    conn.close()
    
    if user and check_password_hash(user[3], password):
        return {'success': True, 'user_id': user[0], 'username': user[1], 'email': user[2]}
    return {'success': False, 'error': 'Invalid credentials'}


def save_prediction(user_id, rainfall, temperature, humidity, ces, climate_condition):
    """Save prediction to database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO predictions (user_id, rainfall, temperature, humidity, ces, climate_condition)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, rainfall, temperature, humidity, ces, climate_condition))
    conn.commit()
    conn.close()


def get_user_predictions(user_id, limit=10):
    """Get user's prediction history"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT rainfall, temperature, humidity, ces, climate_condition, timestamp 
        FROM predictions 
        WHERE user_id = ? 
        ORDER BY timestamp DESC 
        LIMIT ?
    ''', (user_id, limit))
    predictions = c.fetchall()
    conn.close()
    return predictions


def get_user_by_id(user_id):
    """Get user by ID"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, username, email FROM users WHERE id = ?', (user_id,))
    user = c.fetchone()
    conn.close()
    return user


def get_all_users():
    """Get all users (for admin purposes)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, username, email, created_at FROM users')
    users = c.fetchall()
    conn.close()
    return users


def delete_prediction(prediction_id, user_id):
    """Delete a prediction (user can only delete their own)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM predictions WHERE id = ? AND user_id = ?', (prediction_id, user_id))
    conn.commit()
    affected = c.rowcount
    conn.close()
    return affected > 0