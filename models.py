from typing import Optional, Set

class Node(object):
    def __init__(self, git_hash: Optional[str]):
        self.git_hash = git_hash

class Process(Node):
    def __init__(self, git_hash: Optional[str], pid: int, parent_pid: Optional[int], child_pid: Optional[int]):
        super.__init__(git_hash)
        self.pid = pid
        self.parent = parent_pid
        self.child = child_pid
    
    def __eq__(self, other):
        return isinstance(other, Process) and self.git_hash == other.git_hash and self.pid == other.pid and self.parent == other.parent and self.child == other.child
    
    def __hash__(self):
        return hash(self.git_hash, self.pid, self.parent, self.child)

class File(Node):
    def __init__(self, git_hash: Optional[str], filename: str):
        super.__init__(git_hash)
        self.filename = filename

    def __eq__(self, other):
        return isinstance(other, File) and self.git_hash == other.git_hash and self.filename == other.filename
    
    def __hash__(self):
        return hash(self.git_hash, self.filename)
    
class Edge(object):
    def __init__(self, in_node: Node, out_node: Node, syscall: str):
        self.in_node = in_node
        self.out_node = out_node
        self.syscall = syscall
    
    def __eq__(self, other):
        return isinstance(other, Edge) and self.in_node == other.in_node and self.out_node == other.out_node and self.syscall == other.syscall
    
    def __hash__(self):
        return hash(self.in_node, self.out_node, self.syscall)

class Graph(object):

    def __init__(self, nodes: Set[Node], edges: Set[Edge]):
        self.nodes = nodes
        self.edges = edges
        # create adjacency list?

    def generate_dot(self):
        pass

