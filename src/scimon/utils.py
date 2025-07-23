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
    except Exception as e:
        if isinstance(e, ValueError) and "No commit history" in str(e):
            raise
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

    change_list = subprocess.run(
        ["git", "log", "--pretty=format:%H", "--", filename],
        capture_output=True,
        text=True,
        check=True
    ).stdout.splitlines()

    return git_hash in change_list
    

def is_ancestor(commit1: str, commit2: str) -> bool:
    '''
    Given an 2 commits, return True if commit1 is an ancestor of commit2 else False
    '''
    try:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit1, commit2],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False
        )
        return result.returncode == 0
    except subprocess.CalledProcessError:
        print(f"Error checking commit ancestry for {commit1} {commit2}")
        return False




def get_closest_ancestor_hash(filename: str, git_hash: str) -> str:
    '''
    Given a filename and git_hash, return the hash that last changed the file which is right before the provided hash
    '''
    print(f"Locating closest commit for {filename} that is right before the commit {git_hash}")
    # get a list of git-hashes that changed the supplied file
    change_list = subprocess.run(
        ["git", "log", "--pretty=format:%H", "--", filename],
        capture_output=True,
        text=True,
        check=True
    ).stdout.splitlines()
    
    # loop through the hashes
    for i in range(len(change_list)):
        # if current hash is before the specified git_hash and the previous one wasn't, then return it
        if is_ancestor(change_list[i], git_hash):
            return change_list[i]
    raise ValueError("Provided git_hash is invalid")