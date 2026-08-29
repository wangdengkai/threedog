from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class StructureOptions(BaseModel):
    domains: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    granularity: Literal["year", "quarter", "month"] = "month"
    inbox: bool = True


class NamingSpec(BaseModel):
    convention: Literal["zh", "bilingual", "emoji", "numbered"] = "zh"
    emoji_map: dict[str, str] = Field(default_factory=dict)
    en_map: dict[str, str] = Field(default_factory=dict)
    number_width: int = 2


class Presentation(BaseModel):
    portal: Literal["minimal", "dashboard", "timeline"] = "minimal"
    show_stats: bool = True
    narration: bool = True


class StyleProfile(BaseModel):
    id: int | None = None
    name: str
    structure: Literal["domain", "project", "time", "gtd"]
    options: StructureOptions = Field(default_factory=StructureOptions)
    naming: NamingSpec = Field(default_factory=NamingSpec)
    presentation: Presentation = Field(default_factory=Presentation)
    active: bool = False

    @model_validator(mode="after")
    def _check(self) -> StyleProfile:
        if self.structure == "domain" and not self.options.domains:
            raise ValueError("domain 结构需要 options.domains 非空")
        if self.structure == "project" and not self.options.projects:
            raise ValueError("project 结构需要 options.projects 非空")
        return self
