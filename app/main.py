from fastapi import FastAPI
from pydantic import BaseModel
from src.agent import app as agent_app
from typing import Optional
from uuid import uuid4
from ag_ui_langgraph import add_langgraph_fastapi_endpoint



class RequestQuery(BaseModel):
    query: str
    
class RequestOutput(BaseModel):
    medical_output: Optional[str]
    conversational_output: Optional[str]
    feedback: Optional[str]
    
config = {"configurable": {"thread_id": str(uuid4())}}

app = FastAPI()

add_langgraph_fastapi_endpoint(
    app,
    agent_app,
     path="/ag-ui"
)

@app.post("/query", response_model=RequestOutput)
async def MedicalAgent(payload: RequestQuery):
    response = agent_app.invoke({
        "user_query": payload.query
    }, config=config)
    return RequestOutput(
        medical_output = response.get("generated_medical_output", ""),
        conversational_output = response.get("generated_normal_output", ""),
        feedback = response.get("Feedback", "No Feedback Needed")
    )