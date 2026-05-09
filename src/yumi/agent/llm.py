from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field
import os
from yumi.core.config import settings
from yumi.tools import tools
from yumi.agent.personality_manager import personality_manager

# Load personality dynamically from global config
personality = personality_manager.get_current_personality_prompt()

prompt = ChatPromptTemplate.from_messages([
    ("system", personality),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}")
])


class YumiResponse(BaseModel):
    response_text: str = Field(description="The conversational, concise text Yumi will speak out loud.")
    
    # --- EMOTION/MOTION HANDLING (Step 1) ---
    # The LLM is forced to generate these specific fields alongside its text response.
    # The values must be strings corresponding to the mapped keys in the frontend 
    # (see FACIAL_EXPRESSIONS and BODY_MOTIONS in webui/index.html).
    expression: str = Field(description="The generic facial expression label (e.g. smile, angry, sad).")
    motion: str = Field(description="The generic body motion label (e.g. nod, tilthead, fidget).")


# Initialize the LLM with tools bound
base_llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.7,
    api_key=settings.groq_api_key
)

# Bind tools to the LLM
llm_with_tools = base_llm.bind_tools(tools)

# Apply Pydantic schema for structured output (used after tool calls if needed)
llm_structured = base_llm.with_structured_output(YumiResponse)

chain = prompt | llm_with_tools