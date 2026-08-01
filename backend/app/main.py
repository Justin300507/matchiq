from fastapi import FastAPI

app = FastAPI(title="MatchIQ API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
