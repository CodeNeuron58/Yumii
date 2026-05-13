from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field
from yumi.core.config import settings
from yumi.tools import tools
from langgraph.prebuilt import create_react_agent

class YumiResponse(BaseModel):
    response_text: str = Field(description="The conversational, concise text Yumi will speak out loud.")
    expression: str = Field(description="The generic facial expression label (e.g. smile, angry, sad).")
    motion: str = Field(description="The generic body motion label (e.g. nod, tilthead, fidget).")

# Initialize the base LLM based on provider
provider = settings.llm_provider.lower()

if provider == "openai":
    base_llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.7,
        api_key=settings.openai_api_key
    )
elif provider == "anthropic":
    base_llm = ChatAnthropic(
        model="claude-3-5-sonnet-latest",
        temperature=0.7,
        api_key=settings.anthropic_api_key
    )
else:
    # Default to Groq
    base_llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.7,
        api_key=settings.groq_api_key
    )

# Create the standard ReAct agent that handles tool execution
# We will use .with_structured_output() in nodes.py to extract the final formatting
agent = create_react_agent(
    model=base_llm,
    tools=tools
)
