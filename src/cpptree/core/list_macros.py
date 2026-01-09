from cpptree.models import Node
from typing import Sequence
from pydantic import BaseModel

class MacroInfo(BaseModel):
    affected: list[Node]
    macros: dict[str, str]

def list_macros(nodes: Sequence[Node]) -> list[MacroInfo]:
    pass