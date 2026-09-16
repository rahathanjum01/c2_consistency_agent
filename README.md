# C2 - Document & Identity Consistency Agent
Track C Perception Voice Document Reasoning
How to run: py -m pip install flask pillow rapidfuzz reportlab pytesseract
py app.py -> http://127.0.0.1:5000
Architecture: Upload -> OCR (Tesseract) -> Normalization (RapidFuzz/Levenshtein) -> Consistency Engine -> Flagged Report + Voice I/O
Voice: Web Speech API for Speech-to-Text and Text-to-Speech
Test: 3 self-created mock docs - flags DOB fraud