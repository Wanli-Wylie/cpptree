from cpptree.models import Node
from typing import Sequence
from functools import singledispatch

@singledispatch
def tostring(node: Sequence[Node] | Node | dict[str, Sequence[Node]]) -> str:
    pass

@tostring.register(Sequence[Node])
def _tostring_nodes(nodes: Sequence[Node]) -> str:
    pass

@tostring.register(Node)
def _tostring_node(node: Node) -> str:
    pass

@tostring.register(dict[str, Sequence[Node]])
def _tostring_files(files: dict[str, Sequence[Node]]) -> str:
    # Handle include statements
    pass