import argparse
import subprocess
from typing import Optional
from models import Graph
from db import *
from utils import is_file_tracked_by_git, is_git_hash_on_file


def get_trace_data(git_hash: str, db) -> Tuple[list, list, list]:
    """Retrieve all trace data for a given git hash."""
    processes_trace = get_processes_trace(git_hash, db)
    open_files_trace = get_opened_files_trace(git_hash, db)
    executed_files_trace = get_executed_files_trace(git_hash, db)
    return processes_trace, open_files_trace, executed_files_trace


def build_process_nodes_and_edges(graph: Graph, processes_trace: list, git_hash: str):
    """Build process nodes and their relationships in the graph."""
    for pt in processes_trace:
        parent_pid, pid, child_pid, syscall = pt

        parent_process_node = Process(git_hash=git_hash, pid=parent_pid, parent_pid=None, child_pid=pid)
        process_node = Process(git_hash=git_hash, pid=pid, parent_pid=parent_pid, child_pid=child_pid)
        child_process_node = Process(git_hash=git_hash, pid=child_pid, parent_pid=pid, child_pid=None)
        
        parent_edge = Edge(parent_process_node, process_node, syscall)
        child_edge = Edge(process_node, child_process_node, syscall)

        graph.add_node(parent_process_node)
        graph.add_node(process_node)
        graph.add_node(child_process_node)
        graph.add_edge(parent_edge)
        graph.add_edge(child_edge)


def build_file_access_nodes_and_edges(graph: Graph, file_traces: list, git_hash: str, is_execution: bool = False):
    """Build file nodes and their relationships to processes."""
    for trace in file_traces:
        pid, filename, syscall = trace
        
        file_node = File(git_hash, filename)
        process_node = Process(git_hash=git_hash, pid=pid)
        process_to_file_edge = Edge(process_node, file_node, syscall)

        graph.add_node(file_node)
        graph.add_node(process_node)
        graph.add_edge(process_to_file_edge)




def generate_graph(filename: str, git_hash: Optional[str]) -> Graph:
    '''
    Produce a provenance graph for a given file at a version of the given githash, 
    if no githash is provided default to latest version
    '''
    
    # Check if the file exists in the git repository
    if not is_file_tracked_by_git(filename=filename):
        print(f"Error: {filename} is not being tracked by the git repository")
        return
    
    # Check if the git hash exists on this file change list
    if not is_git_hash_on_file(filename, git_hash):
        print(f"Error: the provided git commit hash does not have any changes related to the file {filename}")
        return
    
    # Initialize
    graph = Graph()
    db = get_db()
    if not git_hash: 
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True
        ).strip()

    processes_trace, open_files_trace, executed_files_trace = get_trace_data(git_hash, db)

    build_process_nodes_and_edges(graph, processes_trace, git_hash)
    build_file_access_nodes_and_edges(graph, open_files_trace, git_hash)
    build_file_access_nodes_and_edges(graph, executed_files_trace, git_hash)

    return graph


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