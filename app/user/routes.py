from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.modules.auth.dependencies import current_user
from app.modules.auth.models import User

user_router = APIRouter(dependencies=[Depends(current_user)])


class UserSummary(BaseModel):
    email: str
    role: str


@user_router.get("/summary")
async def user_summary(user: User = Depends(current_user)) -> UserSummary:
    """Example endpoint of the user area: data about the signed-in user."""
    return UserSummary(email=user.email, role=user.role)
