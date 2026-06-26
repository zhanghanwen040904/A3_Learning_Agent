from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, Base
from .routers import auth, chat, profile, resource, health, course

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AptAdapt — 个性化学习智能体", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(profile.router)
app.include_router(resource.router)
app.include_router(health.router)
app.include_router(course.router)


@app.get("/")
def root():
    return {"message": "AptAdapt 后端服务已启动"}
