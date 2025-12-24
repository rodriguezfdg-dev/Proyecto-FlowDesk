from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware # Import SessionMiddleware
import os # Import os for secret key
from .database import engine, Base
from . import models
from .api import (
    clientes_api, 
    tickets_api, 
    actividades_api, 
    proyectos_api, 
    person_of_customer_api, 
    cards_api, 
    comments_api, 
    settings_api, 
    auth_api, 
    users_api, 
    checkinout_api, 
    attachments_api, 
    department_manager_api, 
    attention_flow_api,
    boards_api,
    reports_api
)

# This line creates the database tables based on your models
# It will run every time the application starts.
# For a real application, you'd use a migration tool like Alembic.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Innova Tickets API",
    description="API para el sistema de tickets de Innova S.A.",
    version="1.0.0"
)

origins = [
    "http://localhost",
    "http://localhost:5000",
    "http://127.0.0.1",
    "http://127.0.0.1:5000",
    "http://192.168.100.163:5000",
    # Allow any IP in the 192.168.x.x range for local network access
    "http://192.168.*",
]

# For development, we'll use allow_origin_regex to match local network IPs
import re

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add SessionMiddleware
app.add_middleware(SessionMiddleware, secret_key=os.urandom(32)) # Generate a random secret key

@app.get("/health", tags=["Monitoring"])
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}

app.include_router(auth_api.router)
app.include_router(users_api.router)
app.include_router(clientes_api.router)
app.include_router(tickets_api.router)
app.include_router(actividades_api.router)
app.include_router(proyectos_api.router)
app.include_router(person_of_customer_api.router)
app.include_router(cards_api.router)
app.include_router(comments_api.router)
app.include_router(settings_api.router)
app.include_router(checkinout_api.router)
app.include_router(attachments_api.router)
app.include_router(department_manager_api.router)
app.include_router(attention_flow_api.router)
app.include_router(boards_api.router)
app.include_router(reports_api.router)

@app.get("/debug/routes", tags=["Debug"])
async def debug_routes():
    """Lists all registered routes in the application."""
    routes_list = []
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            routes_list.append({
                "path": route.path,
                "methods": list(route.methods) if route.methods else []
            })
    return {"routes": routes_list}

@app.get("/debug-cors", tags=["Monitoring"])
async def debug_cors():
    return {"allowed_origins": origins}

# We will add more endpoints for tickets, users, etc. in the next steps.
