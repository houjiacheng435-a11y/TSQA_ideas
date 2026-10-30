"""Observational wrapper around the unmodified official execution entry point.

All SQL result batches are gzip-logged. Database opens are read-only, consistent
with the official generator prompt. No answers or reference labels are provided.
"""
import gzip
import json
import os
import runpy
import sqlite3
import sys
from pathlib import Path

TRACE = Path(os.environ['V016_SQL_TRACE'])
CONNECT = sqlite3.connect


def log(obj):
    with gzip.open(TRACE, 'at', encoding='utf-8') as f:
        f.write(json.dumps(obj, default=str, ensure_ascii=False) + '\n')


class Cursor(sqlite3.Cursor):
    def execute(self, sql, parameters=()):
        self.query = sql
        log({'event': 'execute', 'sql': sql, 'parameters': parameters})
        return super().execute(sql, parameters)

    def fetchall(self):
        rows = super().fetchall()
        log({'event': 'fetchall', 'sql': getattr(self, 'query', ''),
             'columns': [x[0] for x in self.description] if self.description else [],
             'n': len(rows), 'rows': [list(x) for x in rows]})
        return rows

    def fetchone(self):
        row = super().fetchone()
        log({'event': 'fetchone', 'sql': getattr(self, 'query', ''), 'row': list(row) if row is not None else None})
        return row

    def fetchmany(self, size=None):
        rows = super().fetchmany() if size is None else super().fetchmany(size)
        log({'event': 'fetchmany', 'sql': getattr(self, 'query', ''), 'n': len(rows), 'rows': [list(x) for x in rows]})
        return rows

    def __iter__(self):
        return self

    def __next__(self):
        row = super().__next__()
        log({'event': 'iterate_row', 'sql': getattr(self, 'query', ''), 'row': list(row)})
        return row


class Connection(sqlite3.Connection):
    def cursor(self, factory=Cursor):
        return super().cursor(factory)

    def execute(self, sql, parameters=()):
        return self.cursor().execute(sql, parameters)


def connect(database, *args, **kwargs):
    db = str(database)
    if not db.startswith('file:'):
        db = Path(db).resolve().as_uri() + '?mode=ro'
    kwargs.update(uri=True, factory=Connection)
    return CONNECT(db, *args, **kwargs)


if __name__ == '__main__':
    sqlite3.connect = connect
    log({'event': 'runner_start', 'database_read_only': True})
    def snapshot(frame, event, arg):
        if (event == 'return' and frame.f_code.co_filename == sys.argv[2]
                and frame.f_code.co_name == '<module>'):
            import numpy as np
            import pandas as pd
            values = {}
            for name, value in frame.f_globals.items():
                if name.startswith('__') or callable(value):
                    continue
                if isinstance(value, pd.DataFrame):
                    values[name] = {'type': 'DataFrame', 'data': value.to_dict(orient='split')}
                elif isinstance(value, pd.Series):
                    values[name] = {'type': 'Series', 'index': list(value.index), 'data': value.tolist()}
                elif isinstance(value, np.ndarray):
                    values[name] = {'type': 'ndarray', 'shape': value.shape, 'data': value.tolist()}
                elif isinstance(value, (dict,list,tuple,str,int,float,bool)) or value is None:
                    values[name] = value
            log({'event': 'final_variables', 'values': values})
    sys.setprofile(snapshot)
    runpy.run_path(os.environ['V016_OFFICIAL_RUNNER'], run_name='__main__')
