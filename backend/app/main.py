import os
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api import routes as routes_module
from app.api.routes import router
from app.api.websocket_hub import hub

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Resume durable queued directives whenever the API process starts."""
    routes_module.sprint_queue.resume_pending()
    try:
        yield
    finally:
        await asyncio.gather(*(routes_module._stop_preview(project_id)
                               for project_id in list(routes_module.preview_processes)),
                             return_exceptions=True)


app = FastAPI(title="Virtual AI Office PM Dashboard", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000", "http://localhost:8000",
        "http://127.0.0.1:5173", "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' ws: wss:; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none';"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

app.include_router(router)

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(websocket)
    except Exception:
        hub.disconnect(websocket)

# Serve built frontend static files if present
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        dist_root = Path(frontend_dist).resolve()
        file_path = (dist_root / full_path).resolve()
        try:
            file_path.relative_to(dist_root)
        except ValueError:
            return FileResponse(dist_root / "index.html")
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dist, "index.html"))
