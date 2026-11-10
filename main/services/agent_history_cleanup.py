from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from main.extensions import db
from main.models.user import RoverAgentMessage, RoverAgentSession


RETENTION_PERIOD = timedelta(days=7)
POSTGRES_CLEANUP_LOCK_ID = 743820194


def cleanup_expired_agent_history(now: datetime | None = None) -> int:
    cutoff = (now or datetime.now(timezone.utc)) - RETENTION_PERIOD

    if db.session.get_bind().dialect.name == "postgresql":
        lock_acquired = db.session.execute(
            text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
            {"lock_id": POSTGRES_CLEANUP_LOCK_ID},
        ).scalar_one()
        if not lock_acquired:
            db.session.rollback()
            return 0

    expired_session_ids = [
        row[0]
        for row in db.session.query(RoverAgentSession.session_id)
        .filter(
            RoverAgentSession.first_message_at.is_not(None),
            RoverAgentSession.first_message_at <= cutoff,
        )
        .all()
    ]
    if not expired_session_ids:
        db.session.commit()
        return 0

    db.session.query(RoverAgentMessage).filter(
        RoverAgentMessage.session_id.in_(expired_session_ids)
    ).delete(synchronize_session=False)
    db.session.query(RoverAgentSession).filter(
        RoverAgentSession.session_id.in_(expired_session_ids)
    ).delete(synchronize_session=False)
    db.session.commit()
    return len(expired_session_ids)
