import os
import sys
import pytest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

# Import the modules to test
from scimon.scimon import (
    get_trace_data,
    build_process_nodes_and_edges,
    build_file_read_write_nodes_and_edges,
    build_file_execution_nodes_and_edges,
    generate_graph,
    reproduce,
    MAKE_FILE_RULE_TEMPLATE,
    MAKE_FILE_NAME
)
from scimon.models import Graph, Process, File, Edge, ProcessTrace, FileOpenTrace, FileExecutionTrace

class TestGetTraceData:
    """Tests for the get_trace_data function."""

    @patch('scimon.scimon.get_processes_trace')
    @patch('scimon.scimon.get_opened_files_trace')
    @patch('scimon.scimon.get_executed_files_trace')
    def test_get_trace_data(self, mock_executed, mock_opened, mock_processes):
        """Test that get_trace_data calls the correct functions and returns expected results."""
        # Setup mock returns
        git_hash = "abc123"
        db_mock = MagicMock()
        
        # Create mock data
        process_traces = [ProcessTrace(1, 2, 3, "fork")]
        open_file_traces = [FileOpenTrace(2, "file.txt", "open", 0, "O_RDONLY")]
        exec_file_traces = [FileExecutionTrace(2, "script.py", "execve")]
        
        # Configure mocks
        mock_processes.return_value = process_traces
        mock_opened.return_value = open_file_traces
        mock_executed.return_value = exec_file_traces
        
        # Call the function
        result = get_trace_data(git_hash, db_mock)
        
        # Verify results
        mock_processes.assert_called_once_with(git_hash, db_mock)
        mock_opened.assert_called_once_with(git_hash, db_mock)
        mock_executed.assert_called_once_with(git_hash, db_mock)
        
        assert result == (process_traces, open_file_traces, exec_file_traces)
        assert len(result) == 3
        assert result[0] == process_traces
        assert result[1] == open_file_traces
        assert result[2] == exec_file_traces


class TestBuildProcessNodesAndEdges:
    """Tests for the build_process_nodes_and_edges function."""
    
    def test_build_process_nodes_and_edges_with_parent(self):
        """Test building process nodes and edges when parent_pid is provided."""
        # Setup
        graph = Graph()
        git_hash = "abc123"
        
        # Create a process trace with parent_pid
        process_trace = ProcessTrace(parent_pid=1, pid=2, child_pid=3, syscall="fork")
        processes_trace = [process_trace]
        
        # Call the function
        build_process_nodes_and_edges(graph, processes_trace, git_hash)
        
        # Verify results
        assert len(graph.nodes) == 3  # Parent, process, and child
        assert len(graph.edges) == 2  # Parent->Process and Process->Child

        # Check that the nodes exist
        parent_node = Process(git_hash=git_hash, pid=1)
        process_node = Process(git_hash=git_hash, pid=2)
        child_node = Process(git_hash=git_hash, pid=3)
        
        assert parent_node in graph.nodes
        assert process_node in graph.nodes
        assert child_node in graph.nodes
        
        # Check that the edges exist
        parent_edge = Edge(parent_node, process_node, "fork")
        child_edge = Edge(process_node, child_node, "fork")
        
        assert parent_edge in graph.edges
        assert child_edge in graph.edges
    
    def test_build_process_nodes_and_edges_without_parent(self):
        """Test building process nodes and edges when parent_pid is None."""
        # Setup
        graph = Graph()
        git_hash = "abc123"
        
        # Create a process trace without parent_pid
        process_trace = ProcessTrace(parent_pid=None, pid=2, child_pid=3, syscall="fork")
        processes_trace = [process_trace]
        
        # Call the function
        build_process_nodes_and_edges(graph, processes_trace, git_hash)
        
        # Verify results
        assert len(graph.nodes) == 2  # Just process and child
        assert len(graph.edges) == 1  # Just Process->Child

        # Check that the nodes exist
        process_node = Process(git_hash=git_hash, pid=2)
        child_node = Process(git_hash=git_hash, pid=3)
        
        assert process_node in graph.nodes
        assert child_node in graph.nodes
        
        # Check that the edges exist
        child_edge = Edge(process_node, child_node, "fork")
        
        assert child_edge in graph.edges


class TestBuildFileReadWriteNodesAndEdges:
    """Tests for the build_file_read_write_nodes_and_edges function."""
    
    @patch('scimon.scimon.is_file_tracked_by_git')
    @patch('scimon.scimon.os.path.isdir')
    def test_build_file_read_write_nodes_edges_read_mode(self, mock_isdir, mock_is_tracked):
        """Test building file nodes and edges with read-only mode."""
        # Setup
        graph = Graph()
        git_hash = "abc123"
        
        # Configure mocks
        mock_is_tracked.return_value = True
        mock_isdir.return_value = False
        
        # Create a file trace with read mode
        file_trace = FileOpenTrace(pid=100, filename="test_file.txt", syscall="open", mode=0, open_flag="O_RDONLY")
        file_traces = [file_trace]
        
        # Call the function
        build_file_read_write_nodes_and_edges(graph, file_traces, git_hash)
        
        # Verify results
        assert len(graph.nodes) == 2  # Process and file
        assert len(graph.edges) == 1  # Process->File (read direction)
        
        # Check nodes
        process_node = Process(git_hash=git_hash, pid=100)
        file_node = File(git_hash=git_hash, filename="test_file.txt")
        
        assert process_node in graph.nodes
        assert file_node in graph.nodes
        
        # Check edge - should be process to file for read
        edge = Edge(process_node, file_node, "open")
        assert edge in graph.edges
    
    @patch('scimon.scimon.is_file_tracked_by_git')
    @patch('scimon.scimon.os.path.isdir')
    def test_build_file_read_write_nodes_edges_write_mode(self, mock_isdir, mock_is_tracked):
        """Test building file nodes and edges with write mode."""
        # Setup
        graph = Graph()
        git_hash = "abc123"
        
        # Configure mocks
        mock_is_tracked.return_value = True
        mock_isdir.return_value = False
        
        # Create a file trace with write mode
        file_trace = FileOpenTrace(pid=100, filename="output.txt", syscall="open", mode=0, open_flag="O_WRONLY")
        file_traces = [file_trace]
        
        # Call the function
        build_file_read_write_nodes_and_edges(graph, file_traces, git_hash)
        
        # Verify results
        assert len(graph.nodes) == 2  # Process and file
        assert len(graph.edges) == 1  # File->Process (write direction)
        
        # Check nodes
        process_node = Process(git_hash=git_hash, pid=100)
        file_node = File(git_hash=git_hash, filename="output.txt")
        
        assert process_node in graph.nodes
        assert file_node in graph.nodes
        
        # Check edge - should be file to process for write
        edge = Edge(file_node, process_node, "open")
        assert edge in graph.edges
    
    @patch('scimon.scimon.is_file_tracked_by_git')
    @patch('scimon.scimon.os.path.isdir')
    def test_build_file_read_write_nodes_edges_ignored_files(self, mock_isdir, mock_is_tracked):
        """Test that files not tracked by git are ignored."""
        # Setup
        graph = Graph()
        git_hash = "abc123"
        
        # Configure mocks to ignore the file
        mock_is_tracked.return_value = False
        mock_isdir.return_value = False
        
        # Create a file trace
        file_trace = FileOpenTrace(pid=100, filename="ignored.txt", syscall="open", mode=0, open_flag="O_RDONLY")
        file_traces = [file_trace]
        
        # Call the function
        build_file_read_write_nodes_and_edges(graph, file_traces, git_hash)
        
        # Verify results - should be empty as file is ignored
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0
    
    @patch('scimon.scimon.is_file_tracked_by_git')
    @patch('scimon.scimon.os.path.isdir')
    def test_build_file_read_write_nodes_edges_directory(self, mock_isdir, mock_is_tracked):
        """Test that directories are ignored."""
        # Setup
        graph = Graph()
        git_hash = "abc123"
        
        # Configure mocks to treat as directory
        mock_is_tracked.return_value = True
        mock_isdir.return_value = True
        
        # Create a directory trace
        file_trace = FileOpenTrace(pid=100, filename="test_dir", syscall="open", mode=0, open_flag="O_RDONLY")
        file_traces = [file_trace]
        
        # Call the function
        build_file_read_write_nodes_and_edges(graph, file_traces, git_hash)
        
        # Verify results - should be empty as it's a directory
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0


class TestBuildFileExecutionNodesAndEdges:
    """Tests for the build_file_execution_nodes_and_edges function."""
    
    @patch('scimon.scimon.is_file_tracked_by_git')
    @patch('scimon.scimon.os.path.isdir')
    def test_build_file_execution_nodes_edges(self, mock_isdir, mock_is_tracked):
        """Test building file execution nodes and edges."""
        # Setup
        graph = Graph()
        git_hash = "abc123"
        
        # Configure mocks
        mock_is_tracked.return_value = True
        mock_isdir.return_value = False
        
        # Create a file execution trace
        file_trace = FileExecutionTrace(pid=100, filename="script.py", syscall="execve")
        file_traces = [file_trace]
        
        # Call the function
        build_file_execution_nodes_and_edges(graph, file_traces, git_hash)
        
        # Verify results
        assert len(graph.nodes) == 2  # Process and file
        assert len(graph.edges) == 1  # Process->File
        
        # Check nodes
        process_node = Process(git_hash=git_hash, pid=100)
        file_node = File(git_hash=git_hash, filename="script.py")
        
        assert process_node in graph.nodes
        assert file_node in graph.nodes
        
        # Check edge - should be process to file for execution
        edge = Edge(process_node, file_node, "execve")
        assert edge in graph.edges
    
    @patch('scimon.scimon.is_file_tracked_by_git')
    @patch('scimon.scimon.os.path.isdir')
    def test_build_file_execution_nodes_edges_ignored_files(self, mock_isdir, mock_is_tracked):
        """Test that files not tracked by git are ignored for execution."""
        # Setup
        graph = Graph()
        git_hash = "abc123"
        
        # Configure mocks to ignore the file
        mock_is_tracked.return_value = False
        mock_isdir.return_value = False
        
        # Create a file execution trace
        file_trace = FileExecutionTrace(pid=100, filename="ignored.py", syscall="execve")
        file_traces = [file_trace]
        
        # Call the function
        build_file_execution_nodes_and_edges(graph, file_traces, git_hash)
        
        # Verify results - should be empty as file is ignored
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0
    
    @patch('scimon.scimon.is_file_tracked_by_git')
    @patch('scimon.scimon.os.path.isdir')
    def test_build_file_execution_nodes_edges_directory(self, mock_isdir, mock_is_tracked):
        """Test that directories are ignored for execution."""
        # Setup
        graph = Graph()
        git_hash = "abc123"
        
        # Configure mocks to treat as directory
        mock_is_tracked.return_value = True
        mock_isdir.return_value = True
        
        # Create a directory execution trace
        file_trace = FileExecutionTrace(pid=100, filename="test_dir", syscall="execve")
        file_traces = [file_trace]
        
        # Call the function
        build_file_execution_nodes_and_edges(graph, file_traces, git_hash)
        
        # Verify results - should be empty as it's a directory
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0


class TestGenerateGraph:
    """Tests for the generate_graph function."""
    
    @patch('scimon.scimon.get_db')
    @patch('scimon.scimon.get_trace_data')
    @patch('scimon.scimon.build_process_nodes_and_edges')
    @patch('scimon.scimon.build_file_read_write_nodes_and_edges')
    @patch('scimon.scimon.build_file_execution_nodes_and_edges')
    def test_generate_graph(self, mock_build_exec, mock_build_rw, mock_build_proc, 
                           mock_get_trace, mock_get_db):
        """Test the graph generation function with all steps."""
        # Setup
        filename = "test_file.py"
        git_hash = "abc123"
        db_mock = MagicMock()
        mock_get_db.return_value = db_mock
        
        # Create mock data
        process_traces = [ProcessTrace(1, 2, 3, "fork")]
        open_file_traces = [FileOpenTrace(2, "file.txt", "open", 0, "O_RDONLY")]
        exec_file_traces = [FileExecutionTrace(2, "script.py", "execve")]
        
        # Configure mock to return trace data
        mock_get_trace.return_value = (process_traces, open_file_traces, exec_file_traces)
        
        # Call the function
        result = generate_graph(filename, git_hash)
        
        # Verify calls
        mock_get_db.assert_called_once()
        mock_get_trace.assert_called_once_with(git_hash, db_mock)
        mock_build_proc.assert_called_once_with(result, process_traces, git_hash)
        mock_build_rw.assert_called_once_with(result, open_file_traces, git_hash)
        mock_build_exec.assert_called_once_with(result, exec_file_traces, git_hash)
        
        # Check the result
        assert isinstance(result, Graph)


class TestReproduce:
    """Tests for the reproduce function."""
    
    @patch('scimon.scimon.is_file_tracked_by_git')
    @patch('scimon.scimon.is_git_hash_on_file')
    @patch('scimon.scimon.get_latest_commit_for_file')
    @patch('scimon.scimon.generate_graph')
    @patch('scimon.scimon.get_command')
    @patch('scimon.scimon.get_closest_ancestor_hash')
    @patch('scimon.scimon.os.path.isdir')
    @patch('builtins.open', new_callable=mock_open)
    def test_reproduce_file_no_dependencies(self, mock_file, mock_isdir, mock_get_closest, mock_get_command,
                                          mock_gen_graph, mock_get_latest, mock_is_hash_on, mock_is_tracked):
        """Test reproduce function for a file with no dependencies."""
        # Setup
        file = "simple.txt"
        git_hash = "abc123"
        
        # Configure mocks
        mock_isdir.return_value = False
        mock_is_tracked.return_value = True
        mock_is_hash_on.return_value = True
        mock_get_latest.return_value = git_hash
        
        # Create a graph without the file node in adjacency list
        graph_mock = MagicMock()
        graph_mock.get_adj_list.return_value = {}  # Empty adjacency list
        mock_gen_graph.return_value = graph_mock
        
        # Call the function
        reproduce(file, git_hash)
        
        # Verify file operations for Makefile
        mock_file.assert_called_once_with(MAKE_FILE_NAME, 'a')
        mock_file().write.assert_called_once()
        
        # Verify the rule template was used with correct parameters
        write_arg = mock_file().write.call_args[0][0]
        expected_rule = MAKE_FILE_RULE_TEMPLATE.render(
            target=file, 
            prerequisites="", 
            recipe=f"git restore --source={git_hash} -- {file}"
        )
        assert write_arg.strip() == expected_rule.strip()

    @patch('scimon.scimon.get_db')
    @patch('scimon.scimon.is_file_tracked_by_git')
    @patch('scimon.scimon.is_git_hash_on_file')
    @patch('scimon.scimon.get_latest_commit_for_file')
    @patch('scimon.scimon.generate_graph')
    @patch('scimon.scimon.get_command')
    @patch('scimon.scimon.get_closest_ancestor_hash')
    @patch('scimon.scimon.os.path.isdir')
    @patch('builtins.open', new_callable=mock_open)
    def test_reproduce_file_with_dependencies(self, mock_file, mock_isdir, mock_get_closest, mock_get_command,
                                            mock_gen_graph, mock_get_latest, mock_is_hash_on, mock_is_tracked, mock_db):
        """Test reproduce function for a file with dependencies."""
        # Setup
        file = "output.txt"
        git_hash = "abc123"
        command = "python process.py > output.txt"
        
        # Configure mocks
        mock_isdir.return_value = False
        mock_is_tracked.return_value = True
        mock_is_hash_on.return_value = True
        mock_get_latest.return_value = git_hash
        mock_get_command.return_value = command
        mock_get_closest.return_value = "def456"  # Different hash for dependency
        mock_db.return_value = None
        
        # Create a graph with dependencies
        graph_mock = MagicMock()
        file_node = File(git_hash, file)
        process_node = Process(git_hash, 100)
        dependency_file = File(git_hash, "process.py")
        
        # Create an adjacency list with the file node and its dependencies
        adj_list = {
            file_node: [process_node],
            process_node: [dependency_file]
        }
        graph_mock.get_adj_list.return_value = adj_list
        mock_gen_graph.return_value = graph_mock
        
        # Call the function
        reproduce(file, git_hash)
        
        # Verify the command was fetched
        mock_get_command.assert_called_once()
        
        # Verify file operations for Makefile
        mock_file.assert_called()
        
        # The exact assertions depend on the behavior of the DFS traversal
        # This would need to be adapted to the exact implementation
        # For now, verify the rule was generated with dependencies
        assert mock_file().write.call_count > 0
    
    @patch('scimon.scimon.is_file_tracked_by_git')
    @patch('scimon.scimon.os.path.isdir')
    def test_reproduce_directory(self, mock_isdir, mock_is_tracked):
        """Test reproduce function when given a directory."""
        # Setup
        directory = "test_dir"
        git_hash = "abc123"
        
        # Configure mocks
        mock_isdir.return_value = True
        
        # Call the function
        reproduce(directory, git_hash)
        
        # Verify it exits early without error
        mock_is_tracked.assert_not_called()  # Should exit before this call
    
    @patch('scimon.scimon.is_file_tracked_by_git')
    @patch('scimon.scimon.os.path.isdir')
    def test_reproduce_untracked_file(self, mock_isdir, mock_is_tracked):
        """Test reproduce function when given an untracked file."""
        # Setup
        file = "untracked.txt"
        git_hash = "abc123"
        
        # Configure mocks
        mock_isdir.return_value = False
        mock_is_tracked.return_value = False
        
        # Call the function
        reproduce(file, git_hash)
        
        # Verify it exits early with the appropriate message
        mock_is_tracked.assert_called_once()
    
    @patch('scimon.scimon.is_file_tracked_by_git')
    @patch('scimon.scimon.is_git_hash_on_file')
    @patch('scimon.scimon.os.path.isdir')
    def test_reproduce_hash_not_on_file(self, mock_isdir, mock_is_hash_on, mock_is_tracked):
        """Test reproduce function when hash doesn't match the file."""
        # Setup
        file = "test.txt"
        git_hash = "wronghash"
        
        # Configure mocks
        mock_isdir.return_value = False
        mock_is_tracked.return_value = True
        mock_is_hash_on.return_value = False
        
        # Call the function
        reproduce(file, git_hash)
        
        # Verify it exits early with the appropriate message
        mock_is_hash_on.assert_called_once_with(file, git_hash)


if __name__ == "__main__":
    pytest.main()