"""
FastAPI application entrypoint for WeatherLab Data API.
"""

from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware

from routers import router


def create_app() -> FastAPI:
    app = FastAPI(title="WeatherLab Data API", version="0.1.0")

    # Routers
    app.include_router(router, prefix="", tags=["data"])

    return app


app = create_app()
