# src/nexusagent/server.py
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from nexusagent.bus import bus
from nexusagent.config import settings
from nexusagent.sdk import sdk
from nexusagent.worker import worker

# Setup logging
logging.basicConfig(
    level=settings.log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan: Handles startup and shutdown.
    """
    logger.info("Starting NexusAgent Backend...")
    try:
        # 1. Initialize DB
        from nexusagent.db import db_manager

        await db_manager.init_db()
        logger.info("Database initialized.")

        # 2. Connect to NATS
        await bus.connect()

        # 3. Start the Worker as a background task within the same process
        # This co-locates the API and the Worker for simplicity in deployment.
        worker_task = asyncio.create_task(worker.start())
        logger.info("Worker background task started.")

        yield

        # Shutdown
        logger.info("Shutting down NexusAgent Backend...")
        worker_task.cancel()
        await bus.close()

    except Exception as e:
        logger.error(f"Critical error during startup: {e}", exc_info=True)
        raise


app = FastAPI(
    title="NexusAgent API",
    description="Production-grade API for the NexusAgent Orchestrator",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SubmitTaskRequest(BaseModel):
    description: str
    priority: int = 1
    metadata: dict = {}


@app.post("/tasks", response_model=dict)
async def create_task(request: SubmitTaskRequest):
    """
    Submit a new task to the orchestrator.
    """
    try:
        # In a production system, we would save the task to DB here before publishing to NATS
        # but for simplicity, we let the worker handle the first 'create' or
        # we can add a call to task_repo.create_task here.

        # Let's ensure the task is in the DB before it hits NATS
        import uuid

        from nexusagent.db import task_repo

        task_id = str(uuid.uuid4())

        await task_repo.create_task(
            task_id=task_id,
            description=request.description,
            priority=request.priority,
            metadata=request.metadata,
        )

        task_id = await sdk.submit_task(
            {
                "id": task_id,
                "description": request.description,
                "priority": request.priority,
                "metadata": request.metadata,
            }
        )

        return {"task_id": task_id, "status": "submitted"}
    except Exception as e:
        logger.error(f"Error submitting task: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """
    Check the status of a task.
    """
    status = await sdk.get_task_status(task_id)
    return {"task_id": task_id, "status": status}


@app.get("/tasks/{task_id}/result")
async def get_task_result(task_id: str):
    """
    Retrieve the result of a task.
    Returns 404 if result is not yet available.
    """
    result = await sdk.get_result(task_id)
    if result:
        return result
    raise HTTPException(status_code=404, detail="Result not found or timed out.")


@app.get("/health")
async def health_check():
    return {"status": "ok", "nats": "connected" if bus.nc else "disconnected"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.server.api_port)
