"""
Dashboard API server with FastAPI.
"""

from contextlib import asynccontextmanager
from typing import Optional
import asyncio
import os
import subprocess
import secrets

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List
import uvicorn

from loguru import logger

from clawlet import Config, load_config
from clawlet.health import HealthChecker, quick_health_check
from clawlet.exceptions import ClawletError
from clawlet.providers.models_cache import get_models_cache
from clawlet.metrics import format_prometheus


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
    max_tool_calls_per_message: int
    temperature: float


class SettingsUpdate(BaseModel):
    """Settings update request."""
    provider: Optional[str] = None
    model: Optional[str] = None
    max_iterations: Optional[int] = None
    max_tool_calls_per_message: Optional[int] = None
    temperature: Optional[float] = None


class ModelsResponse(BaseModel):
    """Models list response."""
    models: List[dict]
    updated_at: str


class CacheInfoResponse(BaseModel):
    """Cache info response."""
    updated_at: Optional[str] = None
    model_count: int
    is_expired: bool


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
agent_process: Optional[subprocess.Popen] = None  # <-- ajouté

# Dashboard API token (from env or generated)
DASHBOARD_TOKEN: Optional[str] = None

# Security scheme for Bearer token
security = HTTPBearer(auto_error=False)


def get_cors_origins() -> list[str]:
    """Get CORS origins from environment variable."""
    origins_env = os.environ.get("CORS_ORIGINS", "http://localhost:5173")
    # Split by comma and strip whitespace
    origins = [origin.strip() for origin in origins_env.split(",") if origin.strip()]
    if not origins:
        origins = ["http://localhost:5173"]
    return origins


def get_dashboard_token() -> str:
    """Get or generate dashboard API token."""
    global DASHBOARD_TOKEN
    if DASHBOARD_TOKEN is None:
        token_env = os.environ.get("CLawlet_DASHBOARD_TOKEN")
        if token_env:
            DASHBOARD_TOKEN = token_env
        else:
            # Generate a random token and store it
            # In production, this should be persisted in config
            DASHBOARD_TOKEN = secrets.token_urlsafe(32)
            logger.warning(
                f"Generated random dashboard token (set CLawlet_DASHBOARD_TOKEN to persist): {DASHBOARD_TOKEN}"
            )
    return DASHBOARD_TOKEN


async def verify_api_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """
    Verify API token from Authorization header.

    Args:
        credentials: HTTP Authorization credentials

    Returns:
        The token if valid

    Raises:
        HTTPException: 401 if token is missing or invalid
    """
    expected_token = get_dashboard_token()

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials.credentials != expected_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid API token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager."""
    # Startup
    global config, health_checker

    try:
        config = load_config()
        health_checker = HealthChecker()

        # Initialize dashboard token on startup
        get_dashboard_token()

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

# Add CORS with configurable origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
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
        # Record to history file
        try:
            from pathlib import Path
            history_file = Path.home() / ".clawlet" / "health_history.jsonl"
            history_file.parent.mkdir(parents=True, exist_ok=True)
            import json
            with open(history_file, "a") as f:
                f.write(json.dumps(result) + "\n")
        except Exception as e:
            logger.debug(f"Failed to write health history: {e}")
        return HealthResponse(**result)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health/history")
async def get_health_history(limit: int = 50, token: str = Depends(verify_api_token)):
    """Get recent health history."""
    try:
        from pathlib import Path
        import json
        history_file = Path.home() / ".clawlet" / "health_history.jsonl"
        if not history_file.exists():
            return {"history": []}
        lines = history_file.read_text().strip().split("\n")[-limit:]
        history = [json.loads(line) for line in lines if line.strip()]
        return {"history": list(reversed(history))}
    except Exception as e:
        logger.error(f"Health history read failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health/detailed")
async def get_detailed_health(token: str = Depends(verify_api_token)):
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
async def get_agent_status(token: str = Depends(verify_api_token)):
    """Get current agent status."""
    return AgentStatus(**agent_status)


@app.post("/agent/start")
async def start_agent(token: str = Depends(verify_api_token)):
    """Start the agent."""
    global agent_process
    
    if agent_status["running"]:
        return {"success": False, "message": "Agent already running"}
    
    # Load config to get workspace
    config = load_config()
    
    # Start agent as subprocess
    import subprocess
    try:
        agent_process = subprocess.Popen(
            ["python", "-m", "clawlet"],
            cwd=config.workspace,
            env={**os.environ, "CLAWLET_CONFIG": str(config.config_path)}
        )
        agent_status["running"] = True
        agent_status["uptime_seconds"] = 0
        agent_status["pid"] = agent_process.pid
        
        # Start uptime counter
        asyncio.create_task(update_uptime())
        
        logger.info("Agent started via API")
        return {"success": True, "message": f"Agent started (PID: {agent_process.pid})"}
    except Exception as e:
        logger.error(f"Failed to start agent: {e}")
        return {"success": False, "message": str(e)}


@app.post("/agent/stop")
async def stop_agent(token: str = Depends(verify_api_token)):
    """Stop the agent."""
    global agent_process, agent_status
    
    if not agent_status["running"]:
        return {"success": False, "message": "Agent not running"}
    
    if agent_process and agent_process.poll() is None:
        try:
            agent_process.terminate()
            try:
                agent_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                agent_process.kill()
        except Exception as e:
            logger.error(f"Error stopping agent: {e}")
            return {"success": False, "message": f"Error stopping agent: {e}"}
    
    agent_status["running"] = False
    agent_status["pid"] = None
    
    logger.info("Agent stopped via API")
    return {"success": True, "message": "Agent stopped"}


# Settings endpoints

@app.get("/settings", response_model=SettingsResponse)
async def get_settings(token: str = Depends(verify_api_token)):
    """Get current settings."""
    if config is None:
        raise HTTPException(status_code=503, detail="Config not loaded")
    
    return SettingsResponse(
        provider=config.provider.primary,
        model=config.provider.openrouter.model if config.provider.openrouter else "default",
        storage=config.storage.backend,
        max_iterations=config.agent.max_iterations,
        max_tool_calls_per_message=config.agent.max_tool_calls_per_message,
        temperature=config.agent.temperature,
    )


@app.post("/settings")
async def update_settings(
    settings: SettingsUpdate,
    token: str = Depends(verify_api_token)
):
    """Update settings."""
    if config is None:
        raise HTTPException(status_code=503, detail="Config not loaded")
    
    # Update config (in-memory only)
    if settings.provider:
        config.provider.primary = settings.provider
    if settings.max_iterations is not None:
        config.agent.max_iterations = settings.max_iterations
    if settings.max_tool_calls_per_message is not None:
        config.agent.max_tool_calls_per_message = settings.max_tool_calls_per_message
    if settings.temperature is not None:
        config.agent.temperature = settings.temperature
    
    config.to_yaml(config.config_path)
    logger.info(f"Settings updated: {settings}")
    
    return {"success": True, "message": "Settings updated"}


@app.get("/config/yaml")
async def get_config_yaml(token: str = Depends(verify_api_token)):
    """Get full config.yaml content."""
    if config is None:
        raise HTTPException(status_code=503, detail="Config not loaded")
    try:
        yaml_content = config.config_path.read_text()
        return {"content": yaml_content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/config/yaml")
async def update_config_yaml(
    content: dict,
    token: str = Depends(verify_api_token)
):
    """Update config.yaml entirely."""
    if config is None:
        raise HTTPException(status_code=503, detail="Config not loaded")
    try:
        new_yaml = content.get("content", "")
        if not new_yaml:
            raise HTTPException(status_code=400, detail="Missing content")
        config.config_path.write_text(new_yaml)
        # Reload config
        global reload_config
        config.reload()
        logger.info("Config.yaml updated via API")
        return {"success": True, "message": "Config updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Models endpoints

@app.get("/models", response_model=ModelsResponse)
async def get_models(
    provider: str = "openrouter",
    force_refresh: bool = False,
    token: str = Depends(verify_api_token)
):
    """Get available models for a provider."""
    if provider == "openrouter":
        from clawlet.providers.openrouter import OpenRouterProvider
        
        cache = get_models_cache()
        models = cache.get_models(force_refresh=force_refresh)
        cache_info = cache.get_cache_info() or {}
        updated_at = cache_info.get("updated_at", "")
        
        return ModelsResponse(models=models, updated_at=updated_at)
    else:
        raise HTTPException(status_code=400, detail=f"Provider {provider} not supported")


@app.get("/models/cache-info", response_model=CacheInfoResponse)
async def get_cache_info(
    provider: str = "openrouter",
    token: str = Depends(verify_api_token)
):
    """Get models cache information."""
    if provider == "openrouter":
        cache = get_models_cache()
        info = cache.get_cache_info()
        
        if info is None:
            return CacheInfoResponse(model_count=0, is_expired=True)
        
        return CacheInfoResponse(
            updated_at=info.get("updated_at"),
            model_count=info.get("model_count", 0),
            is_expired=info.get("is_expired", False),
        )
    else:
        raise HTTPException(status_code=400, detail=f"Provider {provider} not supported")


# Logs endpoint

@app.get("/logs")
async def get_logs(limit: int = 100, token: str = Depends(verify_api_token)):
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
async def get_console_output(token: str = Depends(verify_api_token)):
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

@app.get("/metrics")
async def get_metrics(token: str = Depends(verify_api_token)):
    """Prometheus-style metrics endpoint."""
    return Response(content=format_prometheus(), media_type="text/plain")


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


async def start_dashboard_server(host: str = "0.0.0.0", port: int = 8000):
    """Start the dashboard API server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


# Run server

def run_server(port: int = 8000):
    """Run the dashboard API server."""
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    run_server()
