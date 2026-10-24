"""Pydantic schemas for TinyFish integration surfaces (Fetch, Search, Agent, Browser)."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# --- Search API Schemas ---

class TinyFishSearchResult(BaseModel):
    title: str
    url: str
    snippet: Optional[str] = None
    rank: Optional[int] = None


class TinyFishSearchResponse(BaseModel):
    query: str
    total_results: int = 0
    results: List[TinyFishSearchResult] = Field(default_factory=list)
    is_mock: bool = False


# --- Fetch API Schemas ---

class TinyFishFetchRequest(BaseModel):
    urls: List[str] = Field(..., max_length=10)
    format: str = Field(default="markdown", description="'markdown', 'html', or 'json'")
    purpose: Optional[str] = Field(default=None, max_length=2000)
    links: bool = False
    image_links: bool = False
    iframe_links: bool = False


class TinyFishFetchItem(BaseModel):
    url: str
    status_code: int = 200
    content: str
    title: Optional[str] = None
    links: Optional[List[str]] = Field(default_factory=list)
    image_links: Optional[List[str]] = Field(default_factory=list)
    redirect_chain: Optional[List[str]] = Field(default_factory=list)
    headers: Optional[Dict[str, str]] = None


class TinyFishFetchResponse(BaseModel):
    results: List[TinyFishFetchItem] = Field(default_factory=list)
    is_mock: bool = False


# --- Agent API (Detonation) Schemas ---

class TinyFishAgentRequest(BaseModel):
    url: str
    goal: str
    stream: bool = False
    timeout_seconds: int = 120
    parameters: Optional[Dict[str, Any]] = None


class TinyFishAgentEvent(BaseModel):
    event_type: str
    step_number: Optional[int] = None
    action: Optional[str] = None
    thought: Optional[str] = None
    screenshot_url: Optional[str] = None
    timestamp: Optional[str] = None


class TinyFishAgentResponse(BaseModel):
    session_id: str
    status: str = "completed"  # queued, running, completed, failed
    url: str
    goal: str
    extracted_data: Optional[Dict[str, Any]] = None
    final_url: Optional[str] = None
    redirect_chain: List[str] = Field(default_factory=list)
    events: List[TinyFishAgentEvent] = Field(default_factory=list)
    screenshots: List[str] = Field(default_factory=list)
    is_mock: bool = False


# --- Browser API (Managed Cloud Sessions) Schemas ---

class TinyFishBrowserSessionCreate(BaseModel):
    url: Optional[str] = None
    viewport_width: int = 1280
    viewport_height: int = 800


class TinyFishBrowserSession(BaseModel):
    session_id: str
    cdp_url: str
    initial_url: Optional[str] = None
    status: str = "active"
    created_at: str
    is_mock: bool = False


# --- Verification / Health Check Schema ---

class TinyFishVerificationResult(BaseModel):
    client_ready: bool
    api_key_configured: bool
    mode: str  # "live" | "mock_fallback"
    fetch_status: str
    search_status: str
    sample_search_query: str
    sample_search_result_count: int
    sample_fetch_url: str
    sample_fetch_length: int
    message: str
