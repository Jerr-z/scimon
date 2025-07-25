from typer.testing import CliRunner
import os
import subprocess
from pathlib import Path
from unittest.mock import patch, mock_open, call
import pytest
from scimon import __app_name__, __version__
from scimon.cli import app, MONITORED_DIR


runner = CliRunner()


def test_version():
    """Test that the version option displays the correct version and exits."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"{__app_name__} v{__version__}" in result.stdout

@patch("scimon.cli.r")
def test_reproduce(mock_reproduce):
    """Test the reproduce command invocation."""
    # Test without git hash
    result = runner.invoke(app, ["reproduce", "test.py"])
    assert result.exit_code == 0
    mock_reproduce.assert_called_once_with("test.py", None)
    
    # Test with git hash
    mock_reproduce.reset_mock()
    result = runner.invoke(app, ["reproduce", "test.py", "--git-hash", "abcdef"])
    assert result.exit_code == 0
    mock_reproduce.assert_called_once_with("test.py", "abcdef")

class TestInit:

    @patch("scimon.cli.Path")
    @patch("scimon.cli.os")
    @patch("scimon.cli.subprocess.run")
    @patch("scimon.cli.add_to_gitignore")
    @patch("scimon.cli.initialize_db")
    @patch("scimon.cli.open", new_callable=mock_open)
    def test_init_success(mock_file, mock_init_db, mock_add_gitignore, mock_run, mock_os, mock_path):
        """Test successful initialization with the init command."""
        # Setup mocks
        mock_os.getcwd.return_value = "/home/user/project"
        mock_os.path.expanduser.return_value = "/home/user"
        mock_path.return_value.is_relative_to.return_value = True
        mock_path.return_value.relative_to.return_value = Path("project")
        mock_file().readlines.return_value = []
        
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        
        mock_add_gitignore.assert_called_once_with(".db")
        mock_init_db.assert_called_once()
        assert mock_run.call_count == 3  # git init, git add, git commit
        mock_file.assert_any_call(MONITORED_DIR, "r")
        mock_file.assert_any_call(MONITORED_DIR, "a+")

    @patch("scimon.cli.Path")
    @patch("scimon.cli.os")
    @patch("scimon.cli.open", new_callable=mock_open)
    def test_init_already_monitored(mock_file, mock_os, mock_path):
        """Test init command when path is already monitored."""
        mock_os.getcwd.return_value = "/home/user/project"
        mock_os.path.expanduser.return_value = "/home/user"
        mock_path.return_value.is_relative_to.return_value = True
        mock_path.return_value.__eq__.return_value = True
        mock_file().readlines.return_value = ["project\n"]
        
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert "Path already monitored" in result.stdout

    @patch("scimon.cli.Path")
    @patch("scimon.cli.os")
    def test_init_not_in_home(mock_os, mock_path):
        """Test init command when path is not in user's home."""
        mock_path.return_value.is_relative_to.return_value = False
        
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert "not relative to the current user's HOME path" in result.stdout

class TestList:
    @patch("scimon.cli.Path")
    @patch("scimon.cli.open", new_callable=mock_open)
    def test_list_with_dirs(mock_file, mock_path):
        """Test list command when directories are being monitored."""
        mock_path.return_value.exists.return_value = True
        mock_file().readlines.return_value = ["path1\n", "path2\n"]
        
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "path1" in result.stdout
        assert "path2" in result.stdout

    @patch("scimon.cli.Path")
    @patch("scimon.cli.open", new_callable=mock_open)
    def test_list_no_dirs_file(mock_file, mock_path):
        """Test list command when dirs file doesn't exist."""
        mock_path.return_value.exists.return_value = False
        
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        mock_path.return_value.touch.assert_called_once()

@patch("scimon.cli.os")
@patch("scimon.cli.Path")
@patch("scimon.cli.open", new_callable=mock_open)
def test_remove_dir(mock_file, mock_path, mock_os):
    """Test remove command for directory removal."""
    mock_path.return_value.exists.return_value = True
    mock_file().readlines.return_value = ["project\n", "other\n"]
    
    # Configure mock Path to handle equality checks
    mock_path.side_effect = lambda x: x
    
    result = runner.invoke(app, ["remove", "project"])
    assert result.exit_code == 0
    assert "Directory successfully removed" in result.stdout

@patch("scimon.cli.os")
@patch("scimon.cli.open", new_callable=mock_open)
def test_setup(mock_file, mock_os):
    """Test setup command."""
    # Setup mocks
    mock_os.path.join.side_effect = lambda *args: "/".join(args)
    mock_os.path.dirname.return_value = "/path/to"
    mock_os.path.expanduser.return_value = "/home/user"
    mock_file().read.return_value = "# Existing content"
    
    result = runner.invoke(app, ["setup"])
    assert result.exit_code == 0
    assert "Bash hook installed" in result.stdout
    
    # Test when already installed
    mock_os.makedirs.side_effect = OSError
    script_content = '\n# Scimon command hooks\n[ -f "/path/to/commandhook.sh" ] && source "/path/to/commandhook.sh"\n'
    mock_file().read.return_value = f"# Existing content{script_content}"
    
    result = runner.invoke(app, ["setup"])
    assert result.exit_code == 0
    assert "Bash hook already installed" in result.stdout
    assert "App directory already exists" in result.stdout

if __name__ == "__main__":
    pytest.main()