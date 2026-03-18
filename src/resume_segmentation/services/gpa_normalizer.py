"""
gpa_normalizer.py — Universal GPA / grade normalization engine.

Converts any academic grade format to three canonical scales:
  - Percentage (0–100)
  - 4.0 scale (US standard)
  - 10-point CGPA (Indian standard)

Handles:
  "9.2 / 10"       CGPA (India)
  "3.8 / 4.0"      GPA (US)
  "87%"            Percentage
  "87"             Bare percentage
  "First Class"    Grade class (India/UK)
  "A+"             Letter grade
  "Distinction"    Qualitative grade
  "4.0"            GPA without denominator
  "8.5"            CGPA without denominator (context-inferred)
  "O"              Outstanding (some Indian grading)
  "87/100"         Fraction
  "560/600"        Raw marks
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


                                                                               
              
                                                                               

@dataclass
class NormalizedGPA:
    raw: str
    percentage: Optional[float]          
    gpa_4: Optional[float]                          
    cgpa_10: Optional[float]                            
    scale: str                                                                                         
    display: str                                                    

    @property
    def is_high(self) -> bool:
        if self.percentage is not None:
            return self.percentage >= 75
        return False

    @property
    def is_valid(self) -> bool:
        return self.percentage is not None


                                                                               
                   
                                                                               

                                    
_LETTER_TO_PCT: dict[str, float] = {
    "o":   96.0,                       
    "a+":  96.0,
    "a":   92.0,
    "a-":  87.5,
    "b+":  82.5,
    "b":   77.5,
    "b-":  72.5,
    "c+":  67.5,
    "c":   62.5,
    "c-":  57.5,
    "d+":  52.5,
    "d":   47.5,
    "d-":  42.5,
    "f":   25.0,
    "e":   25.0,                        
}

                                   
_CLASS_TO_PCT: dict[str, float] = {
    "distinction":         90.0,
    "first class":         72.5,
    "first":               72.5,
    "second class upper":  62.5,
    "second class":        55.0,
    "second class lower":  52.5,
    "second":              55.0,
    "pass class":          45.0,
    "pass":                45.0,
    "fail":                25.0,
    "merit":               75.0,
    "credit":              65.0,
}

                                               
def _gpa4_to_pct(gpa: float) -> float:
    if gpa >= 4.0:  return 97.0
    if gpa >= 3.9:  return 95.0
    if gpa >= 3.7:  return 92.0
    if gpa >= 3.5:  return 88.5
    if gpa >= 3.3:  return 86.0
    if gpa >= 3.0:  return 83.0
    if gpa >= 2.7:  return 78.0
    if gpa >= 2.3:  return 75.0
    if gpa >= 2.0:  return 73.0
    if gpa >= 1.7:  return 68.0
    if gpa >= 1.3:  return 64.0
    if gpa >= 1.0:  return 61.0
    if gpa >= 0.7:  return 56.0
    return 50.0

                                
def _pct_to_gpa4(pct: float) -> float:
    if pct >= 97: return 4.0
    if pct >= 93: return 3.9
    if pct >= 90: return 3.7
    if pct >= 87: return 3.3
    if pct >= 83: return 3.0
    if pct >= 80: return 2.7
    if pct >= 77: return 2.3
    if pct >= 73: return 2.0
    if pct >= 70: return 1.7
    if pct >= 67: return 1.3
    if pct >= 63: return 1.0
    if pct >= 60: return 0.7
    if pct >= 55: return 0.5
    if pct >= 50: return 0.3
    if pct >= 45: return 0.1
    return 0.0

                                                                       
def _cgpa10_to_pct(cgpa: float) -> float:
    return min(cgpa * 9.5, 100.0)

                      
def _pct_to_cgpa10(pct: float) -> float:
    return round(min(pct / 9.5, 10.0), 2)


                                                                               
          
                                                                               

                                                  
_FRACTION_RE = re.compile(
    r"([\d.]+)\s*/\s*([\d.]+)",
    re.IGNORECASE,
)

                   
_PCT_RE = re.compile(r"([\d.]+)\s*%")

                                    
_BARE_RE = re.compile(r"^[\d.]+$")

                            
_LETTER_RE = re.compile(r"^([A-FO][+-]?)$", re.IGNORECASE)

             
_CLASS_WORDS = sorted(_CLASS_TO_PCT.keys(), key=len, reverse=True)                 
_CLASS_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _CLASS_WORDS) + r")\b",
    re.IGNORECASE,
)

                                                 
_LABEL_RE = re.compile(
    r"\b(?:CGPA|GPA|Percentage|Score|Grade|Marks|Points|CPI|SPI|SGPA|DGPA)[:\s]*",
    re.IGNORECASE,
)


                                                                               
                 
                                                                               

def normalize_gpa(raw: str) -> NormalizedGPA:
    if not raw:
        return NormalizedGPA(raw=raw, percentage=None, gpa_4=None,
                              cgpa_10=None, scale="unknown", display="N/A")

    cleaned = _LABEL_RE.sub("", raw).strip()

                                                                
    frac = _FRACTION_RE.search(cleaned)
    if frac:
        numerator   = float(frac.group(1))
        denominator = float(frac.group(2))
        if denominator <= 0:
            pass
        else:
            ratio = numerator / denominator
            if abs(denominator - 10) < 0.01:
                                
                return _from_cgpa10(raw, numerator)
            elif abs(denominator - 4) < 0.01 or abs(denominator - 4.33) < 0.1:
                                
                return _from_gpa4(raw, numerator)
            elif abs(denominator - 100) < 0.5:
                                       
                return _from_pct(raw, numerator)
            else:
                                                    
                return _from_pct(raw, ratio * 100)

                                     
    pct = _PCT_RE.search(cleaned)
    if pct:
        return _from_pct(raw, float(pct.group(1)))

                                   
    letter = _LETTER_RE.match(cleaned.strip())
    if letter:
        key = letter.group(1).lower()
        pct_val = _LETTER_TO_PCT.get(key)
        if pct_val is not None:
            return _from_pct(raw, pct_val, scale="letter")

                                                        
    cls = _CLASS_RE.search(cleaned)
    if cls:
        key = cls.group(1).lower()
        pct_val = _CLASS_TO_PCT.get(key)
        if pct_val is not None:
            return _from_pct(raw, pct_val, scale="class")

                                                   
    bare = _BARE_RE.match(cleaned.strip())
    if bare:
        val = float(cleaned.strip())
        if val <= 4.33:
            return _from_gpa4(raw, val)
        elif val <= 10:
            return _from_cgpa10(raw, val)
        elif val <= 100:
            return _from_pct(raw, val)

    return NormalizedGPA(raw=raw, percentage=None, gpa_4=None,
                          cgpa_10=None, scale="unknown", display=raw)


def _from_cgpa10(raw: str, cgpa: float) -> NormalizedGPA:
    cgpa = max(0.0, min(cgpa, 10.0))
    pct  = round(_cgpa10_to_pct(cgpa), 1)
    gpa4 = round(_pct_to_gpa4(pct), 2)
    return NormalizedGPA(
        raw=raw, percentage=pct, gpa_4=gpa4, cgpa_10=round(cgpa, 2),
        scale="cgpa_10", display=f"{cgpa}/10  ({pct}%  ≈ {gpa4}/4.0)",
    )


def _from_gpa4(raw: str, gpa: float) -> NormalizedGPA:
    gpa  = max(0.0, min(gpa, 4.0))
    pct  = round(_gpa4_to_pct(gpa), 1)
    c10  = round(_pct_to_cgpa10(pct), 2)
    return NormalizedGPA(
        raw=raw, percentage=pct, gpa_4=round(gpa, 2), cgpa_10=c10,
        scale="gpa_4", display=f"{gpa}/4.0  ({pct}%  ≈ {c10}/10)",
    )


def _from_pct(raw: str, pct: float, scale: str = "percentage") -> NormalizedGPA:
    pct  = max(0.0, min(pct, 100.0))
    gpa4 = round(_pct_to_gpa4(pct), 2)
    c10  = round(_pct_to_cgpa10(pct), 2)
    return NormalizedGPA(
        raw=raw, percentage=round(pct, 1), gpa_4=gpa4, cgpa_10=c10,
        scale=scale, display=f"{pct}%  (≈ {gpa4}/4.0  ≈ {c10}/10)",
    )
