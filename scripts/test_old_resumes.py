import sys
from pathlib import Path
import time
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from resume_segmentation.services.resume_processor import ResumeProcessor
from resume_segmentation.settings import settings

def main():
    processor = ResumeProcessor(output_dir=settings.output_dir)
    pdf_dir = PROJECT_ROOT / "ENGINEERING resume Test"
    out_dir = PROJECT_ROOT / "output_jsons"
    out_dir.mkdir(exist_ok=True)
    
    pdf_files = list(pdf_dir.glob("*.pdf"))
    
    print(f"Found {len(pdf_files)} PDFs to process.")
    success = 0
    failed = 0
    total_skills = 0
    total_exp = 0
    total_edu = 0
    
    start = time.time()
    
    for i, pdf in enumerate(pdf_files):
        try:
            profile = processor.process(pdf)
            success += 1
            total_skills += len(profile.skills) if profile.skills else 0
            total_exp += len(profile.experience) if profile.experience else 0
            total_edu += len(profile.education) if profile.education else 0
            
            # Save JSON
            out_file = out_dir / (pdf.stem + ".json")
            out_file.write_text(profile.model_dump_json(indent=4), encoding="utf-8")
        except Exception as e:
            failed += 1
            
        if (i+1) % 10 == 0:
            print(f"Processed {i+1}/{len(pdf_files)}")
            
    end = time.time()
    
    print("\n--- Parsing Results ---")
    print(f"Total Resumes: {len(pdf_files)}")
    print(f"Successfully Parsed & Saved JSONs in 'output_jsons' directory: {success}")
    print(f"Failed to Parse: {failed}")
    if success > 0:
        print(f"Avg Skills extracted per resume: {total_skills / success:.1f}")
        print(f"Avg Work Experience instances per resume: {total_exp / success:.1f}")
        print(f"Avg Education instances per resume: {total_edu / success:.1f}")
    print(f"Total Time taken: {end - start:.2f} seconds")

if __name__ == "__main__":
    main()
