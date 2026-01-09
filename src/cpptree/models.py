from __future__ import annotations
from typing import Literal, Union, Optional
from pydantic import BaseModel, Field, model_validator, ConfigDict
from __future__ import annotations

import re
from typing import Literal, Union, Optional
from pydantic import BaseModel, Field, model_validator

# -----------------------
# helpers (pure functions)
# -----------------------
_C_IDENT_PREFIX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*")
_C_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def _strip_hash_prefix(raw: str) -> str:
    # normalize: allow leading spaces, require '#'
    s = raw.lstrip()
    if not s.startswith("#"):
        raise ValueError(f"directive raw must start with '#': {raw!r}")
    return s

def _expect_directive(raw: str, expected: str) -> None:
    """
    expected: 'if'|'ifdef'|'ifndef'|'elif'|'include'|'define'|'undef'|'pragma'|'error'
    Accepts forms like '# if', '#if', '#   ifdef', etc.
    """
    s = _strip_hash_prefix(raw)[1:].lstrip()   # drop '#', strip spaces
    m = _C_IDENT_PREFIX.match(s)
    # directive keyword is the first token after '#'
    kw =  m.group(0) if m else ""
    if kw != expected:
        raise ValueError(f"raw directive keyword mismatch: expected #{expected}, got #{kw} in {raw!r}")

def _require_nonempty_condition(cond: str, *, where: str) -> None:
    if cond is None or cond.strip() == "":
        raise ValueError(f"{where}: condition must be non-empty")

def _require_identifier(cond: str, *, where: str) -> None:
    _require_nonempty_condition(cond, where=where)
    c = cond.strip()
    if not _C_IDENT.match(c):
        raise ValueError(f"{where}: expected C identifier for ifdef/ifndef condition, got {cond!r}")

# -----------------------
# models
# -----------------------

class TextBlock(BaseModel):
    kind: Literal["text"] = "text"
    content: str
    
    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def _validate_text(self) -> "TextBlock":
        # allow empty text blocks if you want; disallow if not
        if self.content is None:
            raise ValueError("TextBlock.content must not be None")
        return self


class DirectiveNode(BaseModel):
    """Generic directive node for include, define, undef, error, pragma, etc."""
    kind: Literal["include", "define", "undef", "pragma", "error"]
    raw: str  # Original raw line

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def _validate_directive(self) -> "DirectiveNode":
        if self.raw is None or self.raw.strip() == "":
            raise ValueError("DirectiveNode.raw must be non-empty")

        # enforce that raw matches kind (Legality: structural consistency)
        _expect_directive(self.raw, self.kind)

        return self


# forward-declare Node for type checking in pydantic models
Node = Union["TextBlock", "DirectiveNode", "ConditionalGroup"]


class ConditionalBranch(BaseModel):
    """Represents a branch of #if / #ifdef / #ifndef / #elif"""
    kind: Literal["if", "ifdef", "ifndef", "elif"]
    condition: str
    body: list[Node]
    raw: str  # '#if CONDITION'

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def _validate_branch(self) -> "ConditionalBranch":
        # raw basic
        if self.raw is None or self.raw.strip() == "":
            raise ValueError("ConditionalBranch.raw must be non-empty")

        # raw directive keyword must match kind
        _expect_directive(self.raw, self.kind)

        # condition legality by kind
        if self.kind in ("if", "elif"):
            _require_nonempty_condition(self.condition, where=f"ConditionalBranch(kind={self.kind})")
        else:  # ifdef/ifndef
            _require_identifier(self.condition, where=f"ConditionalBranch(kind={self.kind})")

        # body must exist (can be empty, but not None)
        if self.body is None:
            raise ValueError("ConditionalBranch.body must not be None")

        return self

class ConditionalGroup(BaseModel):
    kind: Literal["conditional_group"] = "conditional_group"
    entry: ConditionalBranch
    elifs: Optional[list[ConditionalBranch]] = None
    else_body: Optional[list[Node]] = None
    else_raw: Optional[str] = None
    endif_raw: str = "#endif"

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def _validate_group(self) -> "ConditionalGroup":
        # 1) entry must be an opening branch (Legality: cannot be elif)
        if self.entry.kind not in ("if", "ifdef", "ifndef"):
            raise ValueError(f"ConditionalGroup.entry.kind must be one of if/ifdef/ifndef, got {self.entry.kind!r}")

        # 2) elifs must all be kind='elif' if present (Legality: cannot be if/ifdef/ifndef)
        if self.elifs is not None:
            for i, b in enumerate(self.elifs):
                if b.kind != "elif":
                    raise ValueError(f"ConditionalGroup.elifs[{i}].kind must be 'elif', got {b.kind!r}")

        # 3) else_body exists => it's a list (can be empty) and must not be None
        if self.else_body is not None and not isinstance(self.else_body, list):
            raise ValueError("ConditionalGroup.else_body must be a list when provided")

        # 4) (optional but very useful) forbid nested elif inside entry/elif bodies as raw directives
        # You said you require ConditionalGroup合法; a common footgun is letting stray '#elif/#else/#endif'
        # survive into TextBlock/DirectiveNode and break invariants.
        # We enforce: inside any branch body, there must not be DirectiveNode(kind in include/define/...) that is actually #elif/#else/#endif.
        # Since DirectiveNode.kind doesn't include those, they would have to sneak in as TextBlock content or malformed DirectiveNode.raw.
        # We can cheaply guard: no body item may be a ConditionalBranch / raw conditional directive.
        # (Your schema doesn't allow those directly, so this is mostly a sanity check.)
        def _walk(nodes: list[Node]) -> None:
            for n in nodes:
                if isinstance(n, DirectiveNode):
                    # ensure it isn't a conditional keyword disguised
                    s = _strip_hash_prefix(n.raw)[1:].lstrip()
                    kw = s.split(None, 1)[0] if s else ""
                    if kw in ("if", "ifdef", "ifndef", "elif", "else", "endif"):
                        raise ValueError(f"Illegal conditional directive inside body as DirectiveNode: {n.raw!r}")
                elif isinstance(n, ConditionalGroup):
                    # nested groups are fine
                    continue
                elif isinstance(n, TextBlock):
                    # If you want to disallow stray '#elif/#else/#endif' inside text blocks,
                    # you need tokenization; string check would be too fragile. So we don't.
                    continue
                else:
                    raise ValueError(f"Unknown node type in body: {type(n)}")

        _walk(self.entry.body)
        if self.elifs:
            for b in self.elifs:
                _walk(b.body)
        if self.else_body is not None:
            _walk(self.else_body)

        return self


class FileRoot(BaseModel):
    path: str
    items: list[Node]

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def _validate_root(self) -> "FileRoot":
        if self.path is None or self.path.strip() == "":
            raise ValueError("FileRoot.path must be non-empty")

        if self.items is None:
            raise ValueError("FileRoot.items must not be None")

        # (optional) normalize: forbid None items
        for i, it in enumerate(self.items):
            if it is None:
                raise ValueError(f"FileRoot.items[{i}] is None")

        return self


# update forward refs for Node
TextBlock.model_rebuild()
DirectiveNode.model_rebuild()
ConditionalBranch.model_rebuild()
ConditionalGroup.model_rebuild()
FileRoot.model_rebuild()
