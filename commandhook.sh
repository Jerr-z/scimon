#!/bin/bash

#------hook to automatically commit changes in git repositories------------
shopt -s extdebug

GITCHECK_DIRS="$HOME/.autogitcheck"

# Variables to keep track of the last inserted row id in each table
LAST_INSERTED_COMMAND_ID=-1
LAST_INSERTED_PROCESS_ID=-1
LAST_INSERTED_OPENED_FILE_ID=-1
LAST_INSERTED_EXECUTED_FILE_ID=-1

# commit if dirty, using the supplied commit-msg
_git_commit_if_dirty() {
  local msg="$1"
  while IFS="" read -r dir || [ -n "$dir" ] 
  do
    echo "Checking directory: $dir $msg"
    [[ -z "$dir" ]] && continue
    (
      # change directory to the git repo, or skip if it doesn't exist
      cd "$HOME/$dir" 2>/dev/null || echo "Cannot access $dir, skipping...";

      if [[ ! -d .git ]]; then
        echo "$dir isn't a git repository, would you like to initialize a git repository in $dir? (y/n)"
        read -r answer
        if [[ "$answer" == "y" || "$answer" == "Y" ]]; then
          git init
          git add -A
          git commit -m "Initial commit"
        else
          echo "Skipping $dir, not a git repository."
          return
        fi
      fi
      if [ -n "$(git status --porcelain)" ]; then
        local dirty_files
        local rows_to_update
        dirty_files=$(git status --porcelain | awk '{print $2}');
        rows_to_update = ();
        # loop through all the files that are dirty
        for file in $dirty_files; do
          # insert the file into the sqlite database
          _insert_command "$file" "$(git rev-parse HEAD)" "" "$msg"
          rows_to_update += ("$LAST_INSERTED_COMMAND_ID")
        done

        git add -A || echo "git add failed in $dir"
        git commit -m "$msg" || echo "commit failed in $dir"

        for id in $rows_to_update; do
          # update the sqlite database with the post-command commit
          # TODO: fix how this is being called, define a local list to save all the row ids of the dirty files, then loop through them and update the hash
          _update_post_command_commit_hash "$id" "$(git rev-parse HEAD)"
        done
      fi
    )
  done < "$GITCHECK_DIRS"
}

# Before each user command
_pre_command_git_check() {

  # skips autocompletion commands, traps, and VSCode commands
  [[ -n ${COMP_LINE-} ]] && return 0
  [[ -n ${COMP_POINT-} ]] && return 0
  
  case "$BASH_COMMAND" in
    _post_command_git_check
  *   |   \
    trap\ -*       |   \
    __vsc_*        )
      return 0
      ;;
  esac
  # turn off the DEBUG trap so nothing inside re-triggers us
  trap - DEBUG

  # capture what command is about to run
  PREV_CMD="$BASH_COMMAND"

  local cmd_and_args=()
  # split the command into an array to handle cases with spaces
  read -r -a cmd_and_args <<< "$PREV_CMD"

  local type
  type=$(type -t -- "${cmd_and_args[0]}")
  # do our check
  _git_commit_if_dirty "Pre-command Commit: $PREV_CMD"

  if [[ $type == file || $type == alias ]]; then
    echo "Running command under strace: $PREV_CMD"
    # TODO: pipe the output to a function that parses the strace output, then call correponding database operations
    strace -f -e trace=openat,openat2,open,creat,access,faccessat,faccessat2,statx,stat,lstat,fstat,readlink,readlinkat,rename,renameat,renameat2,link,linkat,symlink,symlinkat,mkdir,mkdirat,execve,execveat,fork,vfork,clone,clone3,connect,accept,accept4,fchownat,fchmodat -o strace.log -- "${cmd_and_args[@]}" 
    # re-install the DEBUG hook for next time
    trap '_pre_command_git_check' DEBUG
    # terminate the original command early so it doesn't execute the same effects twice
    return 1
  fi
  # re-install the DEBUG hook for next time
  trap '_pre_command_git_check' DEBUG
}

# After each user command
_post_command_git_check() {
  # again, disable DEBUG so we don't recurse when we cd/git inside here
  trap - DEBUG

  # use the same $PREV_CMD we saved in the DEBUG hook
  _git_commit_if_dirty "Post-command Commit: $PREV_CMD"
  trap '_pre_command_git_check' DEBUG
}


trap 'PREV_CMD=$BASH_COMMAND; _pre_command_git_check' DEBUG
PROMPT_COMMAND='_post_command_git_check'

#-------- database operations --------

# TODO: aknowledge reprozip by using their license? Since I am using their database schema


# Create the tables if they don't exist
_create_tables() {
  sqlite3 -batch .db \
    "CREATE TABLE IF NOT EXISTS commands ( \
      id INTEGER NOT NULL PRIMARY KEY, \
      filename TEXT NOT NULL, \
      last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP, \ 
      pre_command_commit TEXT, \
      post_command_commit TEXT, \
      command TEXT\
    );\
    CREATE TABLE IF NOT EXISTS processes ( \
      id INTEGER NOT NULL PRIMARY KEY, \
      run_id INTEGER NOT NULL, \
      parent INTEGER, \
      timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, \
      exit_code INTEGER \
      ); \
      CREATE TABLE IF NOT EXISTS opened_files( \
      id INTEGER NOT NULL PRIMARY KEY, \
      run_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, \
      mode INTEGER NOT NULL, \
      is_directory BOOLEAN NOT NULL,
      process INTEGER NOT NULL \
      ); \
      CREATE TABLE IF NOT EXISTS executed_files( \
      id INTEGER NOT NULL PRIMARY KEY, \
      name TEXT NOT NULL, \
      run_id INTEGER NOT NULL, \
      timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, \
      process INTEGER NOT NULL, \
      argv TEXT NOT NULL, \
      envp TEXT NOT NULL, \
      workingdir TEXT NOT NULL, \
      ); \
    "
}

# Table operations

_insert_command() {
  local filename="$1"
  local pre_commit="$2"
  local post_commit="$3"
  local command="$4"

  sqlite3 -batch .db \
    "INSERT INTO commands (filename, pre_command_commit, post_command_commit, command) \
     VALUES ('$filename', '$pre_commit', '$post_commit', '$command');"
  LAST_INSERTED_COMMAND_ID=$(sqlite3 -batch .db "SELECT last_insert_rowid();")
}

_update_post_command_commit_hash() {
    local id="$1"
    local commit_hash="$2"
    sqlite3 -batch .db "UPDATE autogitcheck 
                 SET post_command_commit = '$commit_hash' 
                 WHERE id = '$id';"
}

_insert_process() {
  local run_id="$1"
  local parent="$2"
  local exit_code="$3"

  sqlite3 -batch .db \
    "INSERT INTO processes (run_id, parent, exit_code) \
     VALUES ($pid, $run_id, $parent, $exit_code);"

  LAST_INSERTED_PROCESS_ID=$(sqlite3 -batch .db "SELECT last_insert_rowid();")
}

_insert_opened_file() {
  local run_id="$1"
  local name="$2"
  local mode="$3"
  local is_directory="$4"
  local process="$5"
  sqlite3 -batch .db \
    "INSERT INTO opened_files (id, run_id, name, mode, is_directory, process) \
     VALUES ($run_id, '$name', $mode, $is_directory, $process);"

  LAST_INSERTED_OPENED_FILE_ID=$(sqlite3 -batch .db "SELECT last_insert_rowid();")
}

_insert_executed_file() {
  local name="$1"
  local run_id="$2"
  local process="$3"
  local argv="$4"
  local envp="$5"
  local workingdir="$6"

  sqlite3 -batch .db \
    "INSERT INTO executed_files (name, run_id, process, argv, envp, workingdir) \
     VALUES ('$name', $run_id, $process, '$argv', '$envp', '$workingdir');"

  LAST_INSERTED_EXECUTED_FILE_ID=$(sqlite3 -batch .db "SELECT last_insert_rowid();")
}

# ---------------- strace parsing ----------------
_parse_strace() {
  trap - DEBUG
  local strace_file="$1"
  if [[ ! -f "$strace_file" ]]; then
    echo "Strace file not found: $strace_file"
    return 1
  fi

  echo "Parsing strace file: $strace_file"
  while read -r line; do
    # extract the process ID, system call, arguments and return value
    if [[ $line =~ ^([0-9]+)\ ([a-z_]+)\((.*)\)\ =\ ([0-9-]+) ]]; then
      local pid="${BASH_REMATCH[1]}"
      local syscall="${BASH_REMATCH[2]}"
      local args="${BASH_REMATCH[3]}"
      local retval="${BASH_REMATCH[4]}"

      # process the extracted information as needed
      echo "PID: $pid, Syscall: $syscall, Args: $args, Return Value: $retval"
      
      
    fi
  done < "$strace_file"
  echo "Strace parsing completed."
  trap '_pre_command_git_check' DEBUG
}

