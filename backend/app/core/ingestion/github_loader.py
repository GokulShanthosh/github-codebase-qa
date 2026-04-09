"""
GitHub Loader — fetches source files from a GitHub repository.

WHY THIS EXISTS:
We need raw source code from a GitHub repo to feed into the chunker.
This module handles all GitHub API interaction in one place — authentication,
rate limit awareness, file filtering, and content decoding.
"""
import base64
from dataclasses import dataclass
from github import Github, GithubException
from app.core.config import settings


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SourceFile:
    """Raw source file fetched from GitHub, ready to be chunked."""
    repo_name: str    # e.g. "owner/repo"
    file_path: str    # e.g. "services/payment.py"
    language: str     # e.g. "python"
    content: str      # raw source code as string


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# WHY: We only process languages tree-sitter can parse.
# Everything else (markdown, images, configs) is noise — skip it.
SUPPORTED_EXTENSIONS = {
    ".py":   "python",
    ".js":   "javascript",
    ".java": "java",
}

# WHY: These directories never contain meaningful application logic.
# Ingesting them wastes API calls, storage, and degrades retrieval quality.
SKIP_PREFIXES = (
    "node_modules/",
    ".git/",
    "dist/",
    "build/",
    "__pycache__/",
    ".venv/",
    "venv/",
    "migrations/",
)

# WHY: Files larger than 100KB are usually generated, minified, or data files.
# They produce poor chunks and slow down ingestion significantly.
MAX_FILE_SIZE_BYTES = 100_000


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_repo_url(url: str) -> str:
    """
    Extract 'owner/repo' from a GitHub URL.
    e.g. 'https://github.com/tiangolo/fastapi' → 'tiangolo/fastapi'
    """
    # Remove trailing slash if present
    url = url.rstrip("/")
    # Take the last two path segments
    parts = url.split("/")
    if len(parts) < 2:
        raise ValueError(f"Invalid GitHub URL: {url}")
    return f"{parts[-2]}/{parts[-1]}"


def load_repo(repo_url: str) -> tuple[list[SourceFile], str]:
    """
    Fetch all parseable source files from a GitHub repo.

    Returns:
        - list of SourceFile objects
        - latest commit SHA (used for incremental ingestion tracking)

    WHY return the SHA: We store it in the DB after ingestion so next time
    we can compare and only re-ingest files that changed.
    """
    owner_repo = parse_repo_url(repo_url)
    g = Github(settings.github_token)

    try:
        repo = g.get_repo(owner_repo)
    except GithubException as e:
        raise ValueError(f"Could not access repo '{owner_repo}': {e.data.get('message', str(e))}")

    # Get the latest commit SHA on the default branch
    # WHY: We store this SHA to enable incremental ingestion later
    latest_sha = repo.get_branch(repo.default_branch).commit.sha

    # ONE API CALL: get the full file tree recursively
    # This avoids making one API call per directory
    tree = repo.get_git_tree(latest_sha, recursive=True)

    files: list[SourceFile] = []

    for item in tree.tree:
        # Skip directories — we only want files (blobs)
        if item.type != "blob":
            continue

        path = item.path

        # Skip noise directories
        if any(path.startswith(skip) for skip in SKIP_PREFIXES):
            continue

        # Check if the file extension is one we support
        extension = "." + path.rsplit(".", 1)[-1] if "." in path else ""
        language = SUPPORTED_EXTENSIONS.get(extension)
        if not language:
            continue

        # Skip oversized files
        if item.size and item.size > MAX_FILE_SIZE_BYTES:
            continue

        # Fetch file content — this is one API call per file
        try:
            blob = repo.get_git_blob(item.sha)
            # WHY base64: GitHub API returns file content as base64 encoded string
            content = base64.b64decode(blob.content).decode("utf-8", errors="ignore")
        except GithubException:
            # Skip files that fail to fetch — don't let one bad file stop ingestion
            continue

        files.append(SourceFile(
            repo_name=owner_repo,
            file_path=path,
            language=language,
            content=content,
        ))

    return files, latest_sha


def get_changed_files(repo_url: str, old_sha: str, new_sha: str) -> dict[str, str]:
    """
    Get files that changed between two commits.
    Used for incremental ingestion — only re-process what actually changed.

    Returns a dict of {file_path: status}
    where status is one of: 'added', 'modified', 'removed'
    """
    owner_repo = parse_repo_url(repo_url)
    g = Github(settings.github_token)
    repo = g.get_repo(owner_repo)

    # WHY compare: GitHub's compare endpoint gives us exactly the diff
    # between two SHAs — which files changed and how
    comparison = repo.compare(old_sha, new_sha)

    changed = {}
    for f in comparison.files:
        if f.status == "renamed":
            # WHY split into two ops: a rename = delete old path + add new path.
            # If we don't delete the old path, stale chunks stay in the DB forever.
            # GitHub gives us both names on the same file object.
            old_ext = "." + f.previous_filename.rsplit(".", 1)[-1] if "." in f.previous_filename else ""
            new_ext = "." + f.filename.rsplit(".", 1)[-1] if "." in f.filename else ""
            if old_ext in SUPPORTED_EXTENSIONS:
                changed[f.previous_filename] = "removed"
            if new_ext in SUPPORTED_EXTENSIONS:
                changed[f.filename] = "added"
            continue

        extension = "." + f.filename.rsplit(".", 1)[-1] if "." in f.filename else ""
        if extension not in SUPPORTED_EXTENSIONS:
            continue
        if any(f.filename.startswith(skip) for skip in SKIP_PREFIXES):
            continue
        changed[f.filename] = f.status  # 'added', 'modified', 'removed'

    return changed
