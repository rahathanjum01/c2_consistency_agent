import os
import re
import json
import warnings
from datetime import datetime
from flask import Flask, request, render_template_string, send_file
from PIL import Image
import easyocr
from rapidfuzz import fuzz
from dateutil import parser
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from dotenv import load_dotenv

# Suppress PyTorch DataLoader warning when running on CPU
warnings.filterwarnings("ignore", category=UserWarning)

load_dotenv()

app = Flask(__name__)
os.makedirs("uploads", exist_ok=True)
os.makedirs("reports", exist_ok=True)

reader = easyocr.Reader(['en'])

# Groq Client setup with environment fallback
groq_client = None
if os.getenv("GROQ_API_KEY"):
    try:
        from groq import Groq
        groq_client = Groq()
    except Exception:
        groq_client = None

def normalize_date(date_str):
    """Normalizes any generic date format into Indian standard DD-MM-YYYY."""
    if not date_str:
        return ""
    
    # Pre-clean common OCR character misreads in dates
    clean = date_str.replace("'", " ").replace(",", " ").replace(".", " ")
    clean = re.sub(r'[O|o]', '0', clean)
    clean = re.sub(r'[I|l|L]', '1', clean)
    clean = " ".join(clean.split()).strip()

    # 1. Text Month Pattern (e.g., "1 Feb 2000", "15 August 1999")
    text_month_match = re.search(r'(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})', clean, re.IGNORECASE)
    if text_month_match:
        day, month_str, year = text_month_match.groups()
        try:
            dt = datetime.strptime(f"{int(day):02d} {month_str[:3].capitalize()} {year}", "%d %b %Y")
            return dt.strftime("%d-%m-%Y")
        except Exception:
            pass

    # 2. Numeric Pattern (e.g., "01/02/2000", "15-08-1999")
    num_date_match = re.search(r'(\d{1,2})[/\-\s]+(\d{1,2})[/\-\s]+(\d{4})', clean)
    if num_date_match:
        d1, d2, year = num_date_match.groups()
        try:
            return f"{int(d1):02d}-{int(d2):02d}-{year}"
        except Exception:
            pass

    # 3. Fallback parser using DD-MM-YYYY output
    try:
        anchor = datetime(2000, 1, 1)
        dt = parser.parse(clean, dayfirst=True, default=anchor)
        return dt.strftime("%d-%m-%Y")
    except Exception:
        return date_str.strip()

def normalize_address(addr_str):
    """Clean OCR typos in address while preserving original commas and formatting."""
    if not addr_str:
        return ""
        
    addr = addr_str.strip()
    
    # Standardize common Indian address abbreviations & common OCR errors
    replacements = {
        r'\brcad\b': 'Road',
        r'\bfoad\b': 'Road',
        r'\bm\.g\.\b': 'MG',
        r'\bm\.g\b': 'MG',
        r'\badd:\b': '',
        r'\baddress:\b': ''
    }
    
    for pattern, rep in replacements.items():
        addr = re.sub(pattern, rep, addr, flags=re.IGNORECASE)

    # Format words cleanly into Title Case without removing commas/hyphens
    words = addr.split()
    formatted = []
    for w in words:
        # Keep punctuation attached to the word
        core = re.sub(r'[^\w\s]', '', w)
        punct = w[len(core):] if len(core) < len(w) else ""
        
        if core.upper() in ["MG", "ID", "PO", "ROAD", "NO"]:
            formatted.append(core.upper() + punct)
        elif core.isdigit():
            formatted.append(core + punct)
        else:
            formatted.append(core.capitalize() + punct)
            
    res = " ".join(formatted).strip()
    # Ensure standard comma separation after house numbers if missing
    res = re.sub(r'(\d+)\s+(MG|Road|Street|Avenue)', r'\1, \2', res, flags=re.IGNORECASE)
    return res

def run_ocr(image_path):
    """Generalized OCR field extraction engine with strict line boundaries."""
    results = reader.readtext(image_path, detail=0)
    lines = [line.strip() for line in results if line.strip()]
    raw_text = "\n".join(lines)
    
    data = {"name": "", "dob": "", "address": "", "id_no": "", "raw": raw_text}
    
    # Generic Multilingual Key Match Patterns with Lookahead Boundaries
    name_patterns = r'(?:Name|Full Name|Applicant Name|Holder Name|NAME)[:\s]*([A-Za-z\s\.]+?)(?=\s+(?:DOB|Date|Address|Add|Roll|ID)|$)'
    dob_patterns = r'(?:DOB|Date of Birth|Birth Date|Date Of Birth|DOB:)[:\s]*([0-9A-Za-z/\-\s\',]+?)(?=\s+(?:Address|Add|Roll|ID|Application|Card|No)|$)'
    addr_patterns = r'(?:Address|Add|Residential Address|Permanent Address|ADD)[:\s]*([^\n]+)'
    id_patterns = r'(?:Application ID|Roll No|ID No|ID Number|Aadhaar|PAN|Passport No|Card No)[:\s]*([A-Z0-9\-]+)'

    # 1. First Pass: Regex over global block
    n_match = re.search(name_patterns, raw_text, re.IGNORECASE)
    d_match = re.search(dob_patterns, raw_text, re.IGNORECASE)
    a_match = re.search(addr_patterns, raw_text, re.IGNORECASE)
    i_match = re.search(id_patterns, raw_text, re.IGNORECASE)

    if n_match: data['name'] = n_match.group(1).strip()
    if d_match: data['dob'] = normalize_date(d_match.group(1).strip())
    if a_match: data['address'] = normalize_address(a_match.group(1).strip())
    if i_match: data['id_no'] = i_match.group(1).strip()

    # 2. Second Pass: Line-by-Line fallback if first pass missed
    for idx, line in enumerate(lines):
        if not data['name'] and re.search(r'\bName\b', line, re.I):
            val = re.sub(r'.*Name[:\s]*', '', line, flags=re.I).strip()
            if val: data['name'] = val
            elif idx + 1 < len(lines): data['name'] = lines[idx+1]

        if not data['dob'] and re.search(r'\b(DOB|Birth|Date)\b', line, re.I):
            val = re.sub(r'.*(DOB|Birth|Date)[:\s]*', '', line, flags=re.I).strip()
            # Truncate any accidental trailing address words
            val = re.split(r'\b(Address|Add|Roll|ID)\b', val, flags=re.I)[0].strip()
            if val: data['dob'] = normalize_date(val)

        if not data['address'] and re.search(r'\b(Address|Add)\b', line, re.I):
            val = re.sub(r'.*(Address|Add)[:\s]*', '', line, flags=re.I).strip()
            if val: data['address'] = normalize_address(val)

    # 3. Third Pass: Standalone Date Search fallback
    if not data['dob']:
        dob_standalone = re.search(r'([0-3]?[0-9][/\-\s\'][0-1]?[0-9][/\-\s\'][1-2][0-9]{3}|[0-3]?[0-9]\s+[A-Za-z]{3,9}\s+[1-2][0-9]{3})', raw_text)
        if dob_standalone:
            data['dob'] = normalize_date(dob_standalone.group(1))

    return data

def evaluate_consistency(docs):
    """Dynamic N x N cross-matching for any number of uploaded files."""
    flags = []
    n = len(docs)
    
    for i in range(n):
        for j in range(i + 1, n):
            d1, d2 = docs[i], docs[j]
            pair_label = f"Doc {i+1} vs Doc {j+1}"
            
            # 1. DOB Matching
            if d1['dob'] and d2['dob'] and d1['dob'] != d2['dob']:
                flags.append({
                    "type": "DOB MISMATCH",
                    "detail": f"DOB discrepancy: '{d1['dob']}' vs '{d2['dob']}' - High Risk",
                    "conf": 95,
                    "sev": "HIGH",
                    "docs": pair_label
                })

            # 2. Name Matching Logic (handles spelling variations & partial name matches)
            if d1['name'] and d2['name']:
                token_set = fuzz.token_set_ratio(d1['name'], d2['name'])
                partial = fuzz.partial_ratio(d1['name'].lower(), d2['name'].lower())
                
                if token_set < 50 and partial < 50:
                    flags.append({
                        "type": "NAME MISMATCH",
                        "detail": f"Name mismatch: '{d1['name']}' vs '{d2['name']}'",
                        "conf": round(100 - token_set),
                        "sev": "HIGH",
                        "docs": pair_label
                    })
                elif token_set < 100 or partial < 100:
                    flags.append({
                        "type": "NAME VARIATION",
                        "detail": f"Spelling/format variation: '{d1['name']}' vs '{d2['name']}'",
                        "conf": round(100 - token_set),
                        "sev": "LOW",
                        "docs": pair_label
                    })

            # 3. Address Fuzzy Matching
            if d1['address'] and d2['address']:
                addr_ratio = fuzz.token_set_ratio(d1['address'].lower(), d2['address'].lower())
                if addr_ratio < 60:
                    flags.append({
                        "type": "ADDRESS MISMATCH",
                        "detail": f"Address discrepancy: '{d1['address']}' vs '{d2['address']}'",
                        "conf": round(100 - addr_ratio),
                        "sev": "MEDIUM",
                        "docs": pair_label
                    })

    return flags

def run_llm_reasoning(extracted_docs, preliminary_flags):
    """Hybrid Reasoning Agent: Tries online LLM, falls back to offline engine."""
    if groq_client:
        prompt = f"""
        You are an expert Document & Identity Consistency Reasoning Agent.
        Review the extracted data from {len(extracted_docs)} uploaded user documents and the heuristic flags detected.

        EXTRACTED DATA:
        {json.dumps(extracted_docs, indent=2)}

        HEURISTIC FLAGS:
        {json.dumps(preliminary_flags, indent=2)}

        Provide a concise synthesis for a human reviewer:
        1. Summarize overall consistency status across Name, DOB, and Address.
        2. Highlight any potential identity fraud or discrepancies.
        3. Include a clear disclaimer stating final judgment remains human.
        """
        for model_id in ["llama-3.3-70b-versatile", "llama3-8b-8192", "mixtral-8x7b-32768"]:
            try:
                res = groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=model_id,
                )
                return f"[Groq LLM ({model_id}) Reasoning Synthesis]\n\n" + res.choices[0].message.content
            except Exception:
                continue

    # Offline Hybrid Reasoning Agent Fallback
    high_flags = [f for f in preliminary_flags if f['sev'] == 'HIGH']
    low_flags = [f for f in preliminary_flags if f['sev'] in ['MEDIUM', 'LOW']]
    
    summary = ["🧠 [Agent Reasoning Engine Synthesis]\n"]
    if high_flags:
        summary.append("⚠️ VERIFICATION STATUS: HIGH RISK (DISCREPANCIES DETECTED)")
        summary.append("Critical cross-document discrepancies were detected:")
        for f in high_flags:
            summary.append(f"• {f['type']} in {f['docs']}: {f['detail']}")
    else:
        summary.append("✅ VERIFICATION STATUS: PASSED / LOW RISK")

    if low_flags:
        summary.append("\nℹ️ MINOR VARIATIONS (NON-FRAUD):")
        for f in low_flags:
            summary.append(f"• {f['type']} in {f['docs']}: {f['detail']}")

    summary.append("\n📋 AGENT RECOMMENDATION:")
    if high_flags:
        summary.append("Manual reviewer attention required due to potential identity mismatch or date alteration.")
    else:
        summary.append("All primary identity fields are consistent across the uploaded documents.")

    summary.append("\nDisclaimer: Automated pre-screening aid only. Final judgment remains with human officers.")
    return "\n".join(summary)

HTML_TEMPLATE = """<!doctype html><html><head><title>C2 Identity Consistency Agent</title>
<style>
body{font-family:Arial,sans-serif;background:#0f0f0f;color:#fff;padding:20px}
.card{background:#1e1e1e;padding:20px;border-radius:12px;margin:15px 0}
.btn{background:#d4ff32;color:#000;padding:12px 20px;border:none;border-radius:8px;font-weight:bold;cursor:pointer}
.HIGH{border-left:6px solid #ff3b3b}.MEDIUM{border-left:6px solid #ffaa00}.LOW{border-left:6px solid #3b82f6}
.reasoning-box{background:#2a2a2a;padding:15px;border-radius:8px;white-space:pre-wrap;line-height:1.5;font-family:monospace}
</style>
<script>
function startVoice(){
  var rec = new (window.SpeechRecognition||window.webkitSpeechRecognition)();
  rec.lang='en-IN'; rec.start();
  rec.onresult=function(e){
    document.getElementById('voice').value=e.results[0][0].transcript;
    document.getElementById('docForm').submit();
  }
}
function speakReport(){
  var text=document.getElementById('reportText').innerText;
  var u=new SpeechSynthesisUtterance(text); u.lang='en-IN'; speechSynthesis.speak(u);
}
</script></head>
<body>
<h1>✅ C2 Document & Identity Consistency Agent</h1>
<div class="card">
<form id="docForm" method="post" enctype="multipart/form-data">
<input type="file" name="files" multiple required><br><br>
<input id="voice" name="voice_text" placeholder="🎤 Voice Trigger (e.g., 'Check my documents')" style="width:60%;padding:10px;border-radius:8px">
<button type="button" class="btn" onclick="startVoice()">🎤 Voice Trigger</button><br><br>
<button class="btn" type="submit">RUN CHECK</button>
</form></div>
{% if results %}
<div class="card"><h3>Extracted Fields</h3>
{% for r in results %}
<p><b>Doc {{loop.index}}:</b> Name: {{r.name}} | DOB: {{r.dob}} | Address: {{r.address}}</p>
{% endfor %}
{% if voice %}<p style="color:#d4ff32">Voice Command: "{{voice}}"</p>{% endif %}</div>
<div class="card" id="reportText"><h3>Flagged Screening Report</h3>
{% if flags %}{% for f in flags %}
<div class="card {{f.sev}}"><b>🚨 {{f.type}} [{{f.sev}}] (Conf: {{f.conf}}%)</b><br>{{f.docs}}: {{f.detail}}</div>
{% endfor %}{% else %}<h2 style="color:#d4ff32">All Documents Consistent</h2>{% endif %}

<h3>🤖 Agent Reasoning Report</h3>
<div class="reasoning-box">{{llm_reasoning}}</div>

<p style="color:#888;margin-top:15px"><b>Disclaimer:</b> Pre-screening aid only. Final judgment remains human.</p>
<button class="btn" onclick="speakReport()">🔊 Read Report Aloud</button>
<a href="/report"><button class="btn">Download PDF Report</button></a></div>
{% endif %}</body></html>"""

@app.route('/', methods=['GET','POST'])
def home():
    if request.method == 'POST':
        files = request.files.getlist('files')
        voice = request.form.get('voice_text','')
        results = []
        
        for f in files:
            path = os.path.join("uploads", f.filename)
            f.save(path)
            results.append(run_ocr(path))
            
        flags = evaluate_consistency(results)
        llm_summary = run_llm_reasoning(results, flags)
        
        # Build Report PDF
        pdf_path = "reports/screening_report.pdf"
        c = canvas.Canvas(pdf_path, pagesize=A4)
        c.drawString(50, 800, "C2 Identity Verification Summary")
        c.drawString(50, 780, f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if voice: c.drawString(50, 760, f"Voice Prompt: {voice}")
        
        y = 720
        c.drawString(50, y, "Extracted Fields:")
        y -= 20
        for idx, r in enumerate(results):
            c.drawString(70, y, f"Doc {idx+1}: Name={r['name']}, DOB={r['dob']}")
            y -= 15
            
        y -= 10
        c.drawString(50, y, "Consistency Flags:")
        y -= 20
        for fl in flags:
            c.drawString(70, y, f"[{fl['sev']}] {fl['type']}: {fl['detail']}")
            y -= 15
            
        c.drawString(50, y - 20, "Disclaimer: Pre-screening aid only. Final judgment remains human.")
        c.save()
        
        return render_template_string(HTML_TEMPLATE, results=results, flags=flags, voice=voice, llm_reasoning=llm_summary)
        
    return render_template_string(HTML_TEMPLATE, results=None, flags=None, voice=None, llm_reasoning=None)

@app.route('/report')
def report():
    return send_file("reports/screening_report.pdf", as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)