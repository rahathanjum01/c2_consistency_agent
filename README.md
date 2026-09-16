# C2 - Document & Identity Consistency Agent (Track C)

An AI agent that extracts structured field data from uploaded documents, normalizes variations, checks cross-document consistency, and generates an LLM-synthesized reasoning report.

## System Architecture
1. **Perception**: Dynamic text detection using EasyOCR (PyTorch).
2. **Normalization**: `python-dateutil` and `rapidfuzz` address/string standardization.
3. **Consistency Engine**: Multi-document cross-matching logic (Name, DOB, Address).
4. **LLM Reasoning**: Groq API (`llama-3.3-70b-versatile`) synthesizes report findings.
5. **Voice & PDF I/O**: Web Speech API integration + ReportLab PDF report generation.

## Setup Instructions

1. **Clone repository and enter directory**
2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate