from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from openhands.server.routes.manage_conversations import (
    BulkDeleteRequest,
    _try_delete_v1_conversation,
    bulk_delete_conversations,
)


@pytest.mark.asyncio
async def test_try_delete_v1_returns_sandbox_id_on_success():
    """Test that _try_delete_v1_conversation returns (result, sandbox_id) for V1 conversations."""
    conv_uuid = uuid4()
    sandbox_id = "sandbox-abc"

    info = MagicMock()
    info.id = conv_uuid
    info.sandbox_id = sandbox_id

    app_conversation_info_service = AsyncMock()
    app_conversation_info_service.get_app_conversation_info.return_value = info
    app_conversation_info_service.count_conversations_by_sandbox_id.return_value = 1

    app_conversation_service = AsyncMock()
    app_conversation_service.delete_app_conversation.return_value = True

    result, returned_sandbox_id = await _try_delete_v1_conversation(
        conv_uuid.hex,
        app_conversation_service,
        app_conversation_info_service,
        AsyncMock(),  # sandbox_service
        AsyncMock(),  # db_session
        AsyncMock(),  # httpx_client
        defer_sandbox_cleanup=True,
    )

    assert result is True
    assert returned_sandbox_id == sandbox_id
    app_conversation_service.delete_app_conversation.assert_called_once_with(
        conv_uuid, skip_agent_server_delete=False
    )


@pytest.mark.asyncio
async def test_try_delete_v1_returns_none_for_non_v1():
    """Test that _try_delete_v1_conversation returns (None, None) for non-V1 conversations."""
    app_conversation_info_service = AsyncMock()
    app_conversation_info_service.get_app_conversation_info.return_value = None

    result, sandbox_id = await _try_delete_v1_conversation(
        "not-a-uuid",
        AsyncMock(),
        app_conversation_info_service,
        AsyncMock(),
        AsyncMock(),
        AsyncMock(),
    )

    assert result is None
    assert sandbox_id is None


@pytest.mark.asyncio
async def test_bulk_delete_schedules_sandbox_cleanup():
    """Test that bulk_delete_conversations collects sandbox IDs and schedules cleanup."""
    conv1 = uuid4()
    conv2 = uuid4()
    sandbox_id = "sandbox-xyz"

    with (
        patch(
            "openhands.server.routes.manage_conversations._try_delete_v1_conversation",
            new_callable=AsyncMock,
            side_effect=[
                (True, sandbox_id),  # conv1: V1 with sandbox
                (None, None),  # conv2: not V1
            ],
        ),
        patch(
            "openhands.server.routes.manage_conversations._delete_v0_conversation",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch("openhands.server.routes.manage_conversations.asyncio") as mock_asyncio,
    ):
        body = BulkDeleteRequest(conversation_ids=[conv1.hex, conv2.hex])
        result = await bulk_delete_conversations(
            body=body,
            user_id="user-1",
            app_conversation_service=AsyncMock(),
            app_conversation_info_service=AsyncMock(),
            sandbox_service=AsyncMock(),
            db_session=AsyncMock(),
            httpx_client=AsyncMock(),
        )

    assert conv1.hex in result.succeeded
    assert conv2.hex in result.succeeded
    assert len(result.failed) == 0
    mock_asyncio.create_task.assert_called_once()


@pytest.mark.asyncio
async def test_bulk_delete_skips_cleanup_when_no_v1_sandboxes():
    """Test that bulk_delete_conversations does not schedule cleanup for V0-only deletes."""
    with (
        patch(
            "openhands.server.routes.manage_conversations._try_delete_v1_conversation",
            new_callable=AsyncMock,
            return_value=(None, None),
        ),
        patch(
            "openhands.server.routes.manage_conversations._delete_v0_conversation",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch("openhands.server.routes.manage_conversations.asyncio") as mock_asyncio,
    ):
        body = BulkDeleteRequest(conversation_ids=["abc123"])
        result = await bulk_delete_conversations(
            body=body,
            user_id="user-1",
            app_conversation_service=AsyncMock(),
            app_conversation_info_service=AsyncMock(),
            sandbox_service=AsyncMock(),
            db_session=AsyncMock(),
            httpx_client=AsyncMock(),
        )

    assert result.succeeded == ["abc123"]
    mock_asyncio.create_task.assert_not_called()


@pytest.mark.asyncio
async def test_bulk_delete_reports_failures_on_exception():
    """Test that bulk_delete_conversations catches exceptions and reports them as failures."""
    with (
        patch(
            "openhands.server.routes.manage_conversations._try_delete_v1_conversation",
            new_callable=AsyncMock,
            side_effect=Exception("boom"),
        ),
        patch("openhands.server.routes.manage_conversations.asyncio"),
    ):
        body = BulkDeleteRequest(conversation_ids=["fail-id"])
        result = await bulk_delete_conversations(
            body=body,
            user_id="user-1",
            app_conversation_service=AsyncMock(),
            app_conversation_info_service=AsyncMock(),
            sandbox_service=AsyncMock(),
            db_session=AsyncMock(),
            httpx_client=AsyncMock(),
        )

    assert result.succeeded == []
    assert result.failed == ["fail-id"]
