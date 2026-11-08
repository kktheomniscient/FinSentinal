from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=1000)
    ticker: str | None = Field(default=None, max_length=10, pattern=r"^[A-Za-z0-9.\-]+$")


class Citation(BaseModel):
    tag: str
    cited: bool
    ticker: str
    period_end: str
    section: str
    accession: str | None = None
    source_url: str | None = None
    excerpt: str


class TraceStep(BaseModel):
    node: str
    detail: str


class Grounding(BaseModel):
    """Where one figure in the memo was found."""
    figure: str
    kind: str  # filing | market | calc
    tag: str
    field: str
    source_value: float
    source_text: str | None = None
    snippet: str | None = None
    period_end: str | None = None
    scaled: bool = False


class Verification(BaseModel):
    numbers_checked: int
    unverified: list[str]
    grounded_ratio: float | None
    grounding: list[Grounding] = []


class ResearchResponse(BaseModel):
    trace_url: str | None = None
    query: str
    ticker: str | None
    memo: str | None
    error: str | None = None
    citations: list[Citation] = []
    market: dict | None = None
    calcs: list[dict] = []
    notes: list[str] = []
    verification: Verification | None = None
    trace: list[TraceStep] = []
