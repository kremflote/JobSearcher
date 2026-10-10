from fastapi import APIRouter

from jobsearcher.api.schemas import Overview
from jobsearcher.web.errors import not_implemented

router = APIRouter(tags=["overview"])


@router.get("/overview")
def get_overview() -> Overview:
    raise not_implemented()
