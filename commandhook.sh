#!/bin/bash

#------hook to automatically commit changes in git repositories------------
shopt -s extdebug

GITCHECK_DIRS="$HOME/.autogitcheck"
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
        dirty_files=$(git status --porcelain | awk '{print $2}');
        # loop through all the files that are dirty
        for file in $dirty_files; do
          # insert the file into the sqlite database
          insert_item "$file" "$(git rev-parse HEAD)" "" "$msg"
        done

        git add -A || echo "git add failed in $dir"
        git commit -m "$msg" || echo "commit failed in $dir"

        for file in $dirty_files; do
          # update the sqlite database with the post-command commit
          update_post_command_commit_hash "$file" "$(git rev-parse HEAD)"
        done
      fi
    )
  done < "$GITCHECK_DIRS"
}

# Before each user command
autogit_pre() {

  case "$BASH_COMMAND" in
    autogit_post*   |   \
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
    strace -f -e trace=execve -- "${cmd_and_args[@]}" 
    # re-install the DEBUG hook for next time
    trap 'autogit_pre' DEBUG
    # terminate the original command early so it doesn't execute the same effects twice
    return 1
  fi
  # re-install the DEBUG hook for next time
  trap 'autogit_pre' DEBUG
}

# After each user command
autogit_post() {
  # again, disable DEBUG so we don't recurse when we cd/git inside here
  trap - DEBUG

  # use the same $PREV_CMD we saved in the DEBUG hook
  _git_commit_if_dirty "Post-command Commit: $PREV_CMD"
  trap 'autogit_pre' DEBUG
}


trap 'PREV_CMD=$BASH_COMMAND; autogit_pre' DEBUG
PROMPT_COMMAND='autogit_post'

#-------- creates sqlite table if it doesn't exist --------

create_table() {
  sqlite3 -batch .db \
    "CREATE TABLE IF NOT EXISTS autogitcheck ( \
      id INTEGER PRIMARY KEY AUTOINCREMENT, \
      filename TEXT NOT NULL, \
      last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP, \
      pre_command_commit TEXT, \
      post_command_commit TEXT, \
      command TEXT\
    );"
}

insert_item() {
  local filename="$1"
  local pre_commit="$2"
  local post_commit="$3"
  local command="$4"

  sqlite3 .db \
    "INSERT INTO autogitcheck (filename, pre_command_commit, post_command_commit, command) \
     VALUES ('$filename', '$pre_commit', '$post_commit', '$command');"
}

update_post_command_commit_hash() {
    local filename="$1"
    local commit_hash="$2"
    
    sqlite3 .db "UPDATE autogitcheck 
                 SET post_command_commit = '$commit_hash' 
                 WHERE filename = '$filename';"
}
