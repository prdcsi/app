from fastapi import Header, HTTPException

from app.core.config import settings


async def verify_admin_token(
    x_admin_token: str = Header(alias="X-Admin-Token"),
):
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")