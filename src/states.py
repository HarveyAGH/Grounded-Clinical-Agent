
from pydantic import BaseModel, Field
from langgraph.graph import  MessagesState
from datetime import datetime
from typing import Literal, List
from langgraph.managed import RemainingSteps
from pydantic import BaseModel, Field




class MedicalAgentState(MessagesState):
    user_query: str 
    status: str
    generated_medical_output: str | None
    generated_normal_output: str | None
    Feedback: str | None
    generated_output_valid_or_not: str | None
    retrieved_chunks: str
    remaining_steps: RemainingSteps
    retry_count: int
    final_answer: str | None
    
class Router(BaseModel):
    verdict: Literal["medical_agent", "conversational_agent"]
    reasoning: str = Field(description="Your reasoning for selecting this verdict with 1 line")
    confidence: float = Field(description=" Value between 0.0 and 1.0 indicating your confidence in this decision")
    
    
    
    

class EvaluatorOptimizer(BaseModel):
    feedback: str = Field(
        description="Go through each claim in the generated output one by one and check whether it is explicitly supported by the retrieved chunks. Name any claim that is not traceable and explain why."
    )
    grader: Literal["claim_not_tracable", "claim_is_tracable"] = Field(
        description="return claim_is_tracable if the medical/factual claims are supported by the retrieved chunks, ignoring refusal/disclaimer/absence statements. Only return claim_not_tracable if a substantive medical claim is unsupported"
    )









class CitedClaim(BaseModel):
    claim: str = Field(..., description="A single factual claim extracted from the answer")
    citation: str = Field(..., description="Source identifier, e.g. '[Source 1: filename]'")
    confidence: float = Field(
        ...,
        description="Confidence that this claim is directly supported by the citation, as a number between 0.0 and 1.0"
    )

class MedicalAnswer(BaseModel):
    answer: str = Field(
        ..., 
        description="Complete answer composed ONLY of cited claims, do not make it super long and make it short"
    )
    claims: List[CitedClaim] = Field(
        ..., 
        min_length=1,
        description="List of individual claims, each with its own citation (i line, formatted beautifully)"
    )
    disclaimer: str = Field(
        default="This information is for educational purposes only and does not constitute medical advice."
    )