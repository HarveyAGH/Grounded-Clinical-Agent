from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from src.agent import app as agent_app
from src.states import MedicalAnswer
from typing import Optional, List
from uuid import uuid4
from pathlib import Path
from ag_ui_langgraph import add_langgraph_fastapi_endpoint

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
STATIC_DIR = Path(__file__).parent / "static"

class RequestQuery(BaseModel):
    query: str
    
class RequestOutput(BaseModel):
    status: Optional[str] = None
    medical_output: Optional[MedicalAnswer] = None
    conversational_output: Optional[str] = None
    feedback: Optional[str] = None
    groundness_verdict: Optional[str] = None
    retrieved_chunks: Optional[List[str]] = None
    retry_count: Optional[int] = 0
    


app = FastAPI(title="Grounded Clinical Agent API & UI")

if FRONTEND_DIST.exists() and (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")
elif STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

add_langgraph_fastapi_endpoint(
    app,
    agent_app,
    path="/ag-ui"
)

@app.get("/", include_in_schema=False)
async def serve_index():
    if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
        return FileResponse(FRONTEND_DIST / "index.html")
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Grounded Clinical Agent API is running. Access /ag-ui or POST /query."}

@app.post("/query", response_model=RequestOutput)
async def MedicalAgent(payload: RequestQuery):
    config = {"configurable": {"thread_id": str(uuid4())}}
    response = agent_app.invoke({
        "user_query": payload.query
    }, config=config)
    return RequestOutput(
        status = response.get("status"),
        medical_output = response.get("medical_output"),
        conversational_output = response.get("conversational_output", ""),
        feedback = response.get("Feedback", "No Feedback Needed"),
        groundness_verdict = response.get("generated_output_valid_or_not"),
        retrieved_chunks = response.get("retrieved_chunks", []),
        retry_count = response.get("retry_count", 0)
    )