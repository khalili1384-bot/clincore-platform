"""Shop HTML pages router."""
import pathlib
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["shop-pages"])

_TEMPLATES_DIR = pathlib.Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/shop", response_class=HTMLResponse)
async def shop_index(request: Request):
    return templates.TemplateResponse(request, "shop/index.html", {})


@router.get("/shop/admin", response_class=HTMLResponse)
async def shop_admin(request: Request):
    return templates.TemplateResponse(request, "shop/index.html", {})
