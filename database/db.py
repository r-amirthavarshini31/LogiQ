"""
LogiQ Database Module
Handles SQLite database operations for anomaly storage, caching, and settings.
"""

import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logiq.db')


def get_connection():
    """Create and return a new SQLite connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Initialize the database schema. Creates tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS anomalies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            timestamp TEXT,
            level TEXT NOT NULL,
            category TEXT,
            message TEXT NOT NULL,
            raw_line TEXT,
            line_number INTEGER,
            explanation TEXT,
            suggested_fix TEXT,
            runbook TEXT,
            status TEXT DEFAULT 'open',
            cache_hit INTEGER DEFAULT 0,
            severity_score REAL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            total_lines INTEGER DEFAULT 0,
            anomaly_count INTEGER DEFAULT 0,
            critical_count INTEGER DEFAULT 0,
            resolved_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS explanation_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_hash TEXT UNIQUE NOT NULL,
            explanation TEXT NOT NULL,
            suggested_fix TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    ''')

    cursor.execute('DELETE FROM anomalies')
    cursor.execute('DELETE FROM sessions')

    conn.commit()
    conn.close()


def create_session(session_id, filename, total_lines):
    """Create a new analysis session record."""
    conn = get_connection()
    conn.execute(
        'INSERT INTO sessions (id, filename, total_lines) VALUES (?, ?, ?)',
        (session_id, filename, total_lines)
    )
    conn.commit()
    conn.close()


def update_session_stats(session_id, anomaly_count, critical_count):
    """Update session statistics after analysis."""
    conn = get_connection()
    conn.execute(
        'UPDATE sessions SET anomaly_count = ?, critical_count = ? WHERE id = ?',
        (anomaly_count, critical_count, session_id)
    )
    conn.commit()
    conn.close()


def insert_anomaly(anomaly):
    """
    Insert a single anomaly record into the database.

    Args:
        anomaly (dict): Anomaly data with keys: session_id, timestamp, level,
                        category, message, raw_line, line_number, severity_score
    Returns:
        int: The ID of the inserted record.
    """
    conn = get_connection()
    cursor = conn.execute(
        '''INSERT INTO anomalies 
           (session_id, timestamp, level, category, message, raw_line, line_number, severity_score)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (
            anomaly.get('session_id'),
            anomaly.get('timestamp'),
            anomaly.get('level'),
            anomaly.get('category'),
            anomaly.get('message'),
            anomaly.get('raw_line'),
            anomaly.get('line_number'),
            anomaly.get('severity_score', 0.0)
        )
    )
    anomaly_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return anomaly_id


def insert_anomalies_batch(anomalies):
    """Insert multiple anomaly records in a single transaction."""
    conn = get_connection()
    cursor = conn.cursor()
    ids = []
    for anomaly in anomalies:
        cursor.execute(
            '''INSERT INTO anomalies 
               (session_id, timestamp, level, category, message, raw_line, line_number, severity_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                anomaly.get('session_id'),
                anomaly.get('timestamp'),
                anomaly.get('level'),
                anomaly.get('category'),
                anomaly.get('message'),
                anomaly.get('raw_line'),
                anomaly.get('line_number'),
                anomaly.get('severity_score', 0.0)
            )
        )
        ids.append(cursor.lastrowid)
    conn.commit()
    conn.close()
    return ids


def get_anomalies_by_session(session_id):
    """Retrieve all anomalies for a given session."""
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM anomalies WHERE session_id = ? ORDER BY line_number ASC',
        (session_id,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_anomaly_by_id(anomaly_id):
    """Retrieve a single anomaly by its ID."""
    conn = get_connection()
    row = conn.execute('SELECT * FROM anomalies WHERE id = ?', (anomaly_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_anomalies(filters=None):
    """
    Retrieve all anomalies with optional filters.

    Args:
        filters (dict): Optional filters — date_from, date_to, level, category, status
    Returns:
        list[dict]: List of anomaly records.
    """
    conn = get_connection()
    query = 'SELECT * FROM anomalies WHERE 1=1'
    params = []

    if filters:
        if filters.get('date_from'):
            query += ' AND created_at >= ?'
            params.append(filters['date_from'])
        if filters.get('date_to'):
            query += ' AND created_at <= ?'
            params.append(filters['date_to'])
        if filters.get('level'):
            query += ' AND level = ?'
            params.append(filters['level'])
        if filters.get('category'):
            query += ' AND category = ?'
            params.append(filters['category'])
        if filters.get('status'):
            query += ' AND status = ?'
            params.append(filters['status'])

    query += ' ORDER BY created_at DESC'
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_anomaly_explanation(anomaly_id, explanation, suggested_fix, cache_hit=False):
    """Update an anomaly with its AI explanation and suggested fix."""
    conn = get_connection()
    conn.execute(
        'UPDATE anomalies SET explanation = ?, suggested_fix = ?, cache_hit = ? WHERE id = ?',
        (explanation, suggested_fix, 1 if cache_hit else 0, anomaly_id)
    )
    conn.commit()
    conn.close()


def update_anomaly_runbook(anomaly_id, runbook):
    """Update an anomaly with its generated runbook."""
    conn = get_connection()
    conn.execute(
        'UPDATE anomalies SET runbook = ? WHERE id = ?',
        (runbook, anomaly_id)
    )
    conn.commit()
    conn.close()


def resolve_anomaly(anomaly_id):
    """Mark an anomaly as resolved."""
    conn = get_connection()
    conn.execute(
        "UPDATE anomalies SET status = 'resolved' WHERE id = ?",
        (anomaly_id,)
    )
    # Update session resolved count
    row = conn.execute('SELECT session_id FROM anomalies WHERE id = ?', (anomaly_id,)).fetchone()
    if row:
        conn.execute(
            '''UPDATE sessions SET resolved_count = 
               (SELECT COUNT(*) FROM anomalies WHERE session_id = ? AND status = 'resolved')
               WHERE id = ?''',
            (row['session_id'], row['session_id'])
        )
    conn.commit()
    conn.close()


def check_explanation_cache(message_hash):
    """
    Check if an explanation exists in the cache for the given message hash.

    Args:
        message_hash (str): SHA-256 hash of the normalized error message.
    Returns:
        dict or None: Cached explanation and fix, or None if not found.
    """
    conn = get_connection()
    row = conn.execute(
        'SELECT explanation, suggested_fix FROM explanation_cache WHERE message_hash = ?',
        (message_hash,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def store_explanation_cache(message_hash, explanation, suggested_fix):
    """Store an explanation in the cache for future lookups."""
    conn = get_connection()
    conn.execute(
        '''INSERT OR REPLACE INTO explanation_cache (message_hash, explanation, suggested_fix)
           VALUES (?, ?, ?)''',
        (message_hash, explanation, suggested_fix)
    )
    conn.commit()
    conn.close()


def get_setting(key, default=None):
    """Retrieve a setting value by key."""
    conn = get_connection()
    row = conn.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
    conn.close()
    return row['value'] if row else default


def save_setting(key, value):
    """Save or update a setting."""
    conn = get_connection()
    conn.execute(
        'INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
        (key, value)
    )
    conn.commit()
    conn.close()


def get_all_settings():
    """Retrieve all settings as a dictionary."""
    conn = get_connection()
    rows = conn.execute('SELECT key, value FROM settings').fetchall()
    conn.close()
    return {row['key']: row['value'] for row in rows}


def get_session(session_id):
    """Retrieve a session by ID."""
    conn = get_connection()
    row = conn.execute('SELECT * FROM sessions WHERE id = ?', (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_latest_session():
    """Retrieve the most recent session."""
    conn = get_connection()
    row = conn.execute(
        'SELECT * FROM sessions ORDER BY created_at DESC LIMIT 1'
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_lifetime_stats():
    """
    Retrieve aggregated lifetime monitoring metrics.
    
    Returns:
        dict: Total lines, total sessions, total anomalies, total critical anomalies,
              total resolved anomalies, and category breakdown.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Aggregated session totals
    cursor.execute('''
        SELECT 
            COUNT(id) as total_sessions,
            COALESCE(SUM(total_lines), 0) as total_lines,
            COALESCE(SUM(anomaly_count), 0) as total_anomalies,
            COALESCE(SUM(critical_count), 0) as total_critical,
            COALESCE(SUM(resolved_count), 0) as total_resolved
        FROM sessions
    ''')
    row = cursor.fetchone()
    stats = dict(row) if row else {
        'total_sessions': 0,
        'total_lines': 0,
        'total_anomalies': 0,
        'total_critical': 0,
        'total_resolved': 0
    }
    
    # Category breakdown from anomalies
    cursor.execute('''
        SELECT category, COUNT(*) as count 
        FROM anomalies 
        GROUP BY category
    ''')
    categories = {r['category'] or 'Unknown': r['count'] for r in cursor.fetchall()}
    stats['categories'] = categories
    
    conn.close()
    return stats


def get_all_sessions():
    """
    Retrieve all sessions sorted by date DESC.
    """
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM sessions ORDER BY created_at DESC'
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_session_and_anomalies(session_id):
    """
    Delete a session and all its associated anomalies.
    """
    conn = get_connection()
    conn.execute('DELETE FROM anomalies WHERE session_id = ?', (session_id,))
    conn.execute('DELETE FROM sessions WHERE id = ?', (session_id,))
    conn.commit()
    conn.close()


def clear_all_history():
    """
    Delete all sessions and anomalies from the database to clear history.
    """
    conn = get_connection()
    conn.execute('DELETE FROM anomalies')
    conn.execute('DELETE FROM sessions')
    conn.commit()
    conn.close()

