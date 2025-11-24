"""
FastAPI application entrypoint for WeatherLab Data API.
"""

from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware

from routers import router


def create_app() -> FastAPI:
    app = FastAPI(title="WeatherLab Data API", version="0.1.0")

    # # CORS - open by default; can be restricted later via settings
    # app.add_middleware(
    #     CORSMiddleware,
    #     allow_origins=["*"],
    #     allow_credentials=True,
    #     allow_methods=["*"],
    #     allow_headers=["*"],
    # )

    # Routers
    app.include_router(router, prefix="", tags=["data"])

    return app


app = create_app()
