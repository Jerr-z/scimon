import argparse
import heapq
import re
from typing import Optional




def generate_graph(file: str, git_hash: Optional[str]) -> Graph:
    yield


def reproduce(file: str, git_hash: Optional[str]):
    # generate a file dependency graph containing the current node
    graph = generate_graph(file, git_hash)
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