from typing import Optional, Set
import graphviz

class Node(object):
    def __init__(self, git_hash: str):
        self.git_hash = git_hash

class Process(Node):
    def __init__(self, git_hash: str, pid: int, parent_pid: Optional[int] = None, child_pid: Optional[int] = None):
        super().__init__(git_hash)
        self.pid = pid
        self.parent_pid = parent_pid
        self.child_pid = child_pid
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
    
class Edge(object):
    def __init__(self, in_node: Node, out_node: Node, syscall: str):
        self.in_node = in_node
        self.out_node = out_node
        self.syscall = syscall
    
    def __eq__(self, other):
        return isinstance(other, Edge) and self.in_node == other.in_node and self.out_node == other.out_node and self.syscall == other.syscall
    
    def __hash__(self):
        return hash((self.in_node, self.out_node, self.syscall))

class Graph(object):

    def __init__(self, nodes: Optional[Set[Node]] = None, edges: Optional[Set[Edge]] = None):
        self.nodes = set() if not nodes else nodes
        self.edges = set() if not edges else edges
        

    def add_node(self, node: Node) -> None:
        '''Adds the provided node into the collection of nodes in the graph, if it already exists then perform update if possible'''
        if node not in self.nodes:
            self.nodes.add(node)
        else:
            # perform an update if the current supplied Process has more information
            node_in_set = next(iter(self.nodes & {node}))
            if node_in_set and isinstance(node_in_set, Process) and isinstance(node, Process):
                if not node_in_set.parent_pid and node.parent_pid:
                    node_in_set.parent_pid = node.parent_pid
                if not node_in_set.child_pid and node.child_pid:
                    node_in_set.child_pid = node.child_pid
    

    def add_edge(self, edge: Edge) -> None:
        '''
        Adds the provided edge into the collection of edges in the graph
        If one of in-node or out-node is not part of the graph, we add it into the graph as well
        '''
        
        self.add_node(edge.in_node)
        
        self.add_node(edge.out_node)
        
        self.edges.add(edge)


    def generate_dot(self):
        '''
        Generates a dot file for this graph?
        '''
        dot = graphviz.Digraph()

        for n in self.nodes:
            if isinstance(n, Process):
                # Convert all attributes to strings and handle None values
                attrs = {
                    'label': str(n.pid),
                    'git_hash': str(n.git_hash),
                    'parent_pid': str(n.parent_pid) if n.parent_pid is not None else "",
                    'child_pid': str(n.child_pid) if n.child_pid is not None else ""
                }
                print(f"Node Added: {n.pid, n.git_hash}")
                dot.node(str(n.pid), **attrs)
            elif isinstance(n, File):
                print(f"Node Added: {n.filename, n.git_hash}")
                dot.node(n.filename, n.filename, git_hash=str(n.git_hash))

        for e in self.edges:
            in_node_name = str(e.in_node.pid) if isinstance(e.in_node, Process) else e.in_node.filename
            out_node_name = str(e.out_node.pid) if isinstance(e.out_node, Process) else e.out_node.filename
            print(f"Edge Added: {in_node_name, out_node_name, e.syscall}")
            dot.edge(in_node_name, out_node_name, e.syscall)
        
        dot.render("prov", format='png', cleanup=True)
    

