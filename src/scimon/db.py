import sqlite3
from scimon.models import ProcessTrace, FileExecutionTrace, FileOpenTrace
from typing import List, Tuple

DB_NAME=".db"


def get_db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_NAME)
    print("Database connection acquired")
    return con

def get_processes_trace(commit_hash: str, db: sqlite3.Connection) -> List[ProcessTrace]:
    '''Returns a list of (parent_pid, pid, child_pid, syscall) for a given commit hash'''
    db.row_factory = lambda cursor, row: ProcessTrace(*row)
    cursor = db.cursor()
    processes_sql = '''SELECT DISTINCT parent_pid, pid, child_pid, syscall FROM processes WHERE commit_hash = ?'''
    cursor.execute(processes_sql, (commit_hash,))
    return cursor.fetchall()


def get_opened_files_trace(commit_hash: str, db: sqlite3.Connection) -> List[FileOpenTrace]:
    '''Returns a list of (pid, filename, syscall, mode, open_flag) for a given commit hash'''
    db.row_factory = lambda cursor, row: FileOpenTrace(*row)
    cursor = db.cursor()
    opened_files_sql = '''SELECT DISTINCT pid, filename, syscall, mode, open_flag FROM opened_files WHERE commit_hash = ?'''
    cursor.execute(opened_files_sql, (commit_hash,))
    return cursor.fetchall()

def get_executed_files_trace(commit_hash: str, db: sqlite3.Connection) -> List[FileExecutionTrace]:
    '''Returns a list of (pid, filename, syscall) for a given commit hash'''
    db.row_factory = lambda cursor, row: FileExecutionTrace(*row)
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

def initialize_db() -> None:
    '''Initializes the database with proper tables in the current working directory'''
    db = get_db()
    cursor = db.cursor()
    create_tables_sql="""CREATE TABLE IF NOT EXISTS commands (
    id INTEGER NOT NULL PRIMARY KEY, 
    pre_command_commit TEXT,
    post_command_commit TEXT,
    command TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_commands_pre_commit ON commands(pre_command_commit);
CREATE INDEX IF NOT EXISTS idx_commands_post_commit on commands(post_command_commit);
CREATE TABLE IF NOT EXISTS file_changes (
    id INTEGER NOT NULL PRIMARY KEY,
    commit_hash TEXT NOT NULL,
    filename TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_changes_git_hash on file_changes(commit_hash);
CREATE TABLE IF NOT EXISTS processes (
    id INTEGER NOT NULL PRIMARY KEY,
    pid INTEGER NOT NULL,
    commit_hash TEXT NOT NULL,
    parent_pid INTEGER,
    child_pid INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    syscall TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_processes_git_hash on processes(commit_hash);
CREATE TABLE IF NOT EXISTS opened_files (
    id INTEGER NOT NULL PRIMARY KEY,
    commit_hash TEXT NOT NULL,
    filename TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mode INTEGER NOT NULL,
    is_directory BOOLEAN NOT NULL,
    pid INTEGER NOT NULL,
    syscall TEXT NOT NULL,
    open_flag TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_opened_files_git_hash on opened_files(commit_hash);
CREATE TABLE IF NOT EXISTS executed_files (
    id INTEGER NOT NULL PRIMARY KEY,
    filename TEXT NOT NULL,
    commit_hash TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pid INTEGER NOT NULL,
    argv TEXT NOT NULL,
    envp TEXT NOT NULL,
    workingdir TEXT NOT NULL,
    syscall TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_executed_files_git_hash on executed_files(commit_hash);"""
    cursor.executescript(create_tables_sql)