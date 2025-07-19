# Scimon

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub Issues](https://img.shields.io/github/issues/Jerr-z/scimon.svg)](https://github.com/Jerr-z/scimon/issues)
[![GitHub Stars](https://img.shields.io/github/stars/Jerr-z/scimon.svg)](https://github.com/Jerr-z/scimon/stargazers)

> A scientific reproducibility tool supporting evolving experimental workflows

## Table of Contents

- [Scimon](#scimon)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Project Architecture](#project-architecture)
    - [Key Components](#key-components)
    - [Data Flow](#data-flow)
  - [Installation](#installation)
    - [Dependencies](#dependencies)
  - [Usage](#usage)
    - [Running the source code](#running-the-source-code)
  - [Logic Overview](#logic-overview)
    - [Bash Hooks](#bash-hooks)
      - [Pre-exec/Post-exec Hook:](#pre-execpost-exec-hook)
      - [Git Checking/commiting:](#git-checkingcommiting)
      - [Strace Parsing](#strace-parsing)
      - [Database Operations](#database-operations)
    - [Python CLI](#python-cli)
      - [Reproduce](#reproduce)
  - [Contributing](#contributing)
  - [License](#license)

## Overview

This tool aims to passively track the user's interactions with the computing environment through bash, and generate Makefiles that support reproducing any given version of any intermediate or result files produced in the experiment.

## Project Architecture

### Key Components

- **Bash**: Our way to track user actions passively, all commands being run in an interactive bash shell will be intercepted and run with strace instead to capture relevant system calls.
- **Git**: We are utilizing git's powerful version control abilities to keep track of file states. The commit hash also serves as a great unique identifier for storing system calls, commands and showing file changes.
- **SQLite3**: The system calls and related data are then parsed and stored into the database.
- **Python CLI**: Various functionalities are available through the CLI written in python.

### Data Flow

![Data flow](dataflow.png)


## Installation

### Dependencies
- SQLite3
- Python >= 3.9
- Strace
- Git
- Bash

```bash
# Install the CLI
pip install scimon
```

Then copy the contents of `commandhook.sh` into `~/.bashrc`, and restart the bash session for the hooks to take effect.

## Usage

```bash
# Adds current directory for monitoring (WIP)
scimon init 

# Reproduce a given file with optionally a specified commit hash, if no commit hash is specified then the latest version will be reproduced
scimon reproduce [file] --git-hash=abc123

# Lists all directories currently being monitored (WIP)
scimon list

# Removes a directory from being monitored (WIP)
scimon remove [dir]

# Outputs a provenance graph for the given file (WIP)
scimon visualize [file] --git-hash=abc123
```

### Running the source code

I would highly recommend using `uv` to manage the dependencies of this project. Conda works? as an alternative.

1. Navigate to project root
2. `pipx install .`
3. Done

## Logic Overview

### Bash Hooks

#### Pre-exec/Post-exec Hook: 
  
The hooks that fire before and after each command are implemented with bash's debug trap and `PROMPT_COMMAND` respectively.

The debug trap will fire before each bash command is executed, this is achieved through `trap [your-command] DEBUG`.

`PROMPT_COMMAND` will fire before each user prompt shows up in bash, this means that whenever a command finishes executing we can embed our own logic into a bash function and run it.

The code snippet below enable the hooks whenever an interaction bash session starts:
```bash
_init_hook() {
  PROMPT_COMMAND='_post_command_git_check'
  trap '_pre_command_git_check' DEBUG
}

PROMPT_COMMAND='_init_hook'
```

#### Git Checking/commiting: 

For every command that the user enters into bash, we will perform 2 checks through git, they happen everytime:
  - Before the execution of the command and commit if there are any changes in the monitored repository
  - After the execution of the command and commit if there are any changes to the monitored repository

Taking these snapshots allow us to determine commands that are producing side effects, which are the ones worth recording in our case.
  

#### Strace Parsing

In the function `_pre_command_git_check` (I really should rename this already), you can see that we are actually parsing the command and executing it with `strace` instead. This allows us to have a list of the system calls being used to execute the command which is stored in `~/.scimon/strace.log`. After the strace command stops running, we terminate the whole execution early so the original command doesn't get executed again!

Finally, we parse the output log with `_parse_strace`, and store relevant system calls in the proper tables

#### Database Operations

Currently we have 5 tables in the SQL database:
- `commands`: Stores all commands that has a side effect, associated with the commit id before and after the command.
- `executed_files`: Stores all system calls of the `execve` flavour (see details in `commandhook.sh: _parse_strace`).
- `file_changes`: Stores a list of file changes associated with the commit id (Most likely not needed, I created this in the very early stage of the project and haven't found a need for it yet).
- `opened_files`: Stores all system calls of the `openat` flavour, tracks file reads/writes.
- `processes`: Stores system calls of the `clone` flavour, not super useful at the moment but good to have.

### Python CLI

- `scimon.py`: the heart of the application, contains the main functionalities
- `db.py`: database operations
- `utils.py`: various functions that perform git commands that suit the needs of our application, might add other stuff later on
- `models.py`: class definitions for the provenance graph

#### Reproduce

Reproduce takes in a filename and optionally a git commit hash, if no commit hash is specified the latest version will be reproduced by default.

First, we generate a provenance graph based on the commit.

Then we perform a graph traversal from the file node that we want to reproduce to identify all dependencies needed. If there are no dependent files for the current file, that means the current file isn't produced by a command side-effect and a `git restore` command is sufficient. Otherwise, we recursively call `reproduce` on parent files.

Once we have a list of parent files identified, we then fetch the command used to produce the current file from the database and form a make rule with it. The rule is then appended into the makefile.

Here's a very basic example of a Makefile generated by reproduce. 

I prepared a mock experiment where `script.py` read from `digital_mental_health.csv` and generates a set of plots, then I modified `script.py` slightly so that `screen_time_vs_digital_device_usage.png` is changed. 

Then I ran `scimon reproduce out/screen_time_vs_digital_device_usage.png --git-hash=version-1-commit-id`

We get
```Makefile
script.py: 
	git restore --source=f985c1d438fa81273483ed4229c87f69c16b1eaa -- script.py
data/digital_diet_mental_health.csv: 
	git restore --source=f985c1d438fa81273483ed4229c87f69c16b1eaa -- data/digital_diet_mental_health.csv
out/screen_time_vs_digital_device_usage.png: data/digital_diet_mental_health.csv script.py
	python3 script.py
```

In this example, the CSV file and the python script are not modified by bash command side-effects, therefore we perform `git restore` to check them out at their proper versions.

The plot is modified by `python3 script.py`, and therefore requires the parent files to be reproduced first before executing the captured command once again.

Then 
```Bash
$ make -B -f reproduce.mk out/screen_time_vs_digital_device_usage.png
git restore --source=f985c1d438fa81273483ed4229c87f69c16b1eaa -- script.py
git restore --source=f985c1d438fa81273483ed4229c87f69c16b1eaa -- data/digital_diet_mental_health.csv
python3 script.py
...script outputs...
branch
$
```

And we can see the original plots are generated once again through looking at the git change list:
![alt text](changelist.png)


## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
