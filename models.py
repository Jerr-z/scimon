from typing import Optional, Set

class Node(object):
    def __init__(self, git_hash: str):
        self.git_hash = git_hash

class Process(Node):
    def __init__(self, git_hash: str, pid: int, parent_pid: Optional[int], child_pid: Optional[int]):
        super.__init__(git_hash)
        self.pid = pid
        self.parent_pid = parent_pid
        self.child_pid = child_pid
    def __eq__(self, other):
        return isinstance(other, Process) and self.git_hash == other.git_hash and self.pid == other.pid
    
    def __hash__(self):
        return hash(self.git_hash, self.pid, self.parent, self.child)

class File(Node):
    def __init__(self, git_hash: str, filename: str):
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

    def __init__(self, nodes: Optional[Set[Node]], edges: Optional[Set[Edge]]):
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
        # TODO
        pass
    

