from fastapi import FastAPI
from app.modules.clinical.router import router as clinical_router

app = FastAPI(title="ClinCore Platform (Phase1 Lite)")
app.include_router(clinical_router)
