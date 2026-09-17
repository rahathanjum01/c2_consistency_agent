# Document & Identity Consistency Agent

**Track C: Perception, Voice & Document Reasoning**

An AI-powered document verification agent that processes unstructured inputs (images, voice commands) to extract structured identity metadata, normalize field variations, cross-check multi-document consistency, and generate actionable reasoning reports for human reviewers.

---

## 🏗️ Architecture & Workflow Diagram

```
[ Uploaded Documents ] / [ 🎤 Voice Trigger ]
                          │
                          ▼
              [ EasyOCR Perception Engine ]
              (Line-by-line field extraction)
                          │
                          ▼
            [ Text Normalization Layer ]
   • Dates  ➔ DD-MM-YYYY (Indian Standard)
   • Names  ➔ RapidFuzz Token Set Matching
   • Addr   ➔ Typo Correction & Formatting
                          │
                          ▼
         [ Multi-Doc Consistency Matrix ]
       (Cross-checks Name, DOB, & Address)
                          │
                          ▼
        [ Hybrid LLM Reasoning Engine ]
   • Groq API (Llama-3.3-70b / Mixtral)
   • Offline Heuristic Synthesis Fallback
                          │
                          ▼
    [ Web Dashboard ] ➔ [ 🔊 Speech Synthesis ]
                     ➔ [ 📄 Styled PDF Report ]

```

---

## ✨ Key Features

* **Perception Engine**: Powered by `EasyOCR` for text detection across document types (Aadhaar, PAN, Passports, Marksheets).
* **Smart Normalization**: Converts dates into `DD-MM-YYYY` format and handles address typos (`rcad` $\rightarrow$ `Road`) while preserving commas and proper noun capitalization.
* **Calibrated Cross-Matching**: Distinguishes between critical fraud risks (DOB alterations) and minor variations (middle name or spacing differences like `"Rajkumar"` vs `"RAJ KUMAR SHARMA"`).
* **Hybrid Reasoning**: Leverages Groq API for LLM reasoning with an offline fallback engine to guarantee zero-downtime execution.
* **Voice & PDF I/O**: Voice command routing via Web Speech API and PDF report generation built on ReportLab's `Platypus` layout framework.
* **Human-in-the-Loop Safeguards**: Integrated disclaimers ensuring the agent operates as a pre-screening aid.

---

## 🚀 Quickstart & Setup (Under 2 Minutes)

### Prerequisites

* **Python 3.9+** installed.

### Step 1: Clone Repository & Create Virtual Environment

```bash
git clone https://github.com/rahathanjum01/c2_consistency_agent.git
cd c2_consistency_agent

# Create virtual environment
python -m venv venv

# Activate environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt

```

### Step 3: Configure Environment Variables

Create a `.env` file in the project root directory:

```env
GROQ_API_KEY=gsk_your_groq_api_key_here

```

*(Note: If `GROQ_API_KEY` is omitted, the application automatically runs in offline hybrid reasoning mode without crashing).*

---

## 🧪 Testing Instructions

### 1. Generate Test Data

Run the mock generator script to create test document images:

```bash
python create_mock.py

```

This creates three test images in the `uploads/` directory:

* `doc1_application.png`: Standard application form (`DOB: 01/02/2000`).
* `doc2_marksheet.png`: Board marksheet with spelling/date variants (`DOB: 1 Feb 2000`).
* `doc3_idcard.png`: ID card with altered birth year (`DOB: 15/08/1999` - Fraud Risk).

### 2. Launch the Application

```bash
python app.py

```

Open your browser and navigate to: **`[http://127.0.0.1:5000](http://127.0.0.1:5000)`**

### 3. Verify Execution

1. Click **Choose Files** and upload your documents.
2. Click **RUN CHECK** (or click **🎤 Speak Voice Command** and say *"Check my documents"*).
3. Verify that:
* **Dates** map to `01-02-2000` and `15-08-1999`.
* **Name Variant** between Doc 1 & Doc 2 is categorized as `[LOW]` risk.
* **DOB Mismatch** between Doc 1/2 & Doc 3 is flagged as `[HIGH]` risk fraud.
* Click **🔊 Read Report Aloud** to test voice synthesis.
* Click **Download PDF Report** to view the formatted PDF output.



---

## 📂 Project Structure

```
├── app.py                  # Core Flask server, OCR engine, normalization & PDF pipeline
├── create_mock.py          # Synthetic mock document generator script
├── requirements.txt        # Project dependencies
├── .env                    # Environment variables (Groq API Key)
├── uploads/                # Temporary uploaded files directory
└── reports/                # Generated PDF reports directory

```

---

## ⚖️ Evaluation & Disclaimer

This agent is designed as an automated pre-screening aid for document verification workflows (scheme enrollments, admissions, loan processing). Final verification judgments remain with human officers.