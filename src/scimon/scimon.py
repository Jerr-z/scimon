from typing import Optional
from scimon.models import Graph, Node, Edge
from scimon.db import *
from scimon.utils import *
import os
from jinja2 import Template
from pathlib import Path

MAKE_FILE_RULE_TEMPLATE = Template("""
{{ target }}: {{ prerequisites }}
\t{{ recipe }}
""")

MAKE_FILE_NAME='reproduce.mk'

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
        if os.path.isdir(filename):
            continue
        # normalize filename
        cwd = Path(os.getcwd())
        abs_path = Path(filename).resolve()
        filename = str(abs_path.relative_to(cwd))

        file_node = File(git_hash, filename)
        # if file with same path already in the graph, fetch that node in the graph
        # TODO:
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
        if os.path.isdir(filename):
            continue
        # normalize filename
        cwd = Path(os.getcwd())
        abs_path = Path(filename).resolve()
        filename = str(abs_path.relative_to(cwd))


        file_node = File(git_hash, filename)
        
        process_node = Process(git_hash=git_hash, pid=pid)
        process_to_file_edge = Edge(process_node, file_node, syscall)

        graph.add_node(file_node)
        graph.add_node(process_node)
        graph.add_edge(process_to_file_edge)


def generate_graph(filename: str, git_hash: str) -> Graph:
    '''
    Produce a provenance graph for a given file at a version of the given githash, 
    '''
    # Initialize
    graph = Graph()
    db = get_db()
    
    print(f"Preparing to generate graph for file {filename} with version {git_hash}")

    processes_trace, open_files_trace, executed_files_trace = get_trace_data(git_hash, db)

    build_process_nodes_and_edges(graph, processes_trace, git_hash)
    build_file_read_write_nodes_and_edges(graph, open_files_trace, git_hash)
    build_file_execution_nodes_and_edges(graph, executed_files_trace, git_hash)

    return graph



def reproduce(file: str, git_hash: Optional[str]):

    # TODO: check if cwd is a valid directory being monitored
    cwd = Path(os.getcwd())

    # Normalize file
    abs_path = Path(file).resolve()
    file = str(abs_path.relative_to(cwd))

    # Check if the file is a directory
    if os.path.isdir(file):
        print(f"{file} is a directory, skipping...")
        return

    # Check if the file exists in the git repository
    if not is_file_tracked_by_git(filename=file):
        print(f"{file} is not being tracked by the git repository")
        return
    
    # Check if the git hash exists on this file change list
    if not is_git_hash_on_file(file, git_hash):
        print(f"The provided git commit hash {git_hash} does not have any changes related to the file {file}")
        return 
    if not git_hash: 
        git_hash = get_latest_commit_for_file(file)

    # generate a file dependency graph containing the current node
    graph = generate_graph(file, git_hash)
    # traverse up the graph to get parents
    adj = graph.get_adj_list()

    # for k,v in adj.items():
    #     if isinstance(k, File):
    #         print(k.filename, ":", end=" ")
    #     else:
    #         print(k.pid, ":", end=" ")
    #     for n in v:
    #         if isinstance(n, File):
    #             print(n.filename, end=" ")
    #         else:
    #             print(n.pid, end=" ")
    #     print()
    
    if File(git_hash, file) not in adj:
        print(f"The current file {file} has no dependencies, directly checking the version {git_hash} out from git...")
        rule = MAKE_FILE_RULE_TEMPLATE.render(target=file, prerequisites="", recipe=f"git restore --source={git_hash} -- {file}")
        with open(MAKE_FILE_NAME, 'a') as f:
            f.write(rule)
        return

    dependencies = set()

    def dfs(node: Node):
        if node in adj:
            for parent in adj[node]:
                if isinstance(parent, File):
                    if parent.filename not in dependencies:
                        print(f"Parent file {parent.filename} of {file} located, calling reproduce on it...")
                        target_hash = get_closest_ancestor_hash(parent.filename, git_hash)
                        # call reproduce on that version
                        dependencies.add(parent.filename)
                        reproduce(parent.filename, target_hash)
                else:
                    print(f"Process {parent.pid} located from traversing the provenance graph, continuing traversing")
                    dfs(parent)
        
    dfs(File(git_hash, file))
    print("Fetching command from database")
    command = get_command(git_hash, get_db())
    # create the make rule
    rule = MAKE_FILE_RULE_TEMPLATE.render(target=file, prerequisites=" ".join(dependencies), recipe=command)
    with open(MAKE_FILE_NAME, 'a') as f:
        f.write(rule)





# def main():
#     parser = argparse.ArgumentParser(description="A passive scientific reproducibility tool")
#     subparsers = parser.add_subparsers(dest="command")

#     # reproduce [file] --git-hash=...
#     reproduce_parser = subparsers.add_parser("reproduce", help="Reproduce a given file")
#     reproduce_parser.add_argument("file", nargs=1, help="The filename of the file you want to reproduce")
#     reproduce_parser.add_argument("--git-hash", nargs="?", help="Specific git version of the file")

#     # TODO
#     # add [directory]
#     # list [directory]
#     # remove [directory]
#     args = parser.parse_args()
#     if args.command == "reproduce":
#         reproduce(args.file[0], args.git_hash)

# if __name__ == "__main__":
#     main()