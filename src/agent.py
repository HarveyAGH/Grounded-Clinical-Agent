from langchain_aws import ChatBedrockConverse
from dotenv import load_dotenv 
import os
from langgraph.graph import START, END, StateGraph
from langchain.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import ToolNode
from .tools import tools
from langchain_core.messages import ToolMessage
from langchain.agents import create_agent
from langchain.agents.structured_output import StructuredOutputValidationError
from .states import MedicalAgentState, EvaluatorOptimizer, Router, MedicalAnswer, CitedClaim
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

system_prompt_router = open("src/prompts/AgentDecisionSystemPrompt.md").read()
system_prompt_medical = open("src/prompts/MedicalSystemMessage.md").read()



load_dotenv()

BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-haiku-4-5-20251001-v1:0")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")
DB_URI = os.environ["DB_URI"]

haiku = ChatBedrockConverse(model=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION, temperature=0)
haiku_converstaional = ChatBedrockConverse(model=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION, temperature=0.7)

pool = ConnectionPool(conninfo=DB_URI, max_size=20, check=ConnectionPool.check_connection, kwargs={"autocommit": True, "row_factory": dict_row})
checkpointer = PostgresSaver(pool)
checkpointer.setup()



# LLM Augumentations
router = haiku.with_structured_output(Router)
Feedback = haiku.with_structured_output(EvaluatorOptimizer)

medical_agent = create_agent(
    model=haiku,
    tools=tools,
    system_prompt=system_prompt_medical,
    response_format=MedicalAnswer,
)




def Router_function(state: MedicalAgentState):
    verdict = router.invoke([
        SystemMessage(content=system_prompt_router),
        HumanMessage(content=f"here is the query to give a verdict on: {state['user_query']}")
    ])
    return {"status": verdict.verdict}

def medical_agent_node(state: MedicalAgentState):
    query = state["user_query"]
    if state.get("Feedback"):
        query += f"\n\n[Correction Feedback]: Revise your previous answer addressing this critique: {state['Feedback']}"

    response = medical_agent.invoke({"messages": [HumanMessage(content=query)]})
    retrieved_chunks = [
        msg.content for msg in response["messages"] if isinstance(msg, ToolMessage)
    ]

    return {
        "medical_output": response["structured_response"],
        "messages": response["messages"],
        "retrieved_chunks": retrieved_chunks,
    }
        

def CONVERSATION_AGENT(state: MedicalAgentState):
    response = haiku_converstaional.invoke([
        SystemMessage(content="You are an amazing helpful agent, your job is to assist the user in any way"),
        HumanMessage(content=f"user query is: {state['user_query']}")
    ])
    return {"conversational_output": response.content}




def groundness_checker(state: MedicalAgentState):
    if not state.get("retrieved_chunks"):
        return {
            "Feedback": "No chunks were retrieved before generating an answer, retrieval must be attempted.",
            "generated_output_valid_or_not": "claim_not_tracable",
            "retry_count": state.get("retry_count", 0) + 1,
        }

    medical_output = state.get("medical_output")
    if hasattr(medical_output, "model_dump_json"):
        output_for_eval = medical_output.model_dump_json()
    else:
        output_for_eval = str(medical_output)

    response = Feedback.invoke([
        SystemMessage(content="You are strict groundness checker, your main objective is to validate whether or not the generated medical output is tracable from the retrieved chunks or not, if it IS retrieved AND IS PRECIESLEY RELEVANT in terms of information, you may respond with claim_is_tracable, Claims about the agent's own limitations, disclaimers, refusal to prescribe/diagnose, or statements that the retrieved evidence does not cover a topic should be excluded from traceability checking. Only verify the medical/factual claims."),
        HumanMessage(content=f"here is the generated output: {output_for_eval}, and here is the retrieved_chunks: {state['retrieved_chunks']}")
    ])

    return {
        "Feedback": response.feedback,
        "generated_output_valid_or_not": response.grader,
        "retry_count": (state.get("retry_count", 0) + 1),
    }








def fallback_node(state: MedicalAgentState):
    return {
        "medical_output": MedicalAnswer(
            answer="This request could not complete within its allotted execution steps. Cause undetermined — escalating for human review.",
            claims=[CitedClaim(claim="Escalated for human review due to step limit.", citation="System Fallback", confidence=1.0)],
            disclaimer="This information is for educational purposes only and does not constitute medical advice."
        ),
        "status": "escalated"
    }

def evaluator_fallback_node(state: MedicalAgentState):
    return {
        "medical_output": MedicalAnswer(
            answer="Unable to verify this claim against retrieved sources after multiple attempts — escalating for human review.",
            claims=[CitedClaim(claim="Escalated for human review due to verification limits.", citation="System Fallback", confidence=1.0)],
            disclaimer="This information is for educational purposes only and does not constitute medical advice."
        ),
        "status": "escalated"
    }
    

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
    return "non_medical"
    
    
    
graph = StateGraph(MedicalAgentState)
graph.add_node("eval_fallback_node", evaluator_fallback_node)
graph.add_node("fallback_node", fallback_node)
graph.add_node("medical_agent", medical_agent_node)
graph.add_node("standard_agent", CONVERSATION_AGENT)
graph.add_node("query_validator", Router_function)
graph.add_node("checker", groundness_checker)

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
        "SUCESS": END,
        "RECRUSION_LIMIT_REACHED": "fallback_node",
        "MAX_LOOP_REACHED": "eval_fallback_node",
        "REDO_NEEDED": "medical_agent"
    }
)
graph.add_edge("standard_agent", END)
graph.add_edge("fallback_node", END)
graph.add_edge("eval_fallback_node", END)


config = {"configurable": {"thread_id": "2"}}

app = graph.compile(checkpointer=checkpointer)

if __name__ == "__main__":

    while True:
        user_input = input("Enter Medical query here: ")
        if user_input.lower() in ["exit", "close"]:
            print("Shutting down system..")
            break
        
        response = app.invoke({"user_query": user_input}, config=config)
        
        print("-" * 80)
        if response.get("medical_output"):
            med = response["medical_output"]
            print(f"MEDICAL ANSWER:\n{med.answer}\n")
            print("CITED CLAIMS:")
            for c in med.claims:
                print(f"  - Claim: {c.claim} | Citation: {c.citation} | Confidence: {c.confidence}")
            print(f"\nDISCLAIMER: {med.disclaimer}")
        
        if response.get("conversational_output"):
            print(f"CONVERSATIONAL OUTPUT:\n{response['conversational_output']}")
            
        print("-" * 80)
        if response.get("Feedback"):
            print(f"FEEDBACK: {response['Feedback']}")
        if response.get("generated_output_valid_or_not"):
            print(f"GROUNDNESS VERDICT: {response['generated_output_valid_or_not']}")
        print("-" * 80)
        
        
        