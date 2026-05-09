from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from yumi.agent.llm import chain, llm_structured, prompt
from yumi.tools import tools
from yumi.agent.personality_manager import personality_manager
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

def check_personality_switch(user_input: str) -> tuple[bool, str | None]:
    """Check if user wants to switch personality. Returns (is_switch, new_personality)."""
    user_input_lower = user_input.lower().strip()
    
    personalities = personality_manager.list_personalities()
    
    # Check for personality switch commands
    for personality in personalities:
        if user_input_lower in [f"switch to {personality}", f"be {personality}", f"become {personality}", personality]:
            return True, personality
    
    return False, None

def chat_node(state):
    user_input = state["input"]
    messages = state.get("messages", [])

    # Check for personality switch
    is_switch, new_personality = check_personality_switch(user_input)
    if is_switch:
        from yumi.core.global_config import update_global_config
        update_global_config("PERSONALITY", new_personality)
        
        # Reload personality and update prompt
        new_personality_prompt = personality_manager.load_personality(new_personality)
        new_prompt = ChatPromptTemplate.from_messages([
            ("system", new_personality_prompt),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])
        
        # Acknowledge personality switch (using new personality)
        from langchain_core.messages import SystemMessage
        import json
        structured_response = llm_structured.invoke(new_prompt.format_messages(
            history=[SystemMessage(content="The user just asked you to switch personalities. Acknowledge this change briefly and warmly in your new personality style.")],
            input="Acknowledge the personality change"
        ))
        
        return {
            "response": structured_response.response_text,
            "expression": structured_response.expression,
            "motion": structured_response.motion,
            "messages": []  # Don't add personality switch to message history
        }

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