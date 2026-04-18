from fastapi import FastAPI

app = FastAPI(title="ClinCore Platform")

@app.get("/")
async def root():
    return {"status": "ok"}

@app.get("/health")
async def health():
    return {"health": "healthy"}
