from fastapi import FastAPI

from src.api.routes import router


app = FastAPI(
    title="RetailIQ API",
    description="AI-Powered Retail Analytics Platform",
    version="1.0"
)


app.include_router(router)


@app.get("/")
def home():

    return {
        "message": "Welcome to RetailIQ API 🚀"
    }