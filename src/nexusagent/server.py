from fastapi import FastAPI
from nexusagent.sdk import NexusSDK
from nexusagent.models import TaskSchema, ResultSchema

app = FastAPI()
sdk = NexusSDK()

@app.post("/tasks", response_model=ResultSchema)
async def create_task(task: TaskSchema):
    return sdk.submit_task(task)

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    return {"status": sdk.get_status(task_id)}
