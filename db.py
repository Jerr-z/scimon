import sqlite3
from models import Process, File, Edge
from typing import List, Tuple
DB_NAME=".db"


def get_db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_NAME)
    print("Database connection acquired")
    return con

def get_processes_trace(commit_hash: str, db: sqlite3.Connection) -> List[Tuple]:
    '''Returns a list of (parent_pid, pid, child_pid, syscall) for a given commit hash'''
    cursor = db.cursor()
    processes_sql = '''SELECT DISTINCT parent_pid, pid, child_pid, syscall FROM processes WHERE commit_hash = ?'''
    cursor.execute(processes_sql, (commit_hash,))
    return cursor.fetchall()


def get_opened_files_trace(commit_hash: str, db: sqlite3.Connection) -> List[Tuple]:
    '''Returns a list of (pid, filename, syscall, mode, open_flag) for a given commit hash'''
    cursor = db.cursor()
    opened_files_sql = '''SELECT DISTINCT pid, filename, syscall, mode, open_flag FROM opened_files WHERE commit_hash = ?'''
    cursor.execute(opened_files_sql, (commit_hash,))
    return cursor.fetchall()

def get_executed_files_trace(commit_hash: str, db: sqlite3.Connection) -> List[Tuple]:
    '''Returns a list of (pid, filename, syscall) for a given commit hash'''
    cursor = db.cursor()
    executed_files_sql = '''SELECT pid, filename, syscall FROM executed_files WHERE commit_hash = ?'''
    cursor.execute(executed_files_sql, (commit_hash,))
    return cursor.fetchall()

def get_command(commit_hash: str, db: sqlite3.Connection) -> str:
    '''Returns the command associated where commit_hash is the post command commit hash in the commands table'''
    cursor = db.cursor()
    get_command_sql = '''SELECT command FROM commands WHERE post_command_commit = ?'''
    cursor.execute(get_command_sql, (commit_hash,))
    return cursor.fetchall()[0][0]