from langchain_aws import ChatBedrockConverse
from dotenv import load_dotenv 
import os
import json
from pydantic import BaseModel, Field
from typing import Optional
from langgraph.graph import START, END, StateGraph, MessagesState
from datetime import datetime
# from state import AgentState
from IPython.display import Image, display
from langchain.messages import SystemMessage, HumanMessage
from typing import Literal, TypedDict, List, Annotated
from langgraph.types import Send
from langgraph.prebuilt import ToolNode
from tools import tools
from langgraph.managed import RemainingSteps
from langchain_core.messages import ToolMessage
import operator




load_dotenv()

BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-haiku-4-5-20251001-v1:0")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")

haiku = ChatBedrockConverse(model=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION)

class MedicalAgentState(MessagesState):
    user_query: str
    status: str
    generated_medical_output: str
    generated_normal_output: str
    Feedback: str
    generated_output_valid_or_not: str
    retrieved_chunks: str
    remaining_steps: RemainingSteps
    retry_count: int
    
class Router(BaseModel):
    verdict: Literal["medical_agent", "non_medical_basic_agent"]

class EvaluatorOptimizer(BaseModel):
    grader: Literal["claim_not_tracable", "claim_is_tracable"] = Field(description="Decide if the generated output is tracable to a retrieved chunk or not")
    feedback: str = Field(description="If the generated output is not tracable, point out exactly why it's not tracable")

# LLM Augumentations
router = haiku.with_structured_output(Router)
llm_with_rag = haiku.bind_tools(tools=tools)
Feedback = haiku.with_structured_output(EvaluatorOptimizer)



def Router_function(state: MedicalAgentState):
    verdict = router.invoke([SystemMessage(content="You are an AI Assisted Router, your only task is to validate the incoming user_query and identify whether or not it is a medical-related request or if it's a general non-medical request/query, ONLY respond with 'medical_agent' if it's medical related, and 'non_medical_basic_agent' if it is NOT related."), HumanMessage(content=f"here is the query to give a verdict on: {state['user_query']}")])
    return {"status": verdict.verdict, }

def medical_agent(state: MedicalAgentState):
    # we assign messages with the entire message history
    messages = state["messages"]
    # we assignnew_messages variable to an empty list which will get populated by either the if/else blocks
    new_messages = []
    # we are saying if the history does not exist we want to invoke this instance of  new_messages
    if not messages:
        new_messages = [
            SystemMessage(content="You are an amazing Medical agent. Use the available tools to answer medical queries."),
            HumanMessage(content=f"user query is: {state['user_query']}"),
        ]
    # we are saying if the feedback state exists, instead of using the previous new_message variable we want to use this one to invoke it
    elif state.get("Feedback"):
        new_messages = [HumanMessage(content=f"Revise your previous answer using this feedback, then conduct a fresh retrival with a better more suitable query: {state['Feedback']}")]
    # we then finally call the llm inserting the full message history + the selected new_message depending on the if/else blocks
    response = llm_with_rag.invoke(messages + new_messages)
    retrieved_chunks = []
    for msg in state["messages"]:
        if isinstance(msg, ToolMessage):
            retrieved_chunks.append(msg.content)
            
            
        
    # we return only the final generated rag output into `generated_medical_output`
    # then we return the new_messages block (whether it was if or else's one)  alongside the full response into the message history
    return{
        "generated_medical_output": response.content,
        "messages": new_messages + [response],
        "retrieved_chunks": retrieved_chunks
    }
        

def standard_agent(state: MedicalAgentState):
    #TODO:
    response = haiku.invoke([SystemMessage(content="You are an amazing helpful agent, your job is to assist the user in any way"),
    HumanMessage(content=f"user query is: {state['user_query']}")])
    return {"generated_normal_output": response.content}




def groundness_checker(state: MedicalAgentState):
    response = Feedback.invoke([SystemMessage(content="You are strict groundness checker, your main objective is to validate whether or not the generated medical output is tracable from the retrieved chunks or not, if it IS retrieved, you may respond with claim_is_tracable, otherwise flag it with  claim_not_tracable"), HumanMessage(content=f"here is the generated output: {state['generated_medical_output']}, and here is the retrieved_chunks: {state['retrieved_chunks']} ")])
    return {
        "Feedback": response.feedback,
        "generated_output_valid_or_not": response.grader,
        "retry_count": (state.get("retry_count", 0) + 1),
        }








def fallback_node(state:MedicalAgentState):
    return { "generated_medical_output": "This request could not complete within its allotted execution steps. Cause undetermined — escalating for human review.", "status": "escalated"}

def evaluator_fallback_node(state:MedicalAgentState):
    return{"generated_medical_output": "Unable to verify this claim against retrieved sources after multiple attempts — escalating for human review.", "status": "escalated"}
    

def should_continue(state: MedicalAgentState):
    messages = state["messages"]
    last_message = messages[-1]
    
    if last_message.tool_calls:
        return "needs_tool"
    return "no_tools_needed"

def Response_route(state: MedicalAgentState):
    if state["generated_output_valid_or_not"] == "claim_is_tracable":
        return "SUCESS"
    elif state["remaining_steps"] <= 2:
        return "RECRUSION_LIMIT_REACHED"
    elif state.get("retry_count") >= 3:
        return "MAX_LOOP_REACHED"
    else:
        return "REDO_NEEDED"

def Route(state: MedicalAgentState):
    if state["status"] == "medical_agent":
        return "medical"
    elif state["status"] == "non_medical_basic_agent":
        return "non_medical"
    
    
    
graph = StateGraph(MedicalAgentState)
graph.add_node("eval_fallback_node", evaluator_fallback_node)
graph.add_node("fallback_node", fallback_node)
graph.add_node("medical_agent", medical_agent)
graph.add_node("standard_agent", standard_agent)
graph.add_node("query_validator", Router_function)
graph.add_node("checker", groundness_checker)
graph.add_node("tool_node", ToolNode(tools))

graph.add_edge(START, "query_validator")
graph.add_conditional_edges("query_validator", Route,
    {
        "medical": "medical_agent",
        "non_medical": "standard_agent"
    }
    )
graph.add_conditional_edges("medical_agent", should_continue,
    {
        "needs_tool": "tool_node",
        "no_tools_needed": "checker"
    }
)

graph.add_edge("tool_node", "medical_agent")
graph.add_edge("medical_agent", "checker")
graph.add_conditional_edges("checker", Response_route,
    {
        "SUCESS": END,
        "RECRUSION_LIMIT_REACHED": "fallback_node",
        "MAX_LOOP_REACHED": "eval_fallback_node",
        "REDO_NEEDED": "medical_agent"
    }
)
graph.add_edge("standard_agent", END)
graph.add_edge("fallback_node", END)
graph.add_edge("eval_fallback_node", END)

app = graph.compile()

# img = app.get_graph().draw_mermaid_png()
# with open("medical_workflow.png", "wb") as f:
#     f.write(img)
#     print("FINISHED AND PRINTED SIRE!")

if __name__ == "__main__":

    while True:
        user_input = input("Enter Medical query here: ")
        if user_input.lower() in ["exit", "close"]:
            print("Shutting down system..")
            break
        
        response = app.invoke({"user_query":user_input})
        final_response = response["messages"][-1]
        print(final_response.content)
        
        print("-" * 80)
        
        
        print("THE FEEDBACK FOR THIS QUERY FROM THE GROUNDED AGENT:")
        print("-" * 80)
        print(response["Feedback"])
        
        
        print("THE OUTCOME WAS:")
        print("-" * 80)
        print(response["generated_output_valid_or_not"])
        
    
