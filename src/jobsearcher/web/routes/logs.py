from fastapi import APIRouter

from jobsearcher.api.schemas import AgentRunLog, DiscardedLog, RunLog
from jobsearcher.web.errors import not_implemented

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/runs")
def list_runs() -> RunLog:
    raise not_implemented()


@router.get("/agent-runs")
def list_agent_runs() -> AgentRunLog:
    raise not_implemented()


@router.get("/discarded")
def list_discarded() -> DiscardedLog:
    raise not_implemented()
