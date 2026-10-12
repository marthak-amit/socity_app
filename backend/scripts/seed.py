"""Seed realistic demo data.

    python -m scripts.seed            # seeds only if the database is empty
    python -m scripts.seed --reset    # wipes ALL data first (dev only!)

Demo logins (OTP is 123456 when OTP_FIXED_CODE=123456, else check the API log) are printed at the end.
"""

import asyncio
import io
import sys
import uuid
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw
from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import make_qr_token, random_code
from app.models import (
    AuditLog,
    Event,
    EventDay,
    GalleryItem,
    Membership,
    Order,
    OrderItem,
    Pass,
    PassScan,
    PassTier,
    PassTierDay,
    PreapprovedMember,
    Society,
    User,
    VolunteerAssignment,
)
from app.services.events import VOLUNTEER_GRACE
from app.services.images import process_image
from app.services.orders import compute_flags
from app.services.storage import get_storage

IST = ZoneInfo("Asia/Kolkata")
SUPER_ADMIN = "+919800000001"

PEOPLE = {
    # key: (phone, name)
    "ramesh": ("+919800000011", "Ramesh Patel"), "sunita": ("+919800000012", "Sunita Shah"), "kiran": ("+919800000013", "Kiran Desai"),
    "meera": ("+919800000014", "Meera Joshi"), "raj": ("+919800000015", "Raj Mehta"), "anita": ("+919800000016", "Anita Verma"),
    "deepak": ("+919800000017", "Deepak Trivedi"), "farida": ("+919800000018", "Farida Sheikh"), "harsh": ("+919800000019", "Harsh Parikh"),
    "vikram": ("+919800000031", "Vikram Singh"), "pooja": ("+919800000032", "Pooja Nair"), "arjun": ("+919800000033", "Arjun Rao"),
    "newbie": ("+919800000040", "Neha Kapoor"),
}


def local(d, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(d, time(hh, mm), tzinfo=IST).astimezone(UTC)


def fake_image(label: str, color: tuple[int, int, int], size=(900, 600), sub: str = "") -> bytes:
    img = Image.new("RGB", size, color)
    d = ImageDraw.Draw(img)
    for i in range(0, size[1], 6):  # soft gradient bands
        shade = tuple(min(255, c + i // 8) for c in color)
        d.rectangle([0, i, size[0], i + 6], fill=shade)
    d.rectangle([40, 40, size[0] - 40, size[1] - 40], outline=(255, 255, 255), width=4)
    d.text((70, 70), label, fill=(255, 255, 255))
    if sub:
        d.text((70, 110), sub, fill=(255, 255, 255))
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


async def put_public(storage, society_id, kind: str, data: bytes, thumb: bool = False):
    main, th = process_image(data, max_side=2048, thumb_side=480 if thumb else None)
    base = f"public/societies/{society_id}/{kind}/{uuid.uuid4()}"
    await storage.put_object(f"{base}.jpg", main.data, "image/jpeg")
    if th:
        await storage.put_object(f"{base}_thumb.jpg", th.data, "image/jpeg")
    return f"{base}.jpg", (f"{base}_thumb.jpg" if th else None), main


async def put_screenshot(storage, society_id, label: str):
    main, _ = process_image(fake_image("UPI payment", (24, 112, 74), (600, 1000), label), max_side=2200)
    key = f"private/societies/{society_id}/screenshot/{uuid.uuid4()}.jpg"
    await storage.put_object(key, main.data, "image/jpeg")
    return key


async def seed() -> None:
    settings = get_settings()
    storage = get_storage()
    today = datetime.now(IST).date()
    async with SessionLocal() as s:
        # ---------------------------------------------------------------- users
        users: dict[str, User] = {}
        for key, (phone, name) in PEOPLE.items():
            users[key] = User(phone=phone, name=name, locale="en")
            s.add(users[key])
        sa = User(phone=SUPER_ADMIN, name="Platform Admin", is_super_admin=True)
        s.add(sa)
        await s.flush()

        # ---------------------------------------------------------------- societies
        a = Society(name="Green Valley Residency", city="Ahmedabad", address="Satellite Road, Ahmedabad 380015",
                    invite_code="GREEN123", upi_id="greenvalley@okhdfcbank", upi_name="Green Valley Residency",
                    created_by=users["ramesh"].id)
        b = Society(name="Sunrise Heights", city="Surat", address="Vesu, Surat 395007", invite_code="SUNRISE9",
                    upi_id="sunriseheights@okicici", upi_name="Sunrise Heights CHS", created_by=users["vikram"].id)
        s.add_all([a, b])
        await s.flush()

        def member(user, soc, role="member", wing=None, flat=None, status="active"):
            m = Membership(user_id=users[user].id, society_id=soc.id, role=role, wing=wing, flat_no=flat, status=status,
                           approved_by=users["ramesh"].id if status == "active" else None)
            s.add(m)
            return m

        member("ramesh", a, "owner", "A", "001"); member("sunita", a, "admin", "A", "102"); member("kiran", a, "volunteer", "B", "201")
        member("meera", a, "member", "A", "101"); member("raj", a, "member", "B", "202"); member("anita", a, "member", "C", "303", "pending")
        member("deepak", a, "member", "C", "104"); member("farida", a, "member", "B", "305"); member("harsh", a, "member", "A", "401")
        member("vikram", b, "owner", "T1", "1001"); member("pooja", b, "admin", "T1", "1203"); member("arjun", b, "member", "T2", "804")
        member("meera", b, "admin", "T2", "501")   # same person, different role in another society → exercises the switcher
        member("kiran", b, "member", "T1", "302")
        s.add(PreapprovedMember(society_id=a.id, phone=PEOPLE["newbie"][0], name="Neha Kapoor", wing="D", flat_no="405"))
        await s.flush()

        # ---------------------------------------------------------------- events
        def event(soc, creator, title, desc, venue, start, end, status="published", is_paid=True):
            e = Event(society_id=soc.id, title=title, description=desc, venue=venue, starts_at=start, ends_at=end, status=status,
                      is_paid=is_paid, created_by=users[creator].id)
            s.add(e)
            return e

        d0 = today - timedelta(days=1)
        navratri = event(a, "sunita", "Navratri Garba Mahotsav 2026",
                         "Nine nights of garba & dandiya with live dhol, authentic Gujarati food stalls and prizes for best dressed.\n\nGates open 7:30 PM. Traditional attire encouraged.",
                         "Clubhouse Lawn, Green Valley", local(d0, 19), local(d0 + timedelta(days=8), 23, 30))
        diwali = event(a, "sunita", "Diwali Snehmilan 2026", "Annual get-together with rangoli competition, dinner and fireworks display.", "Community Hall",
                       local(today + timedelta(days=24), 18), local(today + timedelta(days=24), 22))
        past = event(a, "ramesh", "Independence Day Cultural Evening", "Flag hoisting, patriotic songs and a children's talent show.", "Central Garden",
                     local(today - timedelta(days=58), 17), local(today - timedelta(days=58), 21))
        draft = event(a, "sunita", "New Year Gala 2027", "Draft — DJ night & dinner buffet.", "Rooftop Terrace",
                      local(today + timedelta(days=80), 20), local(today + timedelta(days=81), 1), status="draft")
        carnival = event(b, "vikram", "Winter Carnival (Free Entry)", "Games, food trucks and a kids' zone. Free passes for residents!", "Podium Garden",
                         local(today + timedelta(days=9), 16), local(today + timedelta(days=9), 21), is_paid=False)
        await s.flush()

        days: dict[uuid.UUID, list[EventDay]] = {}
        for ev, n in ((navratri, 9), (diwali, 1), (past, 1), (draft, 2), (carnival, 1)):
            first = ev.starts_at.astimezone(IST).date()
            days[ev.id] = [EventDay(event_id=ev.id, date=first + timedelta(days=i), label=(f"Night {i + 1}" if n > 1 else None)) for i in range(n)]
            s.add_all(days[ev.id])
        await s.flush()
        nav_days = days[navratri.id]
        nav_days[7].label = "Ashtami (Night 8)"; nav_days[8].label = "Dussehra (Night 9)"

        def tier(ev, name, price, cap, limit=4, guests=True, specific: list[EventDay] | None = None, order=0, desc=None):
            t = PassTier(event_id=ev.id, name=name, price=price, capacity=cap, per_user_limit=limit, allow_guests=guests, sort_order=order,
                         valid_days="specific" if specific else "all", description=desc)
            s.add(t)
            t._days = specific or []  # type: ignore[attr-defined]
            return t

        t_season = tier(navratri, "Season Pass (all 9 nights)", 1500, 200, 6, order=0, desc="Entry on all nine nights")
        t_night = tier(navratri, "Single Night", 250, 400, 8, order=1, desc="Any one night — valid on every day, scan once per day")
        t_ashtami = tier(navratri, "Ashtami Special Night", 400, 120, 4, specific=[nav_days[7]], order=2, desc="Grand finale night only")
        t_kids = tier(navratri, "Kids (under 10)", 0, 100, 3, guests=False, order=3, desc="Free entry for children")
        t_dinner = tier(diwali, "Family Dinner (up to 4)", 800, 80, 3, order=0)
        t_guest = tier(diwali, "Guest Pass", 400, 40, 4, order=1)
        t_past = tier(past, "Entry", 100, 300, 5)
        t_draft = tier(draft, "Couple", 2500, 60, 2)
        t_free = tier(carnival, "Resident Entry", 0, 300, 5)
        await s.flush()
        for t in (t_season, t_night, t_ashtami, t_kids, t_dinner, t_guest, t_past, t_draft, t_free):
            for d in t._days:  # type: ignore[attr-defined]
                s.add(PassTierDay(tier_id=t.id, event_day_id=d.id))

        s.add(VolunteerAssignment(event_id=navratri.id, user_id=users["kiran"].id, expires_at=navratri.ends_at + VOLUNTEER_GRACE))
        await s.flush()

        # ---------------------------------------------------------------- orders
        async def order(user_key, ev, soc, items, status, *, utr=None, paid=None, shot=True, submitted=True, reason=None, age_h=2):
            u = users[user_key]
            total = sum(t.price * q for t, q, _ in items)
            o = Order(ref_code=f"SP-{random_code(8)}", event_id=ev.id, user_id=u.id, society_id=soc.id, total_amount=total, status=status,
                      utr=utr, paid_amount=paid if paid is not None else (total if utr or shot else None), flags=[],
                      created_at=datetime.now(UTC) - timedelta(hours=age_h))
            if submitted and total > 0:
                o.payment_submitted_at = datetime.now(UTC) - timedelta(hours=age_h - 0.1)
                if shot:
                    o.screenshot_key = await put_screenshot(storage, soc.id, o.ref_code)
            for t, q, holders in items:
                names = holders or [(u.name if i == 0 else f"{u.name.split()[0]}'s guest {i}", "member" if i == 0 else "guest") for i in range(q)]
                o.items.append(OrderItem(tier_id=t.id, qty=q, unit_price=t.price if ev.is_paid else 0, holders=[{"name": n, "type": ty} for n, ty in names]))
            s.add(o)
            await s.flush()
            if o.payment_submitted_at:
                await compute_flags(s, o)
            if status == "approved":
                o.reviewed_by, o.reviewed_at = users["sunita"].id, datetime.now(UTC) - timedelta(hours=max(age_h - 1, 0))
                for it in o.items:
                    for h in it.holders:
                        pid = uuid.uuid4()
                        s.add(Pass(id=pid, order_id=o.id, tier_id=it.tier_id, event_id=ev.id, society_id=soc.id, user_id=u.id, holder_name=h["name"],
                                   holder_type=h["type"], qr_token=make_qr_token(pid, ev.id)))
                s.add(AuditLog(society_id=soc.id, actor_id=users["sunita"].id, action="order.approve", entity="order", entity_id=str(o.id),
                               meta={"amount": total, "utr": utr, "flags": list(o.flags)}))
            elif status == "rejected":
                o.reviewed_by, o.reviewed_at, o.reject_reason = users["sunita"].id, datetime.now(UTC), reason
                s.add(AuditLog(society_id=soc.id, actor_id=users["sunita"].id, action="order.reject", entity="order", entity_id=str(o.id),
                               meta={"reason": reason, "amount": total}))
            return o

        fam = [("Meera Joshi", "member"), ("Aarav Joshi", "member"), ("Tanvi Joshi", "member"), ("Guest: Sneha Rao", "guest")]
        o1 = await order("meera", navratri, a, [(t_season, 4, fam)], "approved", utr="402611220001", age_h=30)
        await order("raj", navratri, a, [(t_night, 2, None), (t_kids, 1, [("Ishaan Mehta", "member")])], "approved", utr="402611220002", age_h=28)
        await order("deepak", navratri, a, [(t_ashtami, 2, None)], "approved", utr="402611220003", age_h=20)
        await order("farida", navratri, a, [(t_season, 1, None)], "approved", utr="402611220004", age_h=10)
        await order("harsh", navratri, a, [(t_night, 3, None)], "pending", utr="402611220005", age_h=3)
        await order("farida", navratri, a, [(t_night, 1, None)], "pending", utr="402611220005", age_h=1)             # duplicate UTR with Harsh
        await order("deepak", navratri, a, [(t_season, 1, None)], "pending", utr="402611220007", paid=1000, age_h=2)  # amount mismatch
        await order("harsh", navratri, a, [(t_night, 1, None)], "pending", utr=None, age_h=1)                          # screenshot only → missing UTR
        await order("raj", navratri, a, [(t_night, 1, None)], "pending", submitted=False, age_h=1)                      # awaiting payment
        await order("meera", navratri, a, [(t_ashtami, 1, None)], "rejected", utr="402611220099", reason="Payment not received in society account", age_h=40)
        await order("meera", navratri, a, [(t_kids, 2, [("Tanvi Joshi", "member"), ("Aarav Joshi", "member")])], "approved", age_h=25)   # free
        await order("meera", diwali, a, [(t_dinner, 1, None)], "approved", utr="402611220010", age_h=5)
        await order("raj", past, a, [(t_past, 2, None)], "approved", utr="402611220011", age_h=24 * 58)
        await order("arjun", carnival, b, [(t_free, 3, None)], "approved", age_h=6)
        await s.flush()

        # a few gate scans for tonight (Night 2 = today)
        today_day = nav_days[1]
        pass_rows = (await s.scalars(select(Pass).where(Pass.event_id == navratri.id, Pass.status == "active").order_by(Pass.created_at))).all()
        for p in pass_rows[:4]:
            s.add(PassScan(pass_id=p.id, event_day_id=today_day.id, scanned_by=users["kiran"].id, gate="Main Gate",
                           scanned_at=datetime.now(UTC) - timedelta(minutes=45)))
        _ = o1

        # ---------------------------------------------------------------- gallery
        palette = [(220, 90, 60), (60, 120, 200), (90, 170, 110), (180, 100, 200), (230, 170, 50), (50, 160, 180)]
        for i, col in enumerate(palette):
            key, thumb, img = await put_public(storage, a.id, "gallery", fake_image("Independence Day 2026", col, sub=f"Photo {i + 1}"), thumb=True)
            s.add(GalleryItem(society_id=a.id, event_id=past.id, url_key=key, thumb_key=thumb, width=img.width, height=img.height,
                              uploaded_by=users["sunita" if i % 2 == 0 else "ramesh"].id, status="approved", moderated_by=users["sunita"].id))
        for i, name in enumerate(("meera", "raj")):
            key, thumb, img = await put_public(storage, a.id, "gallery", fake_image("Member upload", (120, 120, 150), sub=f"by {PEOPLE[name][1]}"), thumb=True)
            s.add(GalleryItem(society_id=a.id, event_id=past.id, url_key=key, thumb_key=thumb, width=img.width, height=img.height,
                              uploaded_by=users[name].id, status="pending"))
        s.add(AuditLog(society_id=a.id, actor_id=users["ramesh"].id, action="society.create", entity="society", entity_id=str(a.id), meta={"name": a.name}))
        s.add(AuditLog(society_id=b.id, actor_id=users["vikram"].id, action="society.create", entity="society", entity_id=str(b.id), meta={"name": b.name}))
        await s.commit()
    _ = settings


async def reset() -> None:
    async with SessionLocal() as s:
        tables = (await s.execute(text("select tablename from pg_tables where schemaname='public' and tablename <> 'alembic_version'"))).scalars().all()
        await s.execute(text("truncate table " + ", ".join(f'"{t}"' for t in tables) + " restart identity cascade"))
        await s.commit()
    print("database wiped")


async def main() -> None:
    if "--reset" in sys.argv:
        if get_settings().is_prod:
            raise SystemExit("refusing to --reset in prod")
        await reset()
    async with SessionLocal() as s:
        if await s.scalar(select(func.count()).select_from(Society)):
            print("Database already has data — run with --reset to re-seed.")
            return
    await seed()
    code = get_settings().otp_fixed_code or "<see API log>"
    print(f"""
Seeded! OTP for every demo login: {code}

  Platform super-admin (web panel)   {SUPER_ADMIN}
  --- Green Valley Residency (invite code GREEN123) ---
  Owner      Ramesh Patel     {PEOPLE['ramesh'][0]}
  Admin      Sunita Shah      {PEOPLE['sunita'][0]}
  Volunteer  Kiran Desai      {PEOPLE['kiran'][0]}   (assigned to Navratri)
  Member     Meera Joshi      {PEOPLE['meera'][0]}   (has passes; ADMIN of Sunrise Heights → try the society switcher)
  Member     Raj Mehta        {PEOPLE['raj'][0]}
  Pending    Anita Verma      {PEOPLE['anita'][0]}   (join request waiting for approval)
  Pre-approved Neha Kapoor    {PEOPLE['newbie'][0]}   (CSV pre-approved → auto-approved on join with code GREEN123)
  --- Sunrise Heights (invite code SUNRISE9) ---
  Owner      Vikram Singh     {PEOPLE['vikram'][0]}
  Admin      Pooja Nair       {PEOPLE['pooja'][0]}
  Member     Arjun Rao        {PEOPLE['arjun'][0]}
""")


if __name__ == "__main__":
    asyncio.run(main())
