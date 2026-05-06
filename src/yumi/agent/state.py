from typing import TypedDict, Annotated
import operator

class MainState(TypedDict):
    input: Annotated[str, operator.add]
    response: Annotated[str, operator.add]
    expression: Annotated[str, lambda x, y: y if y is not None else x]
    motion: Annotated[str, lambda x, y: y if y is not None else x]
    session_id: str
