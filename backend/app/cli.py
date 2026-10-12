"""Ops CLI:  python -m app.cli create-superadmin +919800000000 | expire-orders | send-reminders"""

import asyncio
import sys

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.phone import normalize_phone
from app.models import User


async def create_superadmin(phone: str) -> None:
    phone = normalize_phone(phone)
    async with SessionLocal() as s:
        u = await s.scalar(select(User).where(User.phone == phone))
        if u is None:
            u = User(phone=phone, name="Platform Admin")
            s.add(u)
        u.is_super_admin = True
        await s.commit()
    print(f"super admin ready: {phone}")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "create-superadmin":
        asyncio.run(create_superadmin(sys.argv[2]))
    elif cmd == "expire-orders":
        from app.services.orders import expire_pending_orders

        print("expired:", asyncio.run(expire_pending_orders()))
    elif cmd == "send-reminders":
        from app.services.reminders import send_event_reminders

        print("reminders sent:", asyncio.run(send_event_reminders()))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
