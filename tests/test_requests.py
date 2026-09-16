import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.database.models import NotificationDeliveryStatus, RequestStatus
from app.services.requests import RequestService


def test_request_stats_include_workflow_and_delivery_counts():
    async def run_check():
        request_rows = [
            (RequestStatus.NEW.value, 2),
            (RequestStatus.IN_PROGRESS.value, 1),
            (RequestStatus.DONE.value, 3),
            (RequestStatus.REJECTED.value, 1),
            (RequestStatus.CANCELLED.value, 1),
        ]
        delivery_rows = [
            (NotificationDeliveryStatus.PENDING.value, 2),
            (NotificationDeliveryStatus.PROCESSING.value, 1),
            (NotificationDeliveryStatus.FAILED.value, 4),
        ]
        session = SimpleNamespace(
            scalar=AsyncMock(side_effect=[5, 8]),
            execute=AsyncMock(
                side_effect=[
                    SimpleNamespace(all=lambda: request_rows),
                    SimpleNamespace(all=lambda: delivery_rows),
                ]
            ),
        )

        stats = await RequestService().get_stats(session)

        assert stats.new_requests == 2
        assert stats.in_progress_requests == 1
        assert stats.done_requests == 3
        assert stats.rejected_requests == 1
        assert stats.cancelled_requests == 1
        assert stats.pending_deliveries == 3
        assert stats.failed_deliveries == 4

    asyncio.run(run_check())
