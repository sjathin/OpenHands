"""Service for resolving and cloning personal skills repositories.

Handles resolving a repo URL to a commit hash and cloning the repo
at a pinned commit for skill loading.
"""

import logging
import shutil
import subprocess
from pathlib import Path

_logger = logging.getLogger(__name__)

PERSONAL_SKILLS_CACHE_DIR = Path.home() / '.openhands' / 'personal_skills_repo'


def _normalize_clone_url(url: str) -> str:
    """Ensure URL ends with .git for cloning."""
    url = url.strip().rstrip('/')
    return url if url.endswith('.git') else url + '.git'


def resolve_repo_commit(repo_url: str, token: str | None = None) -> str:
    """Resolve a git repo URL to its current HEAD commit hash.

    Args:
        repo_url: Git repository URL (HTTPS).
        token: Optional auth token for private repos.

    Returns:
        The full SHA-1 commit hash of HEAD.

    Raises:
        ValueError: If the repo URL cannot be resolved.
    """
    clone_url = _inject_token(_normalize_clone_url(repo_url), token)
    try:
        result = subprocess.run(
            ['git', 'ls-remote', clone_url, 'HEAD'],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise ValueError(f'Failed to resolve repo: {result.stderr.strip()}')
        output = result.stdout.strip()
        if not output:
            raise ValueError(f'No HEAD ref found for repo {repo_url}')
        return output.split()[0]
    except subprocess.TimeoutExpired:
        raise ValueError(f'Timeout resolving repo {repo_url}')
    except FileNotFoundError:
        raise ValueError('git is not installed or not in PATH')


def _inject_token(clone_url: str, token: str | None) -> str:
    """Inject an auth token into an HTTPS git URL for private repo access."""
    if not token or not clone_url.startswith('https://'):
        return clone_url
    return clone_url.replace('https://', f'https://x-access-token:{token}@', 1)


def clone_repo_at_commit(repo_url: str, commit: str, token: str | None = None) -> Path:
    """Clone a repo at a specific commit into the personal skills cache.

    If the cache already has the correct commit checked out, this is a no-op.

    Args:
        repo_url: Git repository URL.
        commit: Full commit hash to checkout.
        token: Optional auth token for private repos.

    Returns:
        Path to the cloned repo directory.

    Raises:
        ValueError: If cloning or checkout fails.
    """
    cache_dir = PERSONAL_SKILLS_CACHE_DIR
    clone_url = _inject_token(_normalize_clone_url(repo_url), token)

    # Check if already at the right commit
    if cache_dir.exists():
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                cwd=cache_dir,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip() == commit:
                return cache_dir
        except Exception:
            pass
        shutil.rmtree(cache_dir, ignore_errors=True)

    cache_dir.parent.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            ['git', 'clone', '--no-checkout', clone_url, str(cache_dir)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise ValueError(f'Clone failed: {result.stderr.strip()}')
        result = subprocess.run(
            ['git', 'checkout', commit],
            capture_output=True,
            text=True,
            cwd=cache_dir,
            timeout=30,
        )
        if result.returncode != 0:
            raise ValueError(f'Checkout failed: {result.stderr.strip()}')
        return cache_dir
    except subprocess.TimeoutExpired:
        shutil.rmtree(cache_dir, ignore_errors=True)
        raise ValueError(f'Timeout cloning repo {repo_url}')
    except Exception as e:
        shutil.rmtree(cache_dir, ignore_errors=True)
        raise ValueError(f'Failed to clone repo {repo_url}: {e}')


def get_skills_dir_from_repo(repo_dir: Path) -> Path | None:
    """Find the skills/microagents directory inside a cloned repo.

    Looks for common conventions:
    - .openhands/microagents/
    - skills/
    - .agents/skills/
    - Root if it contains .md files

    Returns:
        Path to the skills directory, or None if not found.
    """
    candidates = [
        repo_dir / '.openhands' / 'microagents',
        repo_dir / 'skills',
        repo_dir / '.agents' / 'skills',
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    md_files = list(repo_dir.glob('*.md'))
    if md_files:
        return repo_dir
    return None
