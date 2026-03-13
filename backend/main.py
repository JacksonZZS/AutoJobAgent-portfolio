"""
FastAPI 主应用
集成所有路由和中间件
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.exceptions import RequestValidationError
from pathlib import Path
from contextlib import asynccontextmanager

# 导入 API 路由
from backend.api.v1 import auth, upload, analysis, jobs, history, materials, websocket, resume_optimizer, platforms, statistics, favorites, notifications, feedback, email, interview, market_intelligence

# 导入中间件
from backend.middleware.cors import setup_cors
from backend.middleware.error_handler import (
    global_exception_handler,
    validation_exception_handler
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print("🧹 Cleaning stale status files on startup...")
    status_dir = Path("data/status")
    if status_dir.exists():
        from core.status_manager import StatusManager
        for status_file in status_dir.glob("status_*.json"):
            try:
                user_id = status_file.stem.replace("status_", "")
                status_mgr = StatusManager(user_id=user_id)
                status_mgr.reset()
                print(f"   ✅ Reset status for user: {user_id}")
            except Exception as e:
                print(f"   ⚠️ Failed to clean status for {status_file}: {e}")
    print("✅ Startup cleanup complete")
    yield
    print("👋 Shutting down AutoJobAgent API...")

app = FastAPI(
    title="AutoJobAgent API",
    description="AI-Powered Job Application Automation Platform",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

setup_cors(app)
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# 注册所有路由
app.include_router(auth.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(history.router, prefix="/api/v1")
app.include_router(materials.router, prefix="/api/v1")
app.include_router(websocket.router, prefix="/api/v1")
app.include_router(resume_optimizer.router, prefix="/api/v1")
app.include_router(platforms.router, prefix="/api/v1")
app.include_router(statistics.router, prefix="/api/v1")
app.include_router(favorites.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")
app.include_router(email.router, prefix="/api/v1")
app.include_router(interview.router, prefix="/api/v1")
app.include_router(market_intelligence.router, prefix="/api/v1")

outputs_dir = Path("data/outputs")
if outputs_dir.exists():
    app.mount("/static", StaticFiles(directory=str(outputs_dir)), name="static")

frontend_dist = Path("frontend/dist")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "2.0.0", "service": "AutoJobAgent API"}

@app.get("/")
async def root():
    index_file = frontend_dist / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Welcome to AutoJobAgent API", "version": "2.0.0", "docs": "/docs"}

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith(("api/", "docs", "redoc", "openapi", "static", "health")):
        return None
    file_path = frontend_dist / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    index_file = frontend_dist / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"error": "Frontend not found"}

if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="frontend_assets")

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting AutoJobAgent API Server")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
