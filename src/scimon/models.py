from typing import Optional, Set, Dict, NamedTuple
import graphviz

class Node:
    def __init__(self, git_hash: str):
        self.git_hash = git_hash

class Process(Node):
    def __init__(self, git_hash: str, pid: int):
        super().__init__(git_hash)
        self.pid = pid
    def __eq__(self, other):
        return isinstance(other, Process) and self.git_hash == other.git_hash and self.pid == other.pid
    
    def __hash__(self):
        return hash((self.git_hash, self.pid))

class File(Node):
    def __init__(self, git_hash: str, filename: str):
        super().__init__(git_hash)
        self.filename = filename

    def __eq__(self, other):
        return isinstance(other, File) and self.git_hash == other.git_hash and self.filename == other.filename
    
    def __hash__(self):
        return hash((self.git_hash, self.filename))
    
class Edge:
    def __init__(self, in_node: Node, out_node: Node, syscall: str):
        self.in_node = in_node
        self.out_node = out_node
        self.syscall = syscall
    
    def __eq__(self, other):
        return isinstance(other, Edge) and self.in_node == other.in_node and self.out_node == other.out_node and self.syscall == other.syscall
    
    def __hash__(self):
        return hash((self.in_node, self.out_node, self.syscall))

class Graph:

    def __init__(self, nodes: Optional[Set[Node]] = None, edges: Optional[Set[Edge]] = None):
        self.nodes = set() if not nodes else nodes
        self.edges = set() if not edges else edges
        

    def add_node(self, node: Node) -> None:
        '''Adds the provided node into the collection of nodes in the graph, if it already exists then perform update if possible'''
        if node not in self.nodes:
            self.nodes.add(node)
    
    def add_edge(self, edge: Edge) -> None:
        '''
        Adds the provided edge into the collection of edges in the graph
        If one of in-node or out-node is not part of the graph, we add it into the graph as well
        '''
        
        self.add_node(edge.in_node)
        
        self.add_node(edge.out_node)
        
        self.edges.add(edge)


    def render(self, output_name="prov"):
        '''
        Generates a DOT graph visualization.
        '''
        dot = graphviz.Digraph(
            format='png', 
            graph_attr={
                'rankdir': 'TB',      
                'concentrate': 'true',
                'nodesep': '0.3',     
                'ranksep': '0.5',   
                'splines': 'line',  
                'overlap': 'false',   
                'fontname': 'Arial' 
            },
            node_attr={
                'shape': 'box',
                'style': 'rounded,filled',
                'fontname': 'Arial',
                'margin': '0.2,0.1'
            },
            edge_attr={
                'fontname': 'Arial',
                'fontsize': '10'
            }
        )

        # Process nodes with distinct styling
        for n in self.nodes:
            if isinstance(n, Process):
                attrs = {
                    'label': f"Process {n.pid}",
                    'git_hash': str(n.git_hash),
                    'fillcolor': "#C7E0F8",  # Light blue
                    'tooltip': f"PID: {n.pid}, Git: {n.git_hash}"
                }
                print(f"Node Added: {n.pid, n.git_hash}")
                dot.node(str(n.pid), **attrs)
            elif isinstance(n, File):
                attrs = {
                    'label': n.filename,
                    'git_hash': str(n.git_hash),
                    'fillcolor': "#F4F8CB",  # Light yellow
                    'tooltip': f"File: {n.filename}, Git: {n.git_hash}"
                }
                print(f"Node Added: {n.filename, n.git_hash}")
                dot.node(n.filename, **attrs)

        # Add edges with improved styling
        for e in self.edges:
            in_node_name = str(e.in_node.pid) if isinstance(e.in_node, Process) else e.in_node.filename
            out_node_name = str(e.out_node.pid) if isinstance(e.out_node, Process) else e.out_node.filename
            print(f"Edge Added: {in_node_name, out_node_name, e.syscall}")
            dot.edge(in_node_name, out_node_name, label=e.syscall)
            
        # Use dot layout engine for hierarchical layout
        dot.engine = 'dot'
        dot.unflatten(stagger=10)
        dot.render(output_name, format='png', cleanup=True)
        

    def get_adj_list(self) -> Dict:
        '''
        Returns an adjacency list with all the edges reversed
        '''
        res = {}
        for e in self.edges:
            if e.in_node in res:
                res[e.in_node].append(e.out_node)
            else:
                res[e.in_node] = [e.out_node]
        return res
    
class ProcessTrace(NamedTuple):
    parent_pid: int
    pid: int
    child_pid: int
    syscall: str

class FileOpenTrace(NamedTuple):
    pid: int
    filename: str
    syscall: str
    mode: int
    open_flag: str

class FileExecutionTrace(NamedTuple):
    pid: int
    filename: str
    syscall:str


