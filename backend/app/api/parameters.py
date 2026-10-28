from typing import Annotated

from fastapi import Path, Query
from pydantic import StringConstraints

from app.models import MAX_IDENTIFIER

# Keep identifiers exact in the browser and below SQLite's signed integer limit.
ResourceId = Annotated[int, Path(gt=0, le=MAX_IDENTIFIER)]
QueryId = Annotated[int, Query(gt=0, le=MAX_IDENTIFIER)]
OptionalQueryId = Annotated[int | None, Query(gt=0, le=MAX_IDENTIFIER)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=MAX_IDENTIFIER)]
Keyword = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Search = Annotated[Keyword | None, Query()]
