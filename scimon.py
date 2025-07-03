import argparse
import subprocess
from typing import Optional
from models import Graph
from db import *



def generate_graph(filename: str, git_hash: Optional[str]) -> Graph:
    '''
    Produce a provenance graph for a given file at a version <= the given githash, 
    if no githash is provided default to latest version
    '''
    graph = Graph()
    db = get_db()
    # if not git_hash: 
    #     git_hash = subprocess.check_output(
    #         ["git", "rev-parse", "HEAD"],
    #         text=True
    #     ).strip()

    processes_trace = get_processes_trace(git_hash, db)
    open_files_trace = get_opened_files_trace(git_hash, db)
    executed_files_trace = get_executed_files_trace(git_hash, db)
    yield


def reproduce(file: str, git_hash: Optional[str]):
    # generate a file dependency graph containing the current node
    graph = generate_graph(git_hash)
    # reverse dfs/bfs to reproduce parents


    yield


def main():
    parser = argparse.ArgumentParser(description="A passive scientific reproducibility tool")
    subparsers = parser.add_subparsers(dest="command")

    reproduce_parser = subparsers.add_parser("reproduce", help="Reproduce a given file")
    reproduce_parser.add_argument("file", nargs=1, help="The filename of the file you want to reproduce")
    reproduce_parser.add_argument("--git-hash", nargs="?", help="Specific git version of the file")

    args = parser.parse_args()
    if args.command == "reproduce":
        reproduce(args.file, args.git_hash)

if __name__ == "__main__":
    main()