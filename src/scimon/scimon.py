from typing import Optional, List, Tuple
from scimon.models import Graph, Node, Edge, Process, File, ProcessTrace, FileOpenTrace, FileExecutionTrace
from scimon.db import get_db, get_processes_trace, get_opened_files_trace, get_executed_files_trace, get_command
from scimon.utils import is_file_tracked_by_git, is_git_hash_on_file, get_latest_commit_for_file, get_closest_ancestor_hash
import os
from jinja2 import Template
from pathlib import Path

MAKE_FILE_RULE_TEMPLATE = Template("""
{{ target }}: {{ prerequisites }}
\t{{ recipe }}
""")

MAKE_FILE_NAME='reproduce.mk'

def get_trace_data(git_hash: str, db) -> Tuple[List[ProcessTrace], List[FileOpenTrace], List[FileExecutionTrace]]:
    """Retrieve all trace data for a given git hash."""
    print("Getting trace data")
    processes_trace = get_processes_trace(git_hash, db)
    open_files_trace = get_opened_files_trace(git_hash, db)
    executed_files_trace = get_executed_files_trace(git_hash, db)
    return processes_trace, open_files_trace, executed_files_trace


def build_process_nodes_and_edges(graph: Graph, processes_trace: List[ProcessTrace], git_hash: str):
    """Build process nodes and their relationships in the graph."""
    print("Building process nodes and edges")

    for trace in processes_trace:

       
        process_node = Process(git_hash=git_hash, pid=trace.pid)
        child_process_node = Process(git_hash=git_hash, pid=trace.child_pid)
        
        child_edge = Edge(process_node, child_process_node, trace.syscall)

        graph.add_node(process_node)
        graph.add_node(child_process_node)
        graph.add_edge(child_edge)
        
        if trace.parent_pid:
            parent_process_node = Process(git_hash=git_hash, pid=trace.parent_pid)
            parent_edge = Edge(parent_process_node, process_node, trace.syscall)
            graph.add_node(parent_process_node)
            graph.add_edge(parent_edge)

def build_file_read_write_nodes_and_edges(graph: Graph, file_traces: List[FileOpenTrace], git_hash: str, is_execution: bool = False):
    """Build file nodes and their relationships to processes."""
    print("Building file read write nodes and edges")
    for trace in file_traces:

        # filter files not part of the git repository
        if not is_file_tracked_by_git(trace.filename):
            continue
        if os.path.isdir(trace.filename):
            continue
        # normalize filename
        cwd = Path(os.getcwd())
        abs_path = Path(trace.filename).resolve()
        filename = str(abs_path.relative_to(cwd))

        file_node = File(git_hash, filename)
        # if file with same path already in the graph, fetch that node in the graph
        # TODO:
        process_node = Process(git_hash=git_hash, pid=trace.pid)
        if "O_WRONLY" in trace.open_flag or "O_CREAT" in trace.open_flag or "O_RDWR" in trace.open_flag or "O_TRUNC" in trace.open_flag:
            process_to_file_edge = Edge(file_node, process_node, trace.syscall)
        else:
            process_to_file_edge = Edge(process_node, file_node, trace.syscall)
        graph.add_node(file_node)
        graph.add_node(process_node)
        graph.add_edge(process_to_file_edge)


def build_file_execution_nodes_and_edges(graph: Graph, file_traces: List[FileExecutionTrace], git_hash: str, is_execution: bool = False):
    """Build file nodes and their relationships to processes."""
    print("Building file execution nodes and edges")
    for trace in file_traces:
        # filter files not part of the git repository
        if not is_file_tracked_by_git(trace.filename):
            continue
        if os.path.isdir(trace.filename):
            continue
        # normalize filename
        cwd = Path(os.getcwd())
        abs_path = Path(trace.filename).resolve()
        filename = str(abs_path.relative_to(cwd))


        file_node = File(git_hash, filename)
        
        process_node = Process(git_hash=git_hash, pid=trace.pid)
        process_to_file_edge = Edge(process_node, file_node, trace.syscall)

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