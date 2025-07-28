#!/bin/bash

#------hook to automatically commit changes in git repositories------------
shopt -s extdebug

# Directories
GITCHECK_DIRS="$HOME/.scimon/.dirs"
STRACE_LOG_DIR="$HOME/.scimon/strace.log"

# Variables
IS_PIPE_IN_PROGRESS=1 # setting it to 1 to take care of the case when history 1 on shell startup is a pipe
#-------- database operations --------

# TODO: aknowledge reprozip by using their license? Since I am using their database schema


# Create the tables if they don't exist
_scimon_initialize_db() {


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
CREATE INDEX IF NOT EXISTS idx_executed_files_git_hash on executed_files(commit_hash);
'

}


# Table operations

_scimon_insert_command() {

  local pre_commit="$1"
  local post_commit="$2"
  local command="$3"
  
  # escape single quotes
  command="${command//\'/\'\'}"
  sqlite3 .db \
  "INSERT INTO commands (pre_command_commit, post_command_commit, command) \
    VALUES ('$pre_commit', '$post_commit', '$command');"

}

_scimon_update_post_command_commit_hash() {

    local pre_command_commit="$1"
    local post_command_commit="$2"

    sqlite3 .db "UPDATE commands 
                SET post_command_commit = '$post_command_commit' 
                WHERE pre_command_commit = '$pre_command_commit';"

}

_scimon_insert_file_change() {

  local commit="$1"
  local filename="$2"

  sqlite3 .db "INSERT INTO file_changes (commit_hash, filename) VALUES ('$commit', '$filename');"

}



_scimon_insert_process() {
  # TODO: is it possible that there might be multiple possible pids with the same child pid and commit hash?
  local pid="$1"
  local commit="$2"
  local child_pid="$3"
  local syscall="$4"

  local parent_pid=$(sqlite3 .db "SELECT pid FROM processes WHERE child_pid='$pid' AND commit_hash='$commit'")
  if [[ -z "$parent_pid" ]]; then
    parent_pid="NULL"
  fi
  sqlite3 .db \
  "INSERT INTO processes (pid, commit_hash, parent_pid, child_pid, syscall) \
    VALUES ($pid, '$commit', $parent_pid, $child_pid, '$syscall');"
}


_scimon_insert_opened_file() {
  local commit="$1"
  local filename="$2"
  local mode="$3"
  local is_directory="$4"
  local pid="$5"
  local syscall="$6"
  local open_flag="$7"

  sqlite3 .db \
  "INSERT INTO opened_files (commit_hash, filename, mode, is_directory, pid, syscall, open_flag) \
    VALUES ('$commit', '$filename', $mode, $is_directory, $pid, '$syscall', '$open_flag');"
}


_scimon_insert_executed_file() {
  local filename="$1"
  local commit="$2"
  local pid="$3"
  local argv="$4"
  local envp="$5"
  local workingdir="$6"
  local syscall="$7"

  sqlite3 .db \
  "INSERT INTO executed_files (filename, commit_hash, pid, argv, envp, workingdir, syscall) \
    VALUES ('$filename', '$commit', $pid, '$argv', '$envp', '$workingdir', '$syscall');"
}

# ---------------- strace parsing ----------------
_scimon_parse_strace() {

  
  echo "Parsing strace"
  while IFS= read -r line || [[ -n "$line" ]]; do
    # extract the process ID, system call, arguments and return value
    if [[ $line =~ ^([0-9]+)\ ([a-z0-9_]+)\((.*)\)\ =\ ([0-9-]+) ]]; then
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
        _scimon_handle_processes "$pid" "$syscall" "$args" "$retval"
        ;;
        open|openat|openat2|creat|access|faccessat|faccessat2|stat|lstat|stat64|oldstat|oldlstat|fstatat64|newfstatat|statx|readlink|readlinkat|mkdir|mkdirat|chdir|rename|renameat|renameat2|link|linkat|symlink|symlinkat|connect|accept|accept4|socketcall)
        # handle file opening
        _scimon_handle_file_open "$pid" "$syscall" "$args" "$retval"
        ;;
        execve|execveat)
        # handle executed files
        _scimon_handle_file_execute "$pid" "$syscall" "$args" "$retval"
        ;;    
        esac    
    fi
  done < "$STRACE_LOG_DIR"
  echo "Strace parsing completed."

}

_scimon_is_file_tracked_by_git() {
  local filename="$1"

  if git ls-files --error-unmatch "$filename" &>/dev/null; then
    return 0
  fi

  return 1
}

_scimon_handle_processes() {
  # store the system calls into the processes table
  local pid="$1"
  local syscall="$2"
  local args="$3"
  local retval="$4"

  # i think its fine to call git directly cuz parent function should be invoked in the proper git directory
  _scimon_insert_process "$pid" "$(git rev-parse HEAD)" "$retval" "$syscall"
}

_scimon_handle_file_open() {
  # store the system calls into opened_files table
  local pid="$1"
  local syscall="$2"
  local args="$3"
  local retval="$4"

  # process arguments first
  local filename=$(printf '%s' "$args" | sed -E 's/.*"([^"]+)".*/\1/')
  local mode=-1
  local is_dir
  local open_flag=""

  if ! _scimon_is_file_tracked_by_git "$filename"; then
    return 0
  fi

  if [[ "$syscall" == "open" ]]; then
    if [[ "$args" =~ \"[^\"]+\",[[:space:]]*([^,\)]+) ]]; then
      open_flag="${BASH_REMATCH[1]}"
    fi
  elif [[ "$syscall" == "openat" || "$syscall" == "openat2" ]]; then
    if [[ "$args" =~ \"[^\"]+\",[[:space:]]*([^,\)]+) ]]; then
      open_flag="${BASH_REMATCH[1]}"
    fi
  fi


  if [[ "$args" =~ ,[[:space:]]*([0-7]{3,4}) ]]; then
    mode="${BASH_REMATCH[1]}"
  fi

  # Check on-disk if it’s a directory
  [[ -d "$filename" ]] && is_dir=1 || is_dir=0

  # store into db
  _scimon_insert_opened_file "$(git rev-parse HEAD)" "$filename" "$mode" "$is_dir" "$pid" "$syscall" "$open_flag"
}

_scimon_handle_file_execute() {
  # store the system calls into the executed_files table
  local pid="$1"
  local syscall="$2"
  local args="$3"
  local retval="$4"
  local workingdir="$(pwd)"
  local filename=""
  if [[ "$args" =~ \"([^\"]+)\" ]]; then
    filename="${BASH_REMATCH[1]}"
  fi
  
  if [[ "$syscall" == "execve" ]]; then
    # Get everything between the first [ and the following ],
    if [[ "$args" =~ \"[^\"]+\",[[:space:]]*(\[.*\]),[[:space:]]* ]]; then
      local argv="${BASH_REMATCH[1]}"
    else
      echo "Failed to extract argv from: $args"
      return 1
    fi
  elif [[ "$syscall" == "execveat" ]]; then
    # Handle execveat format
    if [[ "$args" =~ [^,]+,[[:space:]]*\"[^\"]+\",[[:space:]]*(\[.*\]),[[:space:]]* ]]; then
      local argv="${BASH_REMATCH[1]}"
    else
      echo "Failed to extract argv from execveat: $args"
      return 1
    fi
  fi

  if [[ "$args" =~ (\[.*\]),[[:space:]]*(.*) ]]; then
    local envp="${BASH_REMATCH[2]}"
  else
    echo "Failed to extract envp from: $args"
    local envp="(unknown environment)"
  fi

  argv="${argv//\'/\'\'}"
  # remove trailing comments from envp
  envp=$(echo "$envp" | sed -E 's/[[:space:]]*\/\*.*\*\/[[:space:]]*$//')
  
  # echo "Exec: PID: $pid, filename: $filename, argv: $argv, envp: $envp, retval: $retval"
  _scimon_insert_executed_file "$filename" "$(git rev-parse HEAD)" "$pid" "$argv" "$envp" "$workingdir" "$syscall"
}


# ---------------------- MAIN HOOK LOGIC ---------------------------


_scimon_git_check() {
  local msg="$1"
  local is_pre_command="$2"
  if [[ "$msg" == *"scimon"* ]]; then
    return 1
  fi
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
          _scimon_initialize_db
        else
          echo "Skipping $dir, not a git repository."
          return
        fi
      fi

      # if git status isn't clean we will create a commit
      if [ -n "$(git status --porcelain --untracked-files=all)" ]; then
        local dirty_files

        # when we are doing pre-command git check and see dirty files, simply commit. No need to add a command into the db.
        if (( ! is_pre_command )); then
          _scimon_insert_command "$(git rev-parse HEAD)" "" "$msg"
        fi

        dirty_files=$(git status --porcelain --untracked-files=all | awk '{print $2}');
        
        
        git add -A || echo "git add failed in $dir"
        git commit -m "$msg" || echo "commit failed in $dir"

        if (( ! is_pre_command )); then
          _scimon_update_post_command_commit_hash "$(git rev-parse HEAD^)" "$(git rev-parse HEAD)"
          _scimon_parse_strace
        fi

        for file in $dirty_files; do
          _scimon_insert_file_change "$(git rev-parse HEAD)" "$file"
        done
      fi
    )
  done < "$GITCHECK_DIRS"
}

# Before each user command
_scimon_pre_exec_hook() {
  # Skip commands with heredoc redirection that can break strace
  if [[ "$BASH_COMMAND" == *'<<'* ]]; then
      return 0
  fi

  # skips autocompletion commands, traps, and VSCode commands
  [[ -n $VSCODE_SHELL_INTEGRATION || -n $VSCODE_INJECTION ]] && return 0
  [[ -n ${COMP_LINE-} ]] && return 0
  [[ -n ${COMP_POINT-} ]] && return 0
  # Is source skippable?
  # turn off the DEBUG trap so nothing inside re-triggers us
  # DO NOT PUT ANY HOOK LOGIC ABOVE THIS SINCE IT WILL TRIGGER RECURSION
  trap - DEBUG
  case "$BASH_COMMAND" in
    _scimon_post_exec_hook* | \
    strace* | \
    scimon*) 
      return 0
      ;;
  esac

  local cmd_and_args=()
  # split the command into an array to handle cases with spaces
  read -r -a cmd_and_args <<< "$BASH_COMMAND"
  local type
  type=$(type -t -- "${cmd_and_args[0]}")
  local full_cmd=$(history 1 | sed -E 's/^[[:space:]]*[0-9]+[[:space:]]*//')
  local history_count=$(history 1 | awk '{print $1}')
  
  _scimon_git_check "$full_cmd" 1
  echo "command to be executed: $BASH_COMMAND"

  # handle pipes
  if [[ ("$full_cmd" == *"|"* || "$full_cmd" == *">"*)  && $IS_PIPE_IN_PROGRESS -eq 0 ]]; then
    echo "Running pipe command under strace"
    IS_PIPE_IN_PROGRESS=1
    strace -f -e trace=openat,openat2,open,creat,access,faccessat,faccessat2,statx,stat,lstat,fstat,readlink,readlinkat,rename,renameat,renameat2,link,linkat,symlink,symlinkat,mkdir,mkdirat,execve,execveat,fork,vfork,clone,clone3,connect,accept,accept4,fchownat,fchmodat -o "$STRACE_LOG_DIR" -- bash -c "$full_cmd"
    trap '_scimon_pre_exec_hook' DEBUG
    return 1
  elif [[ "$full_cmd" == *"|"*  && $IS_PIPE_IN_PROGRESS -eq 1 ]]; then
    echo "skipping the debug trap invocation on a pipe command that is in progress"
    return 1
  fi
  # normal case
  if [[ $type == file || $type == alias ]]; then
    echo "Running command under strace: $BASH_COMMAND"
    strace -f -e trace=openat,openat2,open,creat,access,faccessat,faccessat2,statx,stat,lstat,fstat,readlink,readlinkat,rename,renameat,renameat2,link,linkat,symlink,symlinkat,mkdir,mkdirat,execve,execveat,fork,vfork,clone,clone3,connect,accept,accept4,fchownat,fchmodat -o "$STRACE_LOG_DIR" -- "${cmd_and_args[@]}" 
    # TODO: Maybe flush out the strace log 
    # terminate the original command early so it doesn't execute the same effects twice
    return 1
  fi

  PROMPT_COMMAND='_scimon_post_exec_hook'
}

# After each user command
_scimon_post_exec_hook() {
  # again, disable DEBUG so we don't recurse when we cd/git inside here
  trap - DEBUG
  local full_cmd=$(history 1 | sed -E 's/^[[:space:]]*[0-9]+[[:space:]]*//')
  _scimon_git_check "$full_cmd" 0
  IS_PIPE_IN_PROGRESS=0
  trap '_scimon_pre_exec_hook' DEBUG
}

# ------------------------------------ Entry Point -------------------------------
_scimon_init() {
  PROMPT_COMMAND='_scimon_post_exec_hook'
  trap '_scimon_pre_exec_hook' DEBUG
}

PROMPT_COMMAND='_scimon_init'