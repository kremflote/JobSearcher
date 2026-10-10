from fastapi import APIRouter

from jobsearcher.api.schemas import Task, TaskRef
from jobsearcher.web.errors import not_implemented

router = APIRouter(tags=["tasks"])


@router.post("/runs", status_code=202)
def start_run() -> TaskRef:
    raise not_implemented()


@router.get("/tasks")
def list_tasks(active: bool = False) -> list[Task]:
    raise not_implemented()


@router.get("/tasks/{task_id}")
def get_task(task_id: str) -> Task:
    raise not_implemented()


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str) -> Task:
    raise not_implemented()
