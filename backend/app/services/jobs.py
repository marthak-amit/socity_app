"""In-process periodic jobs (expire pending orders, send event reminders). Idempotent and safe to
run on several workers: each job claims rows atomically."""

import asyncio
import logging

log = logging.getLogger("societypass.jobs")


async def _loop(name: str, fn, interval: int):
    await asyncio.sleep(5)
    while True:
        try:
            await fn()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("job %s failed", name)
        await asyncio.sleep(interval)


def start_background_jobs() -> list[asyncio.Task]:
    from app.services.orders import expire_pending_orders
    from app.services.reminders import send_event_reminders

    return [
        asyncio.create_task(_loop("expire_orders", expire_pending_orders, 300)),
        asyncio.create_task(_loop("event_reminders", send_event_reminders, 900)),
    ]
