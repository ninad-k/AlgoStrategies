from pydantic import BaseModel


class AttributionSummary(BaseModel):
    attributed_trader: int
    attributed_strategy: int
    guest: int


class UploadResponse(BaseModel):
    batch_id: str
    total_rows: int
    inserted: int
    skipped_duplicates: int
    attribution_summary: AttributionSummary
