from .microagent import (
    BaseMicroagent,
    KnowledgeMicroagent,
    RepoMicroagent,
    load_microagents_from_dir,
)
from .types import MicroagentMetadata, MicroagentType


def collect_dependency_repos(microagents: list[BaseMicroagent]) -> list[str]:
    """Collect unique dependency_repos from all microagents."""
    seen: set[str] = set()
    repos: list[str] = []
    for agent in microagents:
        for repo in agent.metadata.dependency_repos:
            if repo not in seen:
                seen.add(repo)
                repos.append(repo)
    return repos


__all__ = [
    'BaseMicroagent',
    'KnowledgeMicroagent',
    'RepoMicroagent',
    'MicroagentMetadata',
    'MicroagentType',
    'collect_dependency_repos',
    'load_microagents_from_dir',
]
