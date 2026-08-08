from langchain_aws import ChatBedrockConverse
from dotenv import load_dotenv 
import os
import json
import threading
from pydantic import BaseModel, Field, ValidationError
from typing import Optional
from langgraph.graph import START, END, StateGraph, MessagesState
from datetime import datetime
# from state import AgentState
from IPython.display import Image, display
from langchain.messages import SystemMessage, HumanMessage
from typing import Literal, TypedDict, List, Annotated
from langgraph.types import Send
from langgraph.prebuilt import ToolNode
from .tools import tools, retrieve_clinical_evidence
from langgraph.managed import RemainingSteps
from langchain_core.messages import ToolMessage, AIMessage
from langchain.agents import create_agent
from langchain.agents.structured_output import StructuredOutputValidationError
from .states import MedicalAgentState, EvaluatorOptimizer, Router, MedicalAnswer

# The embedding model (MedEmbed-small) is fully cached on disk; never let the
# HuggingFace hub re-validate it at runtime (that logged 96 HEAD/GET requests).
os.environ.setdefault("HF_HUB_OFFLINE", "1")

system_prompt_router = open("src/prompts/AgentDecisionSystemPrompt.md").read()
system_prompt_medical = open("src/prompts/MedicalSystemMessage.md").read()



load_dotenv()

BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-haiku-4-5-20251001-v1:0")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")

haiku = ChatBedrockConverse(model=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION, temperature=0)
haiku_converstaional = ChatBedrockConverse(model=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION, temperature=0.7)



# LLM Augumentations
router = haiku.with_structured_output(Router)
llm_with_rag = haiku.bind_tools(tools=tools + [MedicalAnswer], tool_choice="any")
Feedback = haiku.with_structured_output(EvaluatorOptimizer)
medical_answer_model = haiku.with_structured_output(MedicalAnswer)

medical_agent = create_agent(
    model=haiku,
    tools=tools,
    response_format=MedicalAnswer,
)




def Router_function(state: MedicalAgentState):
    verdict = router.invoke([SystemMessage(content=system_prompt_router),
HumanMessage(content=f"here is the query to give a verdict on: {state['user_query']}")])
    return {"status": verdict.verdict, }

def medical_agent_node(state: MedicalAgentState):
    # Collapsed single-pass pipeline: exactly ONE forced retrieval followed by
    # ONE structured MedicalAnswer call, instead of the ReAct tool loop.
    # Cuts the medical path from (retrieval + 2 model calls + tool round-trips)
    # to just (retrieval + 1 answer call).
    messages = state["messages"]
    feedback = state.get("Feedback")

    # 1) Forced retrieval -- always happens, exactly once, before answering.
    if feedback:
        retrieval_query = (
            f"Revise your previous answer using this feedback, then conduct a fresh "
            f"retrieval with a better more suitable query: {feedback}"
        )
    else:
        retrieval_query = state["user_query"]
    chunks = retrieve_clinical_evidence.invoke({"query": retrieval_query, "k": 5})

    # 2) ONE structured MedicalAnswer call with the retrieved chunks in context.
    new_messages = [
        SystemMessage(content=system_prompt_medical),
        HumanMessage(content=f"user query is: {state['user_query']}"),
    ]
    if feedback:
        new_messages.append(
            HumanMessage(content=f"Checker feedback on your previous answer, revise accordingly: {feedback}")
        )
    new_messages.append(
        HumanMessage(
            content="The retrieve_clinical_evidence tool has already been called and "
            "its output is provided below. Use ONLY this evidence to compose your "
            f"MedicalAnswer:\n\n{chunks}"
        ),
    )
    prompt = messages + new_messages

    answer = None
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            answer = medical_answer_model.invoke(prompt)
            break
        except (StructuredOutputValidationError, ValidationError) as exc:
            last_error = exc
            if attempt < 2:
                # Feed the schema error back so the model can correct it
                # (e.g. an empty claims list) instead of re-invoking the
                # identical prompt.
                prompt = prompt + [
                    HumanMessage(
                        content=(
                            "Your previous structured output failed schema "
                            f"validation: {exc}. Fix the error and return a "
                            "valid MedicalAnswer."
                        )
                    )
                ]
    if answer is None:
        # 3 failed attempts: escalate like evaluator_fallback_node so one bad
        # question can't crash the whole run (the eval harness has no per-case
        # guard around app.invoke).
        return {
            "generated_medical_output": (
                "Unable to produce a schema-valid answer after multiple attempts "
                "— escalating for human review."
            ),
            "messages": prompt,
            "retrieved_chunks": [chunks],
        }

    return {
        "generated_medical_output": answer.answer,
        "messages": prompt + [AIMessage(content=answer.answer)],
        "retrieved_chunks": [chunks],
    }
        

def _content_to_text(content) -> str:
    """Extract plain text from a LangChain content value, which may be a plain
    string or a list of typed blocks (e.g. [{'type': 'text', 'text': ...}]).
    Bedrock Converse streams the block-list form, so joining raw values
    (''.join) crashes with 'expected str instance, list found'."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def CONVERSATION_AGENT(state: MedicalAgentState):
    chunks = []
    for chunk in haiku_converstaional.stream([SystemMessage(content="You are an amazing helpful agent, your job is to assist the user in any way keeping your answers short, professional and concise"),
    HumanMessage(content=f"user query is: {state['user_query']}")]):
        if chunk.content:
            chunks.append(_content_to_text(chunk.content))
    return {"generated_normal_output": "".join(chunks)}




def groundness_checker(state: MedicalAgentState):
    if not state.get("retrieved_chunks"):
        return {
            "Feedback": "No chunks were retrieved before generating an answer — retrieval must be attempted.",
            "generated_output_valid_or_not": "claim_not_tracable",
            "retry_count": state.get("retry_count", 0) + 1,
        }

    response = Feedback.invoke([
        SystemMessage(content="You are strict groundness checker, your main objective is to validate whether or not the generated medical output is tracable from the retrieved chunks or not, if it IS retrieved AND IS PRECIESLEY RELEVANT in terms of information, you may respond with claim_is_tracable,Claims about the agent's own limitations, disclaimers, refusal to prescribe/diagnose, or statements that the retrieved evidence does not cover a topic should be excluded from traceability checking. Only verify the medical/factual claims."),
        HumanMessage(content=f"here is the generated output: {state['generated_medical_output']}, and here is the retrieved_chunks: {state['retrieved_chunks']}")
    ])

    return {
        "Feedback": response.feedback,
        "generated_output_valid_or_not": response.grader,
        "retry_count": (state.get("retry_count", 0) + 1),
    }


def synthesizer(state: MedicalAgentState):
    response = haiku_converstaional.invoke([SystemMessage(content=f"Take these answers and only format them beautifully so you return the output back to the user: {state['generated_medical_output']}")])
    return {"final_answer": _content_to_text(response.content)}








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
    status = state["status"]
    if status == "medical_agent":
        return "medical"
    # conversational_agent and web_search_agent both go to the standard agent;
    # anything unexpected also falls back there so the router never returns None
    return "non_medical"
    
    
    
graph = StateGraph(MedicalAgentState)
graph.add_node("eval_fallback_node", evaluator_fallback_node)
graph.add_node("fallback_node", fallback_node)
graph.add_node("medical_agent", medical_agent_node)
graph.add_node("standard_agent", CONVERSATION_AGENT)
graph.add_node("query_validator", Router_function)
graph.add_node("checker", groundness_checker)
graph.add_node("synthesizer", synthesizer)

graph.add_edge(START, "query_validator")
graph.add_conditional_edges("query_validator", Route,
    {
        "medical": "medical_agent",
        "non_medical": "standard_agent"
    }
    )


graph.add_edge("medical_agent", "checker")
graph.add_conditional_edges("checker", Response_route,
    {
        "SUCESS": "synthesizer",
        "RECRUSION_LIMIT_REACHED": "fallback_node",
        "MAX_LOOP_REACHED": "eval_fallback_node",
        "REDO_NEEDED": "medical_agent"
    }
)
graph.add_edge("standard_agent", END)
graph.add_edge("fallback_node", END)
graph.add_edge("eval_fallback_node", END)
graph.add_edge("synthesizer", END)

app = graph.compile()


def _warm_up():
    """Pre-warm the Bedrock connection and the vector store so the first real
    request doesn't pay the ~60s cold start (Bedrock times out after ~4min
    idle; HF re-validates the embedding model against the hub)."""
    try:
        haiku.invoke([HumanMessage(content="ping")])
    except Exception:
        pass
    try:
        retrieve_clinical_evidence.invoke({"query": "dental infection", "k": 1})
    except Exception:
        pass


threading.Thread(target=_warm_up, daemon=True).start()

img = app.get_graph().draw_mermaid_png()
with open("medical_workflow.png", "wb") as f:
    f.write(img)
    print("FINISHED AND PRINTED SIRE!")

if __name__ == "__main__":

    while True:
        user_input = input("Enter Medical query here: ")
        if user_input.lower() in ["exit", "close"]:
            print("Shutting down system..")
            break
        
        response = app.invoke({"user_query":user_input})
        
        print("-" * 80)
        
        
        print(response.get("generated_medical_output", ""))
        
        
        print("-" * 80)
        
        print(response.get("generated_normal_output", "No normal output was added."))
        
        
        print("-" * 80)
        
        
        print("THE FEEDBACK FOR THIS QUERY FROM THE GROUNDED AGENT:")
        
        
        print("-" * 80)
        print(response.get("Feedback", ""))
        print("-" * 80)
        
        
        print("THE OUTCOME WAS:")
        
        
        print("-" * 80)
        
        
        print(response.get("generated_output_valid_or_not", ""))
