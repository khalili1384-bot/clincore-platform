"""Super Admin Explorer — serves the explorer HTML page."""
import pathlib
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["explorer"])

_HTML = pathlib.Path(__file__).resolve().parent.parent / "templates" / "explorer.html"


@router.get("/super-admin/explorer", response_class=HTMLResponse)
async def explorer_page():
    return HTMLResponse(content=_HTML.read_text(encoding="utf-8"))
