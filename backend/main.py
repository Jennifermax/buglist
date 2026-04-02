from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path
from .routers import config, testcases, generate, execute, document, chat, generate_jobs, zentao, browser_auth, vision
from .services.zentao_init import init_zentao, create_test_bug

# 禅道服务实例（全局）
zentao_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的处理"""
    global zentao_service

    # 启动时：初始化禅道
    print("\n" + "="*50)
    print("Buglist 后端服务启动中...")
    print("="*50)

    zentao_service = await init_zentao()

    if zentao_service:
        # 创建测试 Bug
        await create_test_bug(zentao_service, product_id=1)

    print("="*50)
    print("后端服务启动完成!")
    print("="*50 + "\n")

    yield

    # 关闭时：清理资源
    if zentao_service:
        await zentao_service.close()
        print("禅道连接已关闭")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="Buglist API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://0.0.0.0:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config.router)
app.include_router(testcases.router)
app.include_router(generate.router)
app.include_router(execute.router)
app.include_router(document.router)
app.include_router(chat.router)
app.include_router(generate_jobs.router)
app.include_router(zentao.router)
app.include_router(browser_auth.router)
app.include_router(vision.router)
app.mount("/artifacts", StaticFiles(directory=PROJECT_ROOT / "artifacts"), name="artifacts")

@app.get("/")
async def root():
    return {"message": "Buglist API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
