"""课程路由 — 课程列表与切换"""
from fastapi import APIRouter

from ..courses import COURSES, DEFAULT_COURSE

router = APIRouter(prefix="/courses", tags=["课程"])


@router.get("/", summary="获取所有可用课程")
async def list_courses():
    """返回所有已注册的课程列表"""
    return {
        "courses": COURSES,
        "default": DEFAULT_COURSE,
        "total": len(COURSES),
    }


@router.get("/{course_id}", summary="获取单个课程详情")
async def get_course_detail(course_id: str):
    """返回指定课程的元数据"""
    from ..courses import get_course

    course = get_course(course_id)
    if not course:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")
    return course
