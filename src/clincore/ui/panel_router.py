from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import pathlib

router = APIRouter(prefix="/panel", tags=["panel"])

_ROOT = pathlib.Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(_ROOT / "templates"))

@router.get("/", response_class=HTMLResponse)
async def panel_root(request: Request):
    return templates.TemplateResponse(
        request,
        "panel/base.html",
        {"version": "0.2.0"},
    )