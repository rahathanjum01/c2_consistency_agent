import os
import re
import json
from datetime import datetime
from flask import Flask, request, render_template_string, send_file
from PIL import Image
import easyocr
from rapidfuzz import fuzz
from dateutil import parser
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from dotenv import load_dotenv
from groq import Groq

# 1. Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
os.makedirs("uploads", exist_ok=True)
os.makedirs("reports", exist_ok=True)

# 2. Initialize Clients
reader = easyocr.Reader(['en'])

# Groq client automatically picks up os.environ.get("GROQ_API_KEY")
groq_client = Groq() 

def normalize_date(date_str):
    """Normalize date strings into YYYY-MM-DD format."""
    try:
        dt = parser.parse(date_str, dayfirst=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return date_str.strip()

def normalize_address(addr_str):
    """Standardize address text to reduce false positives."""
    addr = addr_str.lower()
    replacements = {
        "m.g. road": "mg road",
        "m.g road": "mg road",
        "add:": "",
        "address:": "",
        ",": " ",
        "-": " "
    }
    for old, new in replacements.items():
        addr = addr.replace(old, new)
    return " ".join(addr.split())

def run_ocr(image_path):
    """Perform OCR extraction on image files."""
    results = reader.readtext(image_path, detail=0)
    raw_text = "\n".join(results)
    
    data = {"name": "", "dob": "", "address": "", "id_no": "", "raw": raw_text}
    
    # Extract fields via regex
    name_m = re.search(r'(?:Name|NAME)[:\s]+([A-Za-z\s]+)', raw_text)
    dob_m = re.search(r'(?:DOB|Date of Birth)[:\s]+([0-9A-Za-z/\-\s]+)', raw_text)
    addr_m = re.search(r'(?:Address|Add)[:\s]+([^\n]+)', raw_text)
    id_m = re.search(r'(?:Application ID|Roll No|ID No)[:\s]+([A-Z0-9\-]+)', raw_text)

    if name_m: data['name'] = name_m.group(1).strip().split('\n')[0]
    if dob_m: data['dob'] = normalize_date(dob_m.group(1).strip().split('\n')[0])
    if addr_m: data['address'] = normalize_address(addr_m.group(1).strip())
    if id_m: data['id_no'] = id_m.group(1).strip()
    
    return data

def run_llm_reasoning(extracted_docs, preliminary_flags):
    """Use Groq (Llama-3.3-70b) to synthesize cross-document findings."""
    # Check if key loaded properly
    if not os.getenv("GROQ_API_KEY"):
        return "Warning: GROQ_API_KEY missing in .env file. Falling back to automated checks."

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
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"LLM Reasoning unavailable: {str(e)}"

def evaluate_consistency(docs):
    """Cross-checks documents dynamically across Name, DOB, and Address."""
    flags = []
    n = len(docs)
    
    for i in range(n):
        for j in range(i + 1, n):
            d1, d2 = docs[i], docs[j]
            pair_label = f"Doc {i+1} vs Doc {j+1}"
            
            # DOB Check
            if d1['dob'] and d2['dob'] and d1['dob'] != d2['dob']:
                flags.append({
                    "type": "DOB MISMATCH",
                    "detail": f"DOB changed from '{d1['dob']}' to '{d2['dob']}'",
                    "conf": 95,
                    "sev": "HIGH",
                    "docs": pair_label
                })

            # Name Check (Fuzzy)
            if d1['name'] and d2['name']:
                ratio = fuzz.token_sort_ratio(d1['name'], d2['name'])
                if ratio < 75:
                    flags.append({
                        "type": "NAME MISMATCH",
                        "detail": f"Name mismatch: '{d1['name']}' vs '{d2['name']}'",
                        "conf": round(100 - ratio),
                        "sev": "HIGH",
                        "docs": pair_label
                    })
                elif ratio < 98:
                    flags.append({
                        "type": "NAME VARIATION",
                        "detail": f"Spelling variant: '{d1['name']}' vs '{d2['name']}'",
                        "conf": round(100 - ratio),
                        "sev": "LOW",
                        "docs": pair_label
                    })

            # Address Check (Fuzzy)
            if d1['address'] and d2['address']:
                addr_ratio = fuzz.token_set_ratio(d1['address'], d2['address'])
                if addr_ratio < 70:
                    flags.append({
                        "type": "ADDRESS MISMATCH",
                        "detail": f"Address discrepancy: '{d1['address']}' vs '{d2['address']}'",
                        "conf": round(100 - addr_ratio),
                        "sev": "MEDIUM",
                        "docs": pair_label
                    })

    return flags

HTML_TEMPLATE = """<!doctype html><html><head><title>C2 Identity Consistency Agent</title>
<style>
body{font-family:Arial,sans-serif;background:#0f0f0f;color:#fff;padding:20px}
.card{background:#1e1e1e;padding:20px;border-radius:12px;margin:15px 0}
.btn{background:#d4ff32;color:#000;padding:12px 20px;border:none;border-radius:8px;font-weight:bold;cursor:pointer}
.HIGH{border-left:6px solid #ff3b3b}.MEDIUM{border-left:6px solid #ffaa00}.LOW{border-left:6px solid #3b82f6}
.reasoning-box{background:#2a2a2a;padding:15px;border-radius:8px;white-space:pre-wrap;line-height:1.5}
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

<h3>🤖 Agent LLM Reasoning</h3>
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
            
        c.drawString(50, y - 20, "Disclaimer: Automated pre-screening aid. Final judgment remains human.")
        c.save()
        
        return render_template_string(HTML_TEMPLATE, results=results, flags=flags, voice=voice, llm_reasoning=llm_summary)
        
    return render_template_string(HTML_TEMPLATE, results=None, flags=None, voice=None, llm_reasoning=None)

@app.route('/report')
def report():
    return send_file("reports/screening_report.pdf", as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)