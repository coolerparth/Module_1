# Arie Resume Parser

A high-performance, deterministic resume parsing and validation pipeline designed to extract structured information from resumes with precision.

## Features

- **Deterministic Pipeline**: No LLM dependencies for core extraction, ensuring absolute reliability and low cost.
- **Section Segmentation**: Intelligent layout-aware splitting of resume sections.
- **Detailed Extraction**: Captures Personal Info, Skills, Experience, Education, and Certifications.
- **API and CLI Support**: Easily integrable as a FastAPI service or a standalone CLI tool.
- **Benchmarking Tools**: Built-in evaluation scripts with ground truth comparison.

## Quick Start

### Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/coolerparth/Module_1.git
    cd Module_1
    ```

2.  **Install dependencies**:
    ```bash
    pip install -e .
    ```

3.  **Setup Spacy**:
    ```bash
    python -m spacy download en_core_web_sm
    ```

### Usage

#### CLI (Single File)
```bash
python parse_single.py
```

#### API (FastAPI)
```bash
uvicorn main:app --reload
```

## Project Structure

- `src/`: Core parsing engine.
- `data/`: Benchmark datasets and metadata.
- `docs/`: Documentation and benchmarking reports.
- `scripts/`: Utility scripts for evaluation and data processing.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
