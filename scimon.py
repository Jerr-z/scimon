import argparse
import subprocess
from typing import Optional
from models import Graph
from db import *
from utils import is_file_tracked_by_git, is_git_hash_on_file, get_latest_commit_for_file
import os

def get_trace_data(git_hash: str, db) -> Tuple[list, list, list]:
    """Retrieve all trace data for a given git hash."""
    print("Getting trace data")
    processes_trace = get_processes_trace(git_hash, db)
    open_files_trace = get_opened_files_trace(git_hash, db)
    executed_files_trace = get_executed_files_trace(git_hash, db)
    return processes_trace, open_files_trace, executed_files_trace


def build_process_nodes_and_edges(graph: Graph, processes_trace: list, git_hash: str):
    """Build process nodes and their relationships in the graph."""
    print("Building process nodes and edges")
    return
    for pt in processes_trace:
        parent_pid, pid, child_pid, syscall = pt

        parent_process_node = Process(git_hash=git_hash, pid=parent_pid)
        process_node = Process(git_hash=git_hash, pid=pid)
        child_process_node = Process(git_hash=git_hash, pid=child_pid)
        
        parent_edge = Edge(parent_process_node, process_node, syscall)
        child_edge = Edge(process_node, child_process_node, syscall)

        graph.add_node(parent_process_node)
        graph.add_node(process_node)
        graph.add_node(child_process_node)
        graph.add_edge(parent_edge)
        graph.add_edge(child_edge)


def build_file_read_write_nodes_and_edges(graph: Graph, file_traces: list, git_hash: str, is_execution: bool = False):
    """Build file nodes and their relationships to processes."""
    print("Building file read write nodes and edges")
    for trace in file_traces:
        pid, filename, syscall, mode, open_flag = trace
        # filter files not part of the git repository
        if not is_file_tracked_by_git(filename):
            continue
        
        file_node = File(git_hash, filename)
        process_node = Process(git_hash=git_hash, pid=pid)
        if "O_WRONLY" in open_flag or "O_CREAT" in open_flag or "O_RDWR" in open_flag or "O_TRUNC" in open_flag:
            process_to_file_edge = Edge(file_node, process_node, syscall)
        else:
            process_to_file_edge = Edge(process_node, file_node, syscall)
        graph.add_node(file_node)
        graph.add_node(process_node)
        graph.add_edge(process_to_file_edge)


def build_file_execution_nodes_and_edges(graph: Graph, file_traces: list, git_hash: str, is_execution: bool = False):
    """Build file nodes and their relationships to processes."""
    print("Building file execution nodes and edges")
    for trace in file_traces:
        pid, filename, syscall = trace
        # filter files not part of the git repository
        if not is_file_tracked_by_git(filename):
            continue
        
        file_node = File(git_hash, filename)
        process_node = Process(git_hash=git_hash, pid=pid)
        write_syscalls = []
        process_to_file_edge = Edge(process_node, file_node, syscall)

        graph.add_node(file_node)
        graph.add_node(process_node)
        graph.add_edge(process_to_file_edge)


def generate_graph(filename: str, git_hash: Optional[str]) -> Graph:
    '''
    Produce a provenance graph for a given file at a version of the given githash, 
    if no githash is provided default to latest version
    '''
    # TODO: check if cwd is a valid directory being monitored
    cwd = os.getcwd()
    # Check if the file exists in the git repository
    if not is_file_tracked_by_git(filename=filename):
        raise ValueError(f"{filename} is not being tracked by the git repository")
    
    # Check if the git hash exists on this file change list
    if not is_git_hash_on_file(filename, git_hash):
        raise ValueError(f"The provided git commit hash {git_hash} does not have any changes related to the file {filename}")
    
    # Initialize
    graph = Graph()
    db = get_db()
    if not git_hash: 
        git_hash = get_latest_commit_for_file(filename)

    print(f"Preparing to generate graph for file {filename} with version {git_hash}")

    processes_trace, open_files_trace, executed_files_trace = get_trace_data(git_hash, db)

    build_process_nodes_and_edges(graph, processes_trace, git_hash)
    build_file_read_write_nodes_and_edges(graph, open_files_trace, git_hash)
    build_file_execution_nodes_and_edges(graph, executed_files_trace, git_hash)

    return graph


def reproduce(file: str, git_hash: Optional[str]):
    # generate a file dependency graph containing the current node
    graph = generate_graph(file, git_hash)
    # reverse dfs/bfs to reproduce parents
    graph.generate_dot()



def main():
    parser = argparse.ArgumentParser(description="A passive scientific reproducibility tool")
    subparsers = parser.add_subparsers(dest="command")

    # reproduce [file] --git-hash=...
    reproduce_parser = subparsers.add_parser("reproduce", help="Reproduce a given file")
    reproduce_parser.add_argument("file", nargs=1, help="The filename of the file you want to reproduce")
    reproduce_parser.add_argument("--git-hash", nargs="?", help="Specific git version of the file")

    # add [directory]
    # list [directory]
    # remove [directory]
    args = parser.parse_args()
    if args.command == "reproduce":
        reproduce(args.file[0], args.git_hash)

if __name__ == "__main__":
    main()