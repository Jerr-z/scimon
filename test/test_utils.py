import pytest 
import subprocess
from scimon import utils

def test_get_latest_commit_for_file_success(monkeypatch):
    mock_file = "foo.txt"
    mock_git_commit = "abcd1234"
    monkeypatch.setattr(
        utils.subprocess, "check_output",
        lambda *args, **kwargs: mock_git_commit
    )
    assert utils.get_latest_commit_for_file(mock_file) == mock_git_commit

def test_get_latest_commit_for_file_no_history(monkeypatch):
    mock_file = "foo.txt"
    monkeypatch.setattr(
        utils.subprocess, "check_output",
        lambda *args, **kwargs: ""
    )
    with pytest.raises(ValueError) as ei:
        utils.get_latest_commit_for_file(mock_file)
    assert f"No commit history for {mock_file}" in str(ei.value)

def test_get_latest_commit_for_file_git_throwing_error(monkeypatch):
    def throw(*args, **kwargs):
        raise Exception("git failed")
    
    mock_file = "foo.txt"
    monkeypatch.setattr(utils.subprocess, "check_output", throw)
    with pytest.raises(ValueError) as ei:
        utils.get_latest_commit_for_file(mock_file)
    assert f"Error retrieving git history for {mock_file}" in str(ei.value)

def test_is_file_tracked_by_git_true(monkeypatch):
    def true(cmd, capture_output, text, check):
        return subprocess.CompletedProcess(cmd, 0, stdout='', stderr='')
    
    mock_file = "foo.txt"
    monkeypatch.setattr(utils.subprocess, "run", true)
    assert utils.is_file_tracked_by_git(mock_file) is True

def test_is_file_tracked_by_git_false(monkeypatch):
    def throw(cmd, capture_output, text, check):
        raise subprocess.CalledProcessError(1, cmd)
    
    mock_file = "foo.txt"
    monkeypatch.setattr(utils.subprocess, "run", throw)
    assert utils.is_file_tracked_by_git(mock_file) is False

def test_is_git_hash_on_file_empty_hash(monkeypatch):
    assert utils.is_git_hash_on_file("foo.txt", "") is True

def test_is_git_hash_on_file_true(monkeypatch):
    mock_hash = "abcd1234"

    def git_log(cmd, capture_output, text, check):
        return subprocess.CompletedProcess(cmd, 0, stdout=mock_hash, stderr='')

    monkeypatch.setattr(utils.subprocess, "run", git_log)
    assert utils.is_git_hash_on_file("foo.txt", mock_hash) is True

def test_is_git_hash_on_file_false(monkeypatch):
    mock_hash = "abcd1234"

    def git_log(cmd, capture_output, text, check):
        return subprocess.CompletedProcess(cmd, 0, stdout=mock_hash, stderr='')

    monkeypatch.setattr(utils.subprocess, "run", git_log)
    assert utils.is_git_hash_on_file("foo.txt", "heheheha") is False

def test_is_ancestor_true(monkeypatch):
    mock_commit_1 = "abcd1234"
    mock_commit_2 = "defg5678"

    def git_merge_base(cmd, stdout, stderr, check):
        return subprocess.CompletedProcess(cmd, 0)
    
    monkeypatch.setattr(utils.subprocess, "run", git_merge_base)
    assert utils.is_ancestor(mock_commit_1, mock_commit_2) is True

def test_is_ancestor_false(monkeypatch):
    mock_commit_1 = "abcd1234"
    mock_commit_2 = "defg5678"

    def git_merge_base(cmd, stdout, stderr, check):
        return subprocess.CompletedProcess(cmd, 1)
    
    monkeypatch.setattr(utils.subprocess, "run", git_merge_base)
    assert utils.is_ancestor(mock_commit_1, mock_commit_2) is False

def test_is_ancestor_error(monkeypatch):
    mock_commit_1 = "abcd1234"
    mock_commit_2 = "defg5678"

    def throw(*args, **kwargs):
        raise subprocess.CalledProcessError(2, args[0])
    
    monkeypatch.setattr(utils.subprocess, "run", throw)

    assert utils.is_ancestor(mock_commit_1, mock_commit_2) is False
    
def test_get_closest_ancestor_hash_found(monkeypatch):
    mock_ancestor_hashes="abc\ndef\nghi\n"
    def git_log(cmd, capture_output, text, check):
        return subprocess.CompletedProcess(cmd, 0, stdout=mock_ancestor_hashes)
    
    monkeypatch.setattr(utils.subprocess, "run", git_log)
    monkeypatch.setattr(utils, "is_ancestor", lambda c1, c2: c1 == "def")
    
    assert utils.get_closest_ancestor_hash("foo.txt", "xyz") == "def"


def test_get_closest_ancestor_hash_invalid(monkeypatch):
    mock_ancestor_hashes="abc\ndef\nghi\n"
    def git_log(cmd, capture_output, text, check):
        return subprocess.CompletedProcess(cmd, 0, stdout=mock_ancestor_hashes)
    
    monkeypatch.setattr(utils.subprocess, "run", git_log)
    monkeypatch.setattr(utils, "is_ancestor", lambda c1, c2: False)
    
    with pytest.raises(ValueError) as ei:
        utils.get_closest_ancestor_hash("foo.txt", "xyz")
    
    assert "Provided git_hash is invalid" in str(ei.value)


