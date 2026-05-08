from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from yumi.agent.llm import chain, llm_structured, prompt
from yumi.tools import tools

def chat_node(state):
    user_input = state["input"]
    messages = state.get("messages", [])

    # Invoke the chain with tools bound
    response = chain.invoke({
        "input": user_input,
        "history": messages
    })

    # Check if LLM wants to use tools
    if hasattr(response, 'tool_calls') and response.tool_calls:
        print(f"[Tool Call] LLM wants to use: {[tc['name'] for tc in response.tool_calls]}")
        
        # Execute each tool call
        tool_messages = []
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            # Find and execute the tool
            for tool in tools:
                if tool.name == tool_name:
                    result = tool.invoke(tool_args)
                    print(f"[Tool Result] {tool_name}: {result}")
                    tool_messages.append(
                        ToolMessage(content=result, tool_call_id=tool_call["id"])
                    )
                    break
        
        # Feed tool results back to LLM and get structured response
        # Build message history with tool calls and results
        full_messages = messages + [
            HumanMessage(content=user_input),
            response,  # AIMessage with tool_calls
            *tool_messages
        ]
        
        # Get structured response after tool use
        structured_response = llm_structured.invoke(prompt.format_messages(
            history=messages,
            input=f"Based on the tool results, respond to: {user_input}. Tool results: {[tm.content for tm in tool_messages]}"
        ))
        
        return {
            "response": structured_response.response_text,
            "expression": structured_response.expression,
            "motion": structured_response.motion,
            "messages": [
                HumanMessage(content=user_input),
                AIMessage(content=structured_response.response_text)
            ]
        }

    # No tool calls - get structured response directly
    # Re-invoke with structured output
    structured_response = llm_structured.invoke(prompt.format_messages(
        history=messages,
        input=user_input
    ))

    return {
        "response": structured_response.response_text,
        "expression": structured_response.expression,
        "motion": structured_response.motion,
        "messages": [
            HumanMessage(content=user_input),
            AIMessage(content=structured_response.response_text)
        ]
    }