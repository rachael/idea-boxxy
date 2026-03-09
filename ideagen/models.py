"""Data models for the idea generator."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Reaction(str, Enum):
    LOVE = "love"
    LIKE = "like"
    MEH = "meh"
    DISLIKE = "dislike"
    SAVE = "save"          # bookmark for later
    EXPLORE = "explore"    # drill deeper into this idea


class IdeaCategory(str, Enum):
    PRODUCTIVITY = "productivity"
    DEVELOPER_TOOLS = "developer_tools"
    AI_ML = "ai_ml"
    HEALTH_FITNESS = "health_fitness"
    FINANCE = "finance"
    EDUCATION = "education"
    SOCIAL = "social"
    ENTERTAINMENT = "entertainment"
    CREATIVE_TOOLS = "creative_tools"
    DATA_ANALYTICS = "data_analytics"
    AUTOMATION = "automation"
    COMMUNICATION = "communication"
    ECOMMERCE = "ecommerce"
    SUSTAINABILITY = "sustainability"
    HARDWARE_IOT = "hardware_iot"
    OTHER = "other"


@dataclass
class AppIdea:
    id: int
    title: str
    one_liner: str
    description: str
    category: str
    market_angle: str       # why this is popular/useful for people
    personal_angle: str     # why this might interest the user specifically
    target_users: str
    monetization: str
    complexity: str         # small / medium / large
    tags: list[str] = field(default_factory=list)
    reaction: str | None = None
    notes: str = ""
    session_id: int | None = None
    created_at: str = ""


@dataclass
class UserInterest:
    id: int
    topic: str
    weight: float           # 0.0 to 1.0, strength of interest
    source: str             # how we learned this: "reaction", "stated", "inferred"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class SessionRecord:
    id: int
    direction: str          # user-chosen direction or "open" for freeform
    ideas_generated: int = 0
    ideas_liked: int = 0
    started_at: str = ""
    ended_at: str = ""
