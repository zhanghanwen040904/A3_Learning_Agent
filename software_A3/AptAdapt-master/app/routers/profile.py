"""画像路由 — 获取与更新学生画像"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import StudentProfile, ProfileResponse, ProfileUpdateRequest
from ..services.profile_manager import get_profile, save_profile, extract_profile_from_text

router = APIRouter(prefix="/profile", tags=["画像"])


@router.get("/get", response_model=ProfileResponse, summary="获取学生画像")
async def get_student_profile(user_id: str = "demo_user", db: Session = Depends(get_db)):
    """根据 user_id 获取学生画像，未生成时返回空画像"""
    # demo_user 映射到 user_id=1
    uid = 1 if user_id == "demo_user" else int(user_id) if user_id.isdigit() else 1

    profile = get_profile(db, uid)
    if profile is None:
        return ProfileResponse(
            user_id=user_id,
            profile=StudentProfile(),
        )
    return ProfileResponse(user_id=user_id, profile=profile)


@router.post("/update", response_model=ProfileResponse, summary="手动更新学生画像")
async def update_student_profile(req: ProfileUpdateRequest, user_id: str = "demo_user",
                                  db: Session = Depends(get_db)):
    """手动覆盖学生画像"""
    uid = 1 if user_id == "demo_user" else int(user_id) if user_id.isdigit() else 1

    row = save_profile(db, uid, req.profile)
    return ProfileResponse(
        user_id=user_id,
        profile=req.profile,
        updated_at=row.updated_at,
    )


@router.post("/extract", response_model=ProfileResponse, summary="从对话文本抽取画像")
async def extract_profile_from_conversation(text: str, user_id: str = "demo_user",
                                             db: Session = Depends(get_db)):
    """输入一段文本，由大模型抽取画像并保存"""
    uid = 1 if user_id == "demo_user" else int(user_id) if user_id.isdigit() else 1

    try:
        profile = extract_profile_from_text(text)
        row = save_profile(db, uid, profile)
        return ProfileResponse(
            user_id=user_id,
            profile=profile,
            updated_at=row.updated_at,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"画像抽取失败: {str(e)}")
