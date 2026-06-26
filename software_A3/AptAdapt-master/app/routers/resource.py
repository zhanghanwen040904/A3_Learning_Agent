"""资源生成路由 — /resource/generate"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import ResourceGenerateRequest, ResourceGenerateResponse
from ..services.profile_manager import get_profile
from ..services.retriever import retrieve
from ..services.resource_generator import generate_resources

router = APIRouter(prefix="/resource", tags=["资源生成"])


@router.post("/generate", response_model=ResourceGenerateResponse, summary="生成个性化学习资源")
async def generate(req: ResourceGenerateRequest, db: Session = Depends(get_db)):
    """
    按知识点和学生画像生成个性化学习资源。

    支持 5 类资源:
    - doc: 讲解文档 (Markdown)
    - mindmap: 思维导图 (Mermaid)
    - quiz: 练习题 (JSON)
    - code: 代码案例 (JSON)
    - video_script: 视频脚本 (Markdown)

    生成完成后自动经过 Reviewer 审核。
    """
    if not req.resource_types:
        raise HTTPException(status_code=400, detail="resource_types 不能为空")

    valid_types = {"doc", "mindmap", "quiz", "code", "video_script"}
    invalid = set(req.resource_types) - valid_types
    if invalid:
        raise HTTPException(status_code=400, detail=f"不支持的资源类型: {invalid}")

    # 1. 查询画像
    uid = 1 if req.user_id == "demo_user" else int(req.user_id) if req.user_id.isdigit() else 1
    profile = get_profile(db, uid)

    # 2. 检索知识库
    chunks = retrieve(req.knowledge_point, top_k=5, course_id=req.course)

    # 3. 生成资源 + 审核
    try:
        resources, review = generate_resources(
            knowledge_point=req.knowledge_point,
            resource_types=req.resource_types,
            profile=profile,
            chunks=chunks,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"资源生成失败: {str(e)}")

    return ResourceGenerateResponse(
        resources=resources,
        review=review,
    )
