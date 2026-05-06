from langchain_core.runnables.history import RunnableWithMessageHistory
from yumi.agent.memory.chat_history import get_session_history
from yumi.agent.llm import chain
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.messages import AIMessage

# We define a custom wrapper runnable that invokes the original chain (which returns YumiResponse)
# but for the chat history, we need it to return an AIMessage or string so LangChain can save it properly.
def structure_to_text_history_wrapper(input_dict, config=None):
    # 1. Run the base chain to get the structured model
    result = chain.invoke(input_dict, config=config)
    # 2. Return a dictionary that the history runnable can use
    return {
        "full_response": result, 
        "text_for_history": result.response_text 
    }

wrapper_chain = RunnableLambda(structure_to_text_history_wrapper)

# We wrap the History keeping mechanism around our wrapper
chat_chain = RunnableWithMessageHistory(
    wrapper_chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
    # Tell the history runnable to ONLY save the 'text_for_history' key into the DB
    history_factory_config=[],
    output_messages_key="text_for_history"
)

def chat_node(state):
    session_id = state["session_id"]
    user_input = state["input"]

    # This invoke now returns {"full_response": YumiResponse, "text_for_history": str}
    # and the history tracer successfully stores the text string.
    response_wrapper = chat_chain.invoke(
        {"input": user_input},
        config={"configurable": {"session_id": session_id}}
    )
    
    # We unwrap the full Pydantic model response
    response_obj = response_wrapper["full_response"]

    # Return the dictionary representing all dimensions of the LLM state output
    return {
        "response": response_obj.response_text,
        "expression": response_obj.expression,
        "motion": response_obj.motion
    }