import sys
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from resume_segmentation.services.resume_processor import ResumeProcessor
from resume_segmentation.settings import settings

def main():
    processor = ResumeProcessor(output_dir=settings.output_dir)
    pdf_path = PROJECT_ROOT / "ADev_Resume.pdf"
    out_dir = PROJECT_ROOT / "output_jsons"
    out_dir.mkdir(exist_ok=True)
    
    try:
        profile = processor.process(pdf_path)
        out_file = out_dir / (pdf_path.stem + ".json")
        json_data = profile.model_dump_json(indent=4)
        out_file.write_text(json_data, encoding="utf-8")
        print(f"SUCCESS: Saved to {out_file}")
        print("-" * 40)
        print("EXTRACTION SUMMARY:")
        personal_info = profile.personal_info
        print(f"Name: {personal_info.name if personal_info and personal_info.name else 'N/A'}")
        print(f"Skills Extracted: {len(profile.skills) if profile.skills else 0}")
        if profile.skills:
            print(f"Sample Skills: {', '.join(profile.skills[:5])}...")
        print(f"Experience Instances: {len(profile.experience) if profile.experience else 0}")
        if profile.experience:
            for exp in profile.experience:
                print(f" - {exp.title or 'Unknown'} at {exp.company or 'Unknown'}")
        print(f"Education Instances: {len(profile.education) if profile.education else 0}")
        if profile.education:
            for edu in profile.education:
                print(f" - {edu.degree or 'Unknown'} at {edu.institution or 'Unknown'}")
    except Exception as e:
        print(f"Error parsing PDF: {e}")

if __name__ == "__main__":
    main()
