import subprocess
from pathlib import Path

def get_latest_commit_for_file(filename: str) -> str:
    try:
        git_hash = subprocess.check_output(
            ["git", "log", "-n", "1", "--pretty=format:%H", "--", filename],
            text=True
        ).strip()
        if not git_hash:
            raise ValueError(f"No commit history for {filename}")
        return git_hash
    except:
        raise ValueError(f"Error retrieving git history for {filename}")

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
    if not git_hash: return True

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
    


