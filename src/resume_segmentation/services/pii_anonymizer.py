from __future__ import annotations

import re
import hashlib
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ..models.resume import PersonalInfo, ResumeProfile


class AnonymizeMode(str, Enum):
    MASK      = "mask"                                 
    REDACT    = "redact"                    
    PSEUDONYM = "pseudonym"                                     
    PARTIAL   = "partial"                             


@dataclass
class AnonymizationResult:
    profile: ResumeProfile
    fields_masked: list[str]
    mode: str


class PIIAnonymizer:

                           
    PII_FIELDS = ["name", "email", "phone", "location", "headline"]

    def anonymize(
        self,
        profile: ResumeProfile,
        mode: AnonymizeMode = AnonymizeMode.MASK,
        mask_name: bool = True,
        mask_email: bool = True,
        mask_phone: bool = True,
        mask_location: bool = False,
        mask_links: bool = True,
    ) -> AnonymizationResult:
        p = deepcopy(profile)
        masked: list[str] = []

        info = p.personal_info
        name_seed = info.name or "unknown"

        if mask_name and info.name:
            p.personal_info = PersonalInfo(
                name=self._mask(info.name, mode, "NAME", name_seed),
                email=info.email,
                phone=info.phone,
                location=info.location,
                headline=info.headline,
            )
            masked.append("name")

        if mask_email and info.email:
            p.personal_info = PersonalInfo(
                name=p.personal_info.name,
                email=self._mask_email(info.email, mode, name_seed),
                phone=p.personal_info.phone,
                location=p.personal_info.location,
                headline=p.personal_info.headline,
            )
            masked.append("email")

        if mask_phone and info.phone:
            p.personal_info = PersonalInfo(
                name=p.personal_info.name,
                email=p.personal_info.email,
                phone=self._mask_phone(info.phone, mode),
                location=p.personal_info.location,
                headline=p.personal_info.headline,
            )
            masked.append("phone")

        if mask_location and info.location:
            p.personal_info = PersonalInfo(
                name=p.personal_info.name,
                email=p.personal_info.email,
                phone=p.personal_info.phone,
                location=self._mask(info.location, mode, "LOCATION", name_seed),
                headline=p.personal_info.headline,
            )
            masked.append("location")

        if mask_links and p.links:
            p.links = []
            masked.append("links")

        return AnonymizationResult(profile=p, fields_masked=masked, mode=mode.value)

    def _mask(self, value: str, mode: AnonymizeMode, placeholder: str, seed: str) -> str:
        if mode == AnonymizeMode.MASK:
            return f"[{placeholder}]"
        if mode == AnonymizeMode.REDACT:
            return "***"
        if mode == AnonymizeMode.PSEUDONYM:
            return self._pseudonym_name(value, seed)
        if mode == AnonymizeMode.PARTIAL:
            return self._partial_mask(value)
        return f"[{placeholder}]"

    def _mask_email(self, email: str, mode: AnonymizeMode, seed: str) -> str:
        if mode == AnonymizeMode.MASK:
            return "[EMAIL]"
        if mode == AnonymizeMode.REDACT:
            return "***@***.***"
        if mode == AnonymizeMode.PSEUDONYM:
            h = hashlib.md5(seed.encode()).hexdigest()[:6]
            return f"user{h}@example.com"
        if mode == AnonymizeMode.PARTIAL:
            at = email.find("@")
            if at > 1:
                return email[0] + "***" + email[at:]
            return "***@" + email.split("@")[-1]
        return "[EMAIL]"

    def _mask_phone(self, phone: str, mode: AnonymizeMode) -> str:
        if mode == AnonymizeMode.MASK:
            return "[PHONE]"
        if mode == AnonymizeMode.REDACT:
            return "+XX-XXXXXXXXXX"
        if mode == AnonymizeMode.PSEUDONYM:
                                               
            cc_match = re.match(r"(\+\d{1,3})", phone)
            cc = cc_match.group(1) if cc_match else "+XX"
            return f"{cc}-XXXXXXXXXX"
        if mode == AnonymizeMode.PARTIAL:
            digits = re.findall(r"\d", phone)
            if len(digits) >= 4:
                masked_digits = digits[:2] + ["*"] * (len(digits) - 4) + digits[-2:]
                return "".join(masked_digits)
            return "***"
        return "[PHONE]"

    def _pseudonym_name(self, name: str, seed: str) -> str:
        parts = name.strip().split()
        if len(parts) >= 2:
            return ".".join(p[0].upper() for p in parts if p) + "."
        elif parts:
            return parts[0][0].upper() + "."
        return "A.B."

    def _partial_mask(self, value: str) -> str:
        if len(value) <= 2:
            return "*" * len(value)
        return value[0] + "*" * (len(value) - 2) + value[-1]

