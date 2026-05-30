from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.web.routes import router

app = FastAPI(title="Atrioly Wanatring Control Panel", version="v4.0-alpha.1")
app.mount("/static", StaticFiles(directory="src/web/static"), name="static")
app.include_router(router)
