import subprocess
from pathlib import Path

def is_file_tracked_by_git(filename: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", filename],
            capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError:
        return False
    return True

def is_git_hash_on_file(filename: str, git_hash: str) -> bool:
    changed_files = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", git_hash],
        capture_output=True,
        text=True,
        check=True
    ).stdout.splitlines()

    target = Path(filename).resolve()

    for changed in changed_files:
        file_path = Path(changed).resolve()
        if file_path == target:
            return True
    
    return False
    


