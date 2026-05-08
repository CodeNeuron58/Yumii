from langchain_core.tools import tool
from datetime import datetime

@tool
def get_current_time() -> str:
    """Get the current time. Use this when the user asks about the current time."""
    return datetime.now().strftime("%I:%M %p")

# List of all available tools
tools = [get_current_time]
