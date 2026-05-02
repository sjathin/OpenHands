"""Tests for the personal skills repo service."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from openhands.server.personal_skills_repo import (
    get_skills_dir_from_repo,
    resolve_repo_commit,
)
from openhands.storage.data_models.settings import Settings


class TestResolveRepoCommit:
    def test_resolve_success(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'abc123def456\tHEAD\n'

        with patch('subprocess.run', return_value=mock_result):
            commit = resolve_repo_commit('https://github.com/user/repo')
            assert commit == 'abc123def456'

    def test_resolve_failure(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = 'fatal: not found'

        with patch('subprocess.run', return_value=mock_result):
            with pytest.raises(ValueError, match='Failed to resolve repo'):
                resolve_repo_commit('https://github.com/user/nonexistent')

    def test_resolve_empty_output(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ''

        with patch('subprocess.run', return_value=mock_result):
            with pytest.raises(ValueError, match='No HEAD ref found'):
                resolve_repo_commit('https://github.com/user/empty')


class TestGetSkillsDirFromRepo:
    def test_openhands_microagents_dir(self, tmp_path):
        (tmp_path / '.openhands' / 'microagents').mkdir(parents=True)
        assert (
            get_skills_dir_from_repo(tmp_path)
            == tmp_path / '.openhands' / 'microagents'
        )

    def test_skills_dir(self, tmp_path):
        (tmp_path / 'skills').mkdir()
        assert get_skills_dir_from_repo(tmp_path) == tmp_path / 'skills'

    def test_agents_skills_dir(self, tmp_path):
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        assert get_skills_dir_from_repo(tmp_path) == tmp_path / '.agents' / 'skills'

    def test_fallback_to_root_with_md_files(self, tmp_path):
        (tmp_path / 'my-skill.md').write_text('# Skill')
        assert get_skills_dir_from_repo(tmp_path) == tmp_path

    def test_no_skills_dir(self, tmp_path):
        assert get_skills_dir_from_repo(tmp_path) is None


class TestSettingsPersonalSkillsRepoFields:
    def test_default_values(self):
        s = Settings()
        assert s.personal_skills_repo_url is None
        assert s.personal_skills_repo_commit is None
        assert s.personal_skills_repo_updated_at is None

    def test_set_values(self):
        now = datetime.now(timezone.utc)
        s = Settings(
            personal_skills_repo_url='https://github.com/user/skills',
            personal_skills_repo_commit='abc123',
            personal_skills_repo_updated_at=now,
        )
        assert s.personal_skills_repo_url == 'https://github.com/user/skills'
        assert s.personal_skills_repo_commit == 'abc123'

    def test_serialization_roundtrip(self):
        now = datetime.now(timezone.utc)
        s = Settings(
            personal_skills_repo_url='https://github.com/user/skills',
            personal_skills_repo_commit='abc123',
            personal_skills_repo_updated_at=now,
        )
        restored = Settings.model_validate(s.model_dump(mode='json'))
        assert restored.personal_skills_repo_url == s.personal_skills_repo_url
        assert restored.personal_skills_repo_commit == s.personal_skills_repo_commit
