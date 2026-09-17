"""Durable, ordered UI events. Retain a bounded replay window per installation."""
import json
import re
import sqlite3
import time


def redact(value):
    if isinstance(value, dict):
        return {key: '[redacted]' if re.search(r'password|secret|api_key|authorization|access_token', key, re.I)
                else redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value[:200]]
    if isinstance(value, str):
        value = re.sub(r'(?i)(bearer\s+)[\w.\-]+', r'\1[redacted]', value)
        return value[:24000]
    return value


class EventJournal:
    def __init__(self, db_path):
        self.db_path = db_path
        with self.connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS run_events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, '
                         'event TEXT NOT NULL, project_id TEXT, data_json TEXT NOT NULL, created_at REAL NOT NULL)')

    def connect(self):
        return sqlite3.connect(self.db_path, timeout=30)

    def append(self, event, data):
        data = redact(data)
        with self.connect() as conn:
            cursor = conn.execute('INSERT INTO run_events(event,project_id,data_json,created_at) VALUES(?,?,?,?)',
                                  (event, data.get('project_id'), json.dumps(data, ensure_ascii=False), time.time()))
            sequence = cursor.lastrowid
            conn.execute('DELETE FROM run_events WHERE sequence <= ?', (sequence - 10000,))
        return {'event': event, 'data': data, 'sequence': sequence}

    def replay(self, after=0, project_id=None, limit=1000):
        with self.connect() as conn:
            query = 'SELECT sequence,event,data_json FROM run_events WHERE sequence > ?'
            args = [max(0, after)]
            if project_id:
                query += ' AND project_id = ?'
                args.append(project_id)
            rows = conn.execute(query + ' ORDER BY sequence LIMIT ?', [*args, min(1000, max(1, limit))]).fetchall()
        return [{'sequence': seq, 'event': event, 'data': json.loads(data)} for seq, event, data in rows]

    def recent_cursor(self, limit=200):
        with self.connect() as conn:
            row = conn.execute('SELECT sequence FROM run_events ORDER BY sequence DESC LIMIT 1 OFFSET ?', (max(0, limit - 1),)).fetchone()
        return max(0, row[0] - 1) if row else 0
