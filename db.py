import sqlite3

DB_NAME=".db"


def get_db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_NAME)
    return con

