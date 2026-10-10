from fastapi import APIRouter

from jobsearcher.api.schemas import Settings, SettingsPatch
from jobsearcher.web.errors import not_implemented

router = APIRouter(tags=["settings"])


@router.get("/settings")
def get_settings() -> Settings:
    raise not_implemented()


@router.patch("/settings")
def update_settings(body: SettingsPatch) -> Settings:
    raise not_implemented()
