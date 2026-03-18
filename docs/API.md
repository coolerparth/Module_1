# API Reference

## Base URL
```
http://localhost:8000
```

## Endpoints

### POST /extract

Extract structured data from a PDF resume.

**Request**
```bash
curl -X POST http://localhost:8000/extract \
  -F "file=@resume.pdf"
```

**Response**
```json
{
  "schema_version": "3.1.0",
  "extracted_at": "2026-01-01T12:00:00Z",
  "success": true,
  "profile": {
    "personal_info": {
      "name": "Rahul Kumar",
      "email": "rahul@example.com",
      "phone": "+91-9876543210",
      "location": "Bangalore, India",
      "headline": "Senior Software Engineer"
    },
    "links": [
      { "label": "LinkedIn", "url": "https://linkedin.com/in/rahulkumar" },
      { "label": "GitHub",   "url": "https://github.com/rahulkumar" }
    ],
    "summary": "Experienced engineer with 7+ years in distributed systems.",
    "skills": ["Python", "Go", "Kubernetes", "PostgreSQL", "Kafka"],
    "experience": [
      {
        "company": "Google India",
        "title": "Senior Software Engineer",
        "date_range": { "start": "Aug 2021", "end": null, "is_current": true },
        "location": null,
        "bullets": [
          "Architected payment API processing 2M requests/day",
          "Reduced latency by 40% via Redis caching"
        ]
      }
    ],
    "education": [
      {
        "institution": "IIT Delhi",
        "degree": "B.Tech",
        "field_of_study": "Computer Science and Engineering",
        "date_range": { "start": "2017", "end": "2021", "is_current": false },
        "gpa": "9.2 / 10"
      }
    ],
    "projects": [],
    "certifications": [],
    "awards": [],
    "languages": [],
    "interests": []
  },
  "enrichment": {
    "normalized_skills": [...],
    "skills_by_category": {
      "Programming Languages": ["Python", "Go"],
      "Cloud & DevOps": ["Kubernetes"]
    },
    "tech_stack_score": 0.82,
    "career_intelligence": {
      "career_level": "Senior (6–10 yrs)",
      "total_years_experience": 7.2,
      "primary_domain": "Backend / Full-stack",
      "notable_companies": ["Google India"],
      "notable_universities": ["IIT Delhi"],
      "seniority_score": 0.74
    },
    "quality_report": {
      "scores": { "ats": 95, "completeness": 88, "bullets": 76, "overall": 87 },
      "grades": { "ats": "A", "overall": "A" },
      "missing_fields": [],
      "suggestions": []
    },
    "timeline": {
      "is_consistent": true,
      "total_years_experience": 7.2,
      "errors": [],
      "warnings": []
    },
    "gpa_normalized": [
      {
        "institution": "IIT Delhi",
        "raw": "9.2 / 10",
        "percentage": 87.4,
        "gpa_4": 3.3,
        "cgpa_10": 9.2,
        "scale": "cgpa_10",
        "display": "9.2/10  (87.4%  ≈ 3.3/4.0)"
      }
    ],
    "detected_language": "English",
    "layout": "single_column",
    "page_count": 2,
    "processing_time_ms": 312
  },
  "confidence": {
    "overall": 0.87,
    "grade": "A",
    "fields": { ... }
  }
}
```

---

### POST /quality

Get ATS compatibility and quality scores for a resume.

**Request**
```bash
curl -X POST http://localhost:8000/quality \
  -F "file=@resume.pdf"
```

**Response**
```json
{
  "scores": {
    "ats": 92,
    "completeness": 85,
    "bullets": 71,
    "overall": 84
  },
  "grades": { "ats": "A", "overall": "B" },
  "missing_fields": [],
  "suggestions": [
    {
      "priority": 3,
      "category": "Bullets",
      "message": "4/12 bullets lack metrics — add numbers to show impact",
      "example": "Before: 'Improved performance'  →  After: 'Reduced load time by 60%'"
    }
  ],
  "bullet_quality": {
    "top_bullets": ["Architected payment API processing $2M/day"],
    "weak_bullets": ["Responsible for backend development"]
  }
}
```

---

### GET /health

Service health check.

**Response**
```json
{
  "status": "ok",
  "service": "resume_segmentation",
  "version": "3.1.0",
  "output_directory": "/app/data/output"
}
```

---

## Status Codes

| Code | Meaning |
|------|---------|
| 200  | Extraction successful |
| 400  | Invalid file type or empty file |
| 413  | File exceeds 50 MB limit |
| 422  | PDF could not be parsed (scanned/image-only) |
| 500  | Internal server error |
