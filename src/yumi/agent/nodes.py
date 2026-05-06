from langchain_core.messages import HumanMessage, AIMessage
from yumi.agent.llm import chain

def chat_node(state):
    user_input = state["input"]
    messages = state.get("messages", [])

    # Invoke the chain with history from state
    result = chain.invoke({
        "input": user_input,
        "history": messages
    })

    # Return updated state with new messages
    return {
        "response": result.response_text,
        "expression": result.expression,
        "motion": result.motion,
        "messages": [
            HumanMessage(content=user_input),
            AIMessage(content=result.response_text)
        ]
    }