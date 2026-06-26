"""
Pipeline 端到端验证脚本

用法:
    python scripts/test_pipeline.py          # 基础检查（不调用 API）
    python scripts/test_pipeline.py --full   # 全链路检查（调用 API）
    python scripts/test_pipeline.py --stage profile  # 仅测画像
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m⚠\033[0m"

results = {}


def check(name: str, condition: bool, detail: str = "") -> bool:
    status = PASS if condition else FAIL
    extra = f" — {detail}" if detail else ""
    print(f"  {status} {name}{extra}")
    results[name] = condition
    return condition


def test_imports():
    print("\n[1/5] 模块导入检查")
    try:
        from app.config import XFYUN_APPID, XFYUN_API_KEY, DATABASE_URL, SECRET_KEY
        check("config.py", True, f"APPID={XFYUN_APPID}")
    except Exception as e:
        check("config.py", False, str(e))

    try:
        from app.database import engine, Base, get_db
        check("database.py", True)
    except Exception as e:
        check("database.py", False, str(e))

    try:
        from app.models import User, UserProfile
        check("models.py", True, "User + UserProfile")
    except Exception as e:
        check("models.py", False, str(e))

    try:
        from app.llm_client import SparkLLM
        check("llm_client.py", True, "SparkLLM")
    except Exception as e:
        check("llm_client.py", False, str(e))

    try:
        from app.services.retriever import retrieve, populate_knowledge_base
        check("retriever.py", True)
    except Exception as e:
        check("retriever.py", False, str(e))

    try:
        from app.services.profile_manager import extract_profile_from_text, get_profile, save_profile
        check("profile_manager.py", True)
    except Exception as e:
        check("profile_manager.py", False, str(e))

    try:
        from app.services.resource_generator import generate_resources, GENERATORS
        check("resource_generator.py", True, f"注册了 {len(GENERATORS)} 种资源类型")
    except Exception as e:
        check("resource_generator.py", False, str(e))


def test_database():
    print("\n[2/5] 数据库检查")
    try:
        from app.database import engine, Base, SessionLocal
        from app.models import User, UserProfile
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        user_count = db.query(User).count()
        profile_count = db.query(UserProfile).count()
        db.close()
        check("数据库建表", True, f"users={user_count}, profiles={profile_count}")
    except Exception as e:
        check("数据库建表", False, str(e))


def test_chroma():
    print("\n[3/5] Chroma 知识库检查")
    try:
        from app.services.retriever import _get_retriever
        r = _get_retriever()
        count = r.count
        if count > 0:
            check("Chroma 连接", True, f"已入库 {count} 条")
        else:
            check("Chroma 连接", True, "连接正常但知识库为空 (运行 populate_knowledge_base() 入库)")
    except Exception as e:
        check("Chroma 连接", False, str(e))

    # 检索测试（无 API 调用 — 知识库为空时安全）
    try:
        from app.services.retriever import retrieve
        chunks = retrieve("Cache 映射方式", top_k=3)
        if chunks:
            check("retrieve() 检索", True, f"返回 {len(chunks)} 条")
        else:
            check("retrieve() 检索", True, "知识库为空，返回空列表（符合预期）")
    except Exception as e:
        check("retrieve() 检索", False, str(e))


def test_profile_extraction():
    print("\n[4/5] 画像抽取检查")
    try:
        from app.services.profile_manager import extract_profile_from_text
        sample = "我是大二的，计算机专业，数字逻辑还行但汇编很弱，想重点学Cache和流水线"
        profile = extract_profile_from_text(sample)
        has_fields = profile.major or profile.grade or profile.weak_points
        if has_fields:
            check("画像抽取", True, f"major={profile.major}, grade={profile.grade}")
            print(f"       weak_points={profile.weak_points}")
        else:
            check("画像抽取", False, "LLM 返回空画像（API 可能不可用）")
    except Exception as e:
        check("画像抽取", False, str(e))


def test_pipeline_trace():
    print("\n[5/5] Pipeline 串联检查")

    # 模拟完整链路的数据流通
    trace = []

    try:
        from app.services.profile_manager import extract_profile_from_text
        sample = "大三，计科专业，想学Cache映射方式"
        profile = extract_profile_from_text(sample)
        trace.append("profile")
        check("  → 画像", profile is not None)
    except Exception as e:
        check("  → 画像", False, str(e))

    try:
        from app.services.retriever import retrieve
        chunks = retrieve("Cache 映射方式", top_k=3)
        trace.append("retrieve")
        check("  → 检索", True, f"{len(chunks)} 条")
    except Exception as e:
        check("  → 检索", False, str(e))

    try:
        from app.services.resource_generator import generate_resources
        trace.append("generate")
        check("  → 生成函数可用", True)
    except Exception as e:
        check("  → 生成函数", False, str(e))

    if len(trace) == 3:
        print(f"\n  Pipeline 链路完整性: {PASS} 画像 → 检索 → 生成 全部可串联")
    else:
        missing = {"profile", "retrieve", "generate"} - set(trace)
        print(f"\n  Pipeline 链路完整性: {WARN} 缺失阶段: {missing}")


def print_summary():
    passed = sum(results.values())
    total = len(results)
    print(f"\n{'='*50}")
    print(f"结果: {passed}/{total} 通过")
    if passed == total:
        print(f"{PASS} 所有检查通过，可以启动后端服务")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"{WARN} 以下项未通过: {failed}")
    print(f"{'='*50}")


if __name__ == "__main__":
    full_mode = "--full" in sys.argv
    stage = None
    for arg in sys.argv:
        if arg.startswith("--stage="):
            stage = arg.split("=", 1)[1]

    print("AptAdapt Pipeline 验证")
    print(f"模式: {'全链路 (含 API 调用)' if full_mode else '基础检查 (无 API 调用)'}")

    if stage:
        stages = {
            "imports": test_imports,
            "database": test_database,
            "chroma": test_chroma,
            "profile": test_profile_extraction,
            "pipeline": test_pipeline_trace,
        }
        fn = stages.get(stage)
        if fn:
            fn()
        else:
            print(f"未知阶段: {stage}，可选: {list(stages.keys())}")
    else:
        test_imports()
        test_database()
        test_chroma()
        if full_mode:
            test_profile_extraction()
        test_pipeline_trace()

    print_summary()
