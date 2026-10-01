"""FastAPI app: JSON API under /api, plus the built React frontend (frontend/dist) in production.

Run locally: uvicorn backend.main:app --reload
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from backend import config, db
from backend.gemini import GeminiError
from backend.routes import ask, operator
from backend.seed import seed_if_empty

# Module-level so tests can point it at a temp build.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast: a deploy without a key should crash visibly, not escalate every question.
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")
    db.init_db()
    seed_if_empty()  # re-seeds on every cold boot on Render's free tier (decision log #11)
    yield


app = FastAPI(title="Little Acorns Front Desk", lifespan=lifespan)


@app.exception_handler(GeminiError)
async def gemini_unavailable(request: Request, exc: GeminiError) -> JSONResponse:
    # Reached only by KB writes (re-embedding); /api/ask handles GeminiError itself as system_error.
    return JSONResponse(status_code=503, content={"detail": "The AI service is unavailable. Please try again."})


@app.get("/api/health")
def health() -> dict:
    # db_path lets you confirm the deployed DB is on the persistent disk (/var/data/..., decision log #27).
    return {"ok": True, "db_path": str(Path(config.DB_PATH).resolve())}


app.include_router(ask.router, prefix="/api")
app.include_router(operator.router, prefix="/api")


@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str) -> FileResponse:
    """Serve built files, falling back to index.html so client routes like /operator work."""
    if path == "api" or path.startswith("api/"):
        raise HTTPException(404, "Not found")  # unknown API routes stay JSON 404s
    index = FRONTEND_DIST / "index.html"
    if not index.is_file():
        raise HTTPException(404, "Frontend not built (run `npm run build` in frontend/)")
    candidate = (FRONTEND_DIST / path).resolve()
    if path and candidate.is_file() and candidate.is_relative_to(FRONTEND_DIST.resolve()):
        return FileResponse(candidate)
    return FileResponse(index)
