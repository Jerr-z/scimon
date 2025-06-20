#!/bin/bash

#------hook to automatically commit changes in git repositories------------
shopt -s extdebug

# Directories
GITCHECK_DIRS="$HOME/.scimon/.autogitcheck"
STRACE_LOG_DIR="$HOME/.scimon/strace.log"

# Variables to keep track of the last inserted row id in each table
# TODO: find a good way to keep track of these, im suggesting atomic counter in the db :)


# commit if dirty, using the supplied commit-msg
_git_commit_if_dirty() {
  local msg="$1"
  local is_pre_command="$2"
  while IFS="" read -r dir || [ -n "$dir" ] 
  do
    echo "Checking directory: $dir $msg $is_pre_command"
    [[ -z "$dir" ]] && continue
    (
      # change directory to the git repo, or skip if it doesn't exist
      cd "$HOME/$dir" 2>/dev/null || echo "Cannot access $dir, skipping...";

      if [[ ! -d .git ]]; then
        # TODO: this part might not work well, need to fix later
        echo "$dir isn't a git repository, would you like to initialize a git repository in $dir? (y/n)"
        read -r answer </dev/tty
        if [[ "$answer" == "y" || "$answer" == "Y" ]]; then
          git init
          git add -A
          git commit -m "Initial commit"
        else
          echo "Skipping $dir, not a git repository."
          return
        fi
      fi

      # if git status isn't clean we will create a commit
      if [ -n "$(git status --porcelain)" ]; then
        local dirty_files

        # when we are doing pre-command git check and see dirty files, simply commit. No need to add a command into the db.
        if (( ! is_pre_command )); then
          _insert_command "$(git rev-parse HEAD)" "" "$msg"
        fi

        dirty_files=$(git status --porcelain | awk '{print $2}');
        
        
        git add -A || echo "git add failed in $dir"
        git commit -m "$msg" || echo "commit failed in $dir"

        if (( ! is_pre_command )); then
          _update_post_command_commit_hash "$(git rev-parse HEAD^)" "$(git rev-parse HEAD)"
          _parse_strace
        fi

        for file in $dirty_files; do
          _insert_file_change "$(git rev-parse HEAD)" "$file"
        done
      fi
    )
  done < "$GITCHECK_DIRS"
}

# Before each user command
_pre_command_git_check() {
  # Skip commands with heredoc redirection that can break strace
  if [[ "$BASH_COMMAND" == *'<<'* ]]; then
      return 0
  fi

  # skips autocompletion commands, traps, and VSCode commands
  [[ -n ${COMP_LINE-} ]] && return 0
  [[ -n ${COMP_POINT-} ]] && return 0
  
  case "$BASH_COMMAND" in
    _post_command_git_check*   |   \
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
  _git_commit_if_dirty "$PREV_CMD" 1

  if [[ $type == file || $type == alias ]]; then
    echo "Running command under strace: $PREV_CMD"
    strace -f -e trace=openat,openat2,open,creat,access,faccessat,faccessat2,statx,stat,lstat,fstat,readlink,readlinkat,rename,renameat,renameat2,link,linkat,symlink,symlinkat,mkdir,mkdirat,execve,execveat,fork,vfork,clone,clone3,connect,accept,accept4,fchownat,fchmodat -o $STRACE_LOG_DIR -- "${cmd_and_args[@]}" 
    # TODO: Maybe flush out the strace log 

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
  _git_commit_if_dirty "$PREV_CMD" 0
  trap '_pre_command_git_check' DEBUG
}


trap 'PREV_CMD=$BASH_COMMAND; _pre_command_git_check' DEBUG
PROMPT_COMMAND='_post_command_git_check'

#-------- database operations --------

# TODO: aknowledge reprozip by using their license? Since I am using their database schema


# Create the tables if they don't exist
_create_tables() {
  trap - DEBUG

    sqlite3 .db 'CREATE TABLE IF NOT EXISTS commands (
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
CREATE INDEX idx_changes_git_hash on file_changes(commit_hash);
CREATE TABLE IF NOT EXISTS processes (
    id INTEGER NOT NULL PRIMARY KEY,
    pid INTEGER NOT NULL,
    commit_hash TEXT NOT NULL,
    parent INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    exit_code INTEGER
);
CREATE INDEX idx_processes_git_hash on processes(commit_hash);
CREATE TABLE IF NOT EXISTS opened_files (
    id INTEGER NOT NULL PRIMARY KEY,
    commit_hash TEXT NOT NULL,
    filename TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mode INTEGER NOT NULL,
    is_directory BOOLEAN NOT NULL,
    pid INTEGER NOT NULL
);
CREATE INDEX idx_opened_files_git_hash on opened_files(commit_hash);
CREATE TABLE IF NOT EXISTS executed_files (
    id INTEGER NOT NULL PRIMARY KEY,
    filename TEXT NOT NULL,
    commit_hash TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pid INTEGER NOT NULL,
    argv TEXT NOT NULL,
    envp TEXT NOT NULL,
    workingdir TEXT NOT NULL
);
CREATE INDEX idx_executed_files_git_hash on executed_files(commit_hash);
'

trap '_pre_command_git_check' DEBUG
}


# Table operations

_insert_command() {

  local pre_commit="$1"
  local post_commit="$2"
  local command="$3"

  sqlite3 .db \
  "INSERT INTO commands (pre_command_commit, post_command_commit, command) \
    VALUES ('$pre_commit', '$post_commit', '$command');"

}

_update_post_command_commit_hash() {

    local pre_command_commit="$1"
    local post_command_commit="$2"

    sqlite3 .db "UPDATE commands 
                SET post_command_commit = '$post_command_commit' 
                WHERE pre_command_commit = '$pre_command_commit';"

}

_insert_file_change() {

  local commit="$1"
  local filename="$2"

  sqlite3 .db "INSERT INTO file_changes (commit_hash, filename) VALUES ('$commit', '$filename');"

}

_insert_process() {

  local run_id="$1"
  local parent="$2"
  local exit_code="$3"

  sqlite3 .db \
  "INSERT INTO processes (run_id, parent, exit_code) \
    VALUES ($pid, $run_id, $parent, $exit_code);"


}

_select_parent_process_primary_key() {
  local parent_pid="$1"
  # TODO: I think I'm a little bit stuck....
  sqlite3 .db "SELECT id FROM processes WHERE pid = $parent_pid"
}

_insert_opened_file() {


  local run_id="$1"
  local name="$2"
  local mode="$3"
  local is_directory="$4"
  local process="$5"

  sqlite3 .db \
  "INSERT INTO opened_files (id, run_id, name, mode, is_directory, process) \
    VALUES ($run_id, '$name', $mode, $is_directory, $process);"


}

_insert_executed_file() {


  local name="$1"
  local run_id="$2"
  local process="$3"
  local argv="$4"
  local envp="$5"
  local workingdir="$6"

  sqlite3 .db \
  "INSERT INTO executed_files (name, run_id, process, argv, envp, workingdir) \
    VALUES ('$name', $run_id, $process, '$argv', '$envp', '$workingdir');"

  LAST_INSERTED_EXECUTED_FILE_ID=$(sqlite3 .db "SELECT last_insert_rowid();")


}

# ---------------- strace parsing ----------------
_parse_strace() {

  
  echo "Parsing strace"
  while read -r line; do
    # extract the process ID, system call, arguments and return value
    if [[ $line =~ ^([0-9]+)\ ([a-z_]+)\((.*)\)\ =\ ([0-9-]+) ]]; then
      local pid="${BASH_REMATCH[1]}"
      local syscall="${BASH_REMATCH[2]}"
      local args="${BASH_REMATCH[3]}"
      local retval="${BASH_REMATCH[4]}"

      # process the extracted information as needed
      #echo "PID: $pid, Syscall: $syscall, Args: $args, Return Value: $retval"
      
      # setup case filter to redirect to different database storing functions
      case "$syscall" in
        fork|clone|clone3|vfork)
        # processes table
        _handle_processes $pid $syscall $args $retval
        ;;
        open|openat|openat2|creat|access|faccessat|faccessat2|stat|lstat|stat64|oldstat|oldlstat|fstatat64|newfstatat|statx|readlink|readlinkat|mkdir|mkdirat|chdir|rename|renameat|renameat2|link|linkat|symlink|symlinkat|connect|accept|accept4|socketcall)
        # handle file opening
        _handle_file_open $pid $syscall $args $retval
        ;;
        execve|execveat)
        # handle executed files
        _handle_file_execute $pid $syscall $args $retval
        ;;    
        esac    
    fi
  done < "$STRACE_LOG_DIR"
  echo "Strace parsing completed."

}

_handle_processes() {
  # store the system calls into the processes table
  local pid="$1"
  local syscall="$2"
  local args="$3"
  local retval="$4"

  if [[ "$retval" =~ ^[0-9]+$ ]] && [[ "$retval" -gt 0 ]]; then 
    local parent_id
    parent_id=''
  fi
}

_handle_file_open() {
  # store the system calls into opened_files table
  local pid="$1"
  local syscall="$2"
  local args="$3"
  local retval="$4"
}

_handle_file_execute() {
  # store the system calls into the executed_files table
  local pid="$1"
  local syscall="$2"
  local args="$3"
  local retval="$4"
}

