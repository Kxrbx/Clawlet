"""
Dashboard API server with FastAPI.
"""

from contextlib import asynccontextmanager
from typing import Optional
import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from loguru import logger

from clawlet import Config, load_config
from clawlet.health import HealthChecker, quick_health_check
from clawlet.exceptions import ClawletError


# Pydantic models

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    checks: list[dict]


class AgentStatus(BaseModel):
    """Agent status."""
    running: bool
    provider: str
    model: str
    messages_processed: int
    uptime_seconds: int


class SettingsResponse(BaseModel):
    """Settings response."""
    provider: str
    model: str
    storage: str
    max_iterations: int
    temperature: float


class SettingsUpdate(BaseModel):
    """Settings update request."""
    provider: Optional[str] = None
    model: Optional[str] = None
    max_iterations: Optional[int] = None
    temperature: Optional[float] = None


# Global state
config: Optional[Config] = None
health_checker: Optional[HealthChecker] = None
agent_status: dict = {
    "running": False,
    "provider": "openrouter",
    "model": "anthropic/claude-sonnet-4",
    "messages_processed": 0,
    "uptime_seconds": 0,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager."""
    # Startup
    global config, health_checker
    
    try:
        config = load_config()
        health_checker = HealthChecker()
        
        logger.info("Dashboard API started")
        yield
        
    finally:
        # Shutdown
        logger.info("Dashboard API stopped")


# Create FastAPI app
app = FastAPI(
    title="Clawlet Dashboard API",
    description="API for Clawlet dashboard",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health endpoints

@app.get("/health", response_model=HealthResponse)
async def get_health():
    """Get system health status."""
    try:
        result = await quick_health_check()
        return HealthResponse(**result)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health/detailed")
async def get_detailed_health():
    """Get detailed health checks with provider/storage."""
    if health_checker is None:
        raise HTTPException(status_code=503, detail="Health checker not initialized")
    
    try:
        result = await health_checker.check_all()
        return result
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Agent endpoints

@app.get("/agent/status", response_model=AgentStatus)
async def get_agent_status():
    """Get current agent status."""
    return AgentStatus(**agent_status)


@app.post("/agent/start")
async def start_agent():
    """Start the agent."""
    if agent_status["running"]:
        return {"success": False, "message": "Agent already running"}
    
    # TODO: Implement actual agent start
    agent_status["running"] = True
    agent_status["uptime_seconds"] = 0
    
    # Start uptime counter
    asyncio.create_task(update_uptime())
    
    logger.info("Agent started via API")
    return {"success": True, "message": "Agent started"}


@app.post("/agent/stop")
async def stop_agent():
    """Stop the agent."""
    if not agent_status["running"]:
        return {"success": False, "message": "Agent not running"}
    
    # TODO: Implement actual agent stop
    agent_status["running"] = False
    
    logger.info("Agent stopped via API")
    return {"success": True, "message": "Agent stopped"}


# Settings endpoints

@app.get("/settings", response_model=SettingsResponse)
async def get_settings():
    """Get current settings."""
    if config is None:
        raise HTTPException(status_code=503, detail="Config not loaded")
    
    return SettingsResponse(
        provider=config.provider.primary,
        model=config.provider.openrouter.model if config.provider.openrouter else "default",
        storage=config.storage.backend,
        max_iterations=config.agent.max_iterations,
        temperature=config.agent.temperature,
    )


@app.post("/settings")
async def update_settings(settings: SettingsUpdate):
    """Update settings."""
    if config is None:
        raise HTTPException(status_code=503, detail="Config not loaded")
    
    # Update config (in-memory only)
    if settings.provider:
        config.provider.primary = settings.provider
    if settings.max_iterations:
        config.agent.max_iterations = settings.max_iterations
    if settings.temperature:
        config.agent.temperature = settings.temperature
    
    # TODO: Save to disk
    logger.info(f"Settings updated: {settings}")
    
    return {"success": True, "message": "Settings updated"}


# Logs endpoint

@app.get("/logs")
async def get_logs(limit: int = 100):
    """Get recent logs."""
    # TODO: Implement actual log retrieval
    return {
        "logs": [
            {
                "level": "INFO",
                "message": "Agent started",
                "timestamp": "2026-02-10T21:00:00Z",
            },
            {
                "level": "INFO",
                "message": "Connected to OpenRouter",
                "timestamp": "2026-02-10T21:00:01Z",
            },
        ],
        "limit": limit,
    }


# Console endpoint (WebSocket would be better, but HTTP for now)

@app.get("/console")
async def get_console_output():
    """Get recent console output."""
    # TODO: Implement actual console output retrieval
    return {
        "output": [
            "[INFO] Agent started",
            "[INFO] Connected to OpenRouter",
            "[INFO] Loading identity from ~/.clawlet/",
            "[INFO] Initializing Telegram channel...",
            "[SUCCESS] Ready to receive messages",
        ]
    }


# Root

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Clawlet Dashboard API",
        "version": "0.1.0",
        "status": "running",
    }


# Helper functions

async def update_uptime():
    """Update agent uptime every second."""
    while agent_status["running"]:
        await asyncio.sleep(1)
        agent_status["uptime_seconds"] += 1


# Run server

def run_server(port: int = 8000):
    """Run the dashboard API server."""
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    run_server()
