from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class PersonalInfo(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    headline: Optional[str] = None


class LinkItem(BaseModel):
    label: str
    url: str


class DateRange(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None
    is_current: bool = False


class ExperienceEntry(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    date_range: Optional[DateRange] = None
    location: Optional[str] = None
    bullets: list[str] = Field(default_factory=list)


class EducationEntry(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    date_range: Optional[DateRange] = None
    gpa: Optional[str] = None


class ProjectEntry(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    date_range: Optional[DateRange] = None
    technologies: list[str] = Field(default_factory=list)
    url: Optional[str] = None


class CertificationEntry(BaseModel):
    name: Optional[str] = None
    issuer: Optional[str] = None
    date: Optional[str] = None


class ResumeProfile(BaseModel):
    personal_info: PersonalInfo
    links: list[LinkItem] = Field(default_factory=list)
    summary: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    certifications: list[CertificationEntry] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    awards: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)

    @field_validator("skills")
    @classmethod
    def deduplicate_skills(cls, v: list[str]) -> list[str]:
        seen: set = set()
        result: list[str] = []
        for x in v:
            key = x.lower().strip()
            if key and key not in seen:
                seen.add(key)
                result.append(x.strip())
        return result


class BoundingBox(BaseModel):
    label: str
    x0: float
    y0: float
    x1: float
    y1: float
    page: int = 0
    page_width: Optional[float] = None
    page_height: Optional[float] = None
    coord_origin: str = "BOTTOMLEFT"


class ExtractedBlock(BaseModel):
    label: str
    text: str
    urls: list[LinkItem] = Field(default_factory=list)
    page: int = 0
