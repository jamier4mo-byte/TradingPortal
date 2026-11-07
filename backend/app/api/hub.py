"""Hub API: one call for the greeting's welcome-back flag, the process streak, personal bests, the
first-run checklist and the week-behind recap."""

from fastapi import APIRouter

from ..core.deps import CurrentUser, Db
from ..models import utcnow
from ..schemas.hub import HubOut
from ..services import hub as hub_svc

router = APIRouter(prefix="/hub", tags=["hub"])


@router.get("", response_model=HubOut)
def get_hub(user: CurrentUser, db: Db) -> dict:
    return hub_svc.hub(db, user, utcnow())
