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
from .states import MedicalAgentState, EvaluatorOptimizer, Router, MedicalAnswer

system_prompt_router = open("src/prompts/AgentDecisionSystemPrompt.md").read()
system_prompt_medical = open("src/prompts/MedicalSystemMessage.md").read()



load_dotenv()

BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-haiku-4-5-20251001-v1:0")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")

haiku = ChatBedrockConverse(model=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION, temperature=0)
haiku_converstaional = ChatBedrockConverse(model=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION, temperature=0.7)



# LLM Augumentations
router = haiku.with_structured_output(Router)
Feedback = haiku.with_structured_output(EvaluatorOptimizer)

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
    # we assign messages with the entire message history
    messages = state["messages"]
    # we assignnew_messages variable to an empty list which will get populated by either the if/else blocks
    new_messages = []
    # we are saying if the history does not exist we want to invoke this instance of  new_messages
    if not messages:
        new_messages = [
            SystemMessage(content=system_prompt_medical),
            HumanMessage(content=f"user query is: {state['user_query']}"),
        ]
    # we are saying if the feedback state exists, instead of using the previous new_message variable we want to use this one to invoke it
    elif state.get("Feedback"):
        new_messages = [HumanMessage(content=f"Revise your previous answer using this feedback, then conduct a fresh retrival with a better more suitable query: {state['Feedback']}")]
    # we then finally call the llm inserting the full message history + the selected new_message depending on the if/else blocks
    prompt = messages + new_messages
    for attempt in range(3):
        try:
            response = medical_agent.invoke({"messages": prompt})
            break
        except StructuredOutputValidationError:
            if attempt == 2:
                raise
    answer = response["structured_response"]
    retrieved_chunks = []
    for msg in state["messages"]:
        if isinstance(msg, ToolMessage):
            retrieved_chunks.append(msg.content)
            
            
        
    # we return only the final generated rag output into `generated_medical_output`
    # then we return the new_messages block (whether it was if or else's one)  alongside the full response into the message history
    return{
        "generated_medical_output": answer.answer,
        "messages": response["messages"],
        "retrieved_chunks": retrieved_chunks
    }
        

def CONVERSATION_AGENT(state: MedicalAgentState):
    #TODO:
    response = haiku_converstaional.invoke([SystemMessage(content="You are an amazing helpful agent, your job is to assist the user in any way"),
    HumanMessage(content=f"user query is: {state['user_query']}")])
    return {"generated_normal_output": response.content}




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








def fallback_node(state:MedicalAgentState):
    return { "generated_medical_output": "This request could not complete within its allotted execution steps. Cause undetermined — escalating for human review.", "status": "escalated"}
def evaluator_fallback_node(state:MedicalAgentState):
    return{"generated_medical_output": "Unable to verify this claim against retrieved sources after multiple attempts — escalating for human review.", "status": "escalated"}
    

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
graph.add_node("tool_node", ToolNode(tools))

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

app = graph.compile()

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
