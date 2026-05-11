from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from yumi.core.config import settings
from yumi.tools import tools
from langchain.agents import create_agent

class YumiResponse(BaseModel):
    response_text: str = Field(description="The conversational, concise text Yumi will speak out loud.")
    expression: str = Field(description="The generic facial expression label (e.g. smile, angry, sad).")
    motion: str = Field(description="The generic body motion label (e.g. nod, tilthead, fidget).")

# Initialize the base LLM
base_llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.7,
    api_key=settings.groq_api_key
)

# Create the unified agent that natively handles tool execution and structured output
# The system prompt is dynamically passed on each invocation in nodes.py, 
# so we do not pass a static system_prompt here.
agent = create_agent(
    model=base_llm,
    tools=tools,
    response_format=YumiResponse
)
