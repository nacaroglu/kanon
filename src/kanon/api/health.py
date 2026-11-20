import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from kanon.db import get_session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
def health(session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
    """Report liveness plus database reachability; never raises on a database outage."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("database unreachable during health check")
        return {"status": "degraded", "database": "unreachable"}
    return {"status": "ok", "database": "ok"}
