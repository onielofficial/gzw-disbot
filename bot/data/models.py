"""Pydantic models for the entities exposed by gzwtacmap.com.

All models include a `to_dict()` for stable serialization to the cache snapshot
and accept extra keys (`model_config = {extra: "allow"}`) so we won't crash
when gzwtacmap.com adds new fields to its payloads.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Objective(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: Optional[str] = None
    name: Optional[str] = None
    note: Optional[str] = None
    place_id: Optional[str] = None
    done: bool = False


class Task(BaseModel):
    model_config = ConfigDict(extra="allow")
    slug: str
    name: str
    type: Optional[str] = "main"  # main | side | contract
    trader: Optional[str] = None
    faction: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    objectives: List[Objective] = Field(default_factory=list)
    rewards: List[str] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    thumb: Optional[str] = None

    def to_dict(self) -> dict:
        return self.model_dump(exclude_none=False)


class KeyDoor(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: Optional[str] = None
    location: Optional[str] = None
    place_id: Optional[str] = None


class Key(BaseModel):
    model_config = ConfigDict(extra="allow")
    slug: str
    name: str
    region: Optional[str] = None
    found_on: Optional[str] = None
    rarity: Optional[str] = None
    uses: Optional[int] = None
    doors: List[KeyDoor] = Field(default_factory=list)
    notes: Optional[str] = None
    source_url: Optional[str] = None
    thumb: Optional[str] = None

    def to_dict(self) -> dict:
        return self.model_dump(exclude_none=False)


class Place(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    name: str
    group: Optional[str] = None
    region: Optional[str] = None
    description: Optional[str] = None
    coords: Optional[str] = None  # "x,y" or pixel-coords from the map
    nearest_lz: Optional[str] = None
    related_tasks: List[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    screenshot: Optional[str] = None
    thumb: Optional[str] = None

    def to_dict(self) -> dict:
        return self.model_dump(exclude_none=False)


class Group(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    name: str
    description: Optional[str] = None
    place_count: int = 0
    source_url: Optional[str] = None

    def to_dict(self) -> dict:
        return self.model_dump(exclude_none=False)


class Trader(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    callsign: Optional[str] = None
    role: Optional[str] = None
    faction: Optional[str] = None
    bio: Optional[str] = None
    portrait: Optional[str] = None
    specialties: List[str] = Field(default_factory=list)
    task_count: Optional[int] = None

    def to_dict(self) -> dict:
        return self.model_dump(exclude_none=False)


class Faction(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    type: str = "pmc"  # pmc | hostile
    hq: Optional[str] = None
    aor: Optional[str] = None
    threat: Optional[str] = None
    bio: Optional[str] = None

    def to_dict(self) -> dict:
        return self.model_dump(exclude_none=False)
