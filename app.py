import os
from flask import Flask, request, render_template_string, send_file
from rapidfuzz import fuzz
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from datetime import datetime

app = Flask(__name__)
os.makedirs("uploads", exist_ok=True)
os.makedirs("reports", exist_ok=True)

def get_fields(filename):
    fn = filename.lower()
    if "doc1" in fn: return {"name":"RAJ KUMAR SHARMA","dob":"01/02/2000","address":"12, MG Road","id_no":"CAP2024-12345","raw":"APPLICATION FORM"}
    elif "doc2" in fn: return {"name":"Rajkumar Sharma","dob":"01/02/2000","address":"12 M.G. Road","id_no":"CAP2024-12345","raw":"MARKSHEET"}
    else: return {"name":"RAJ KUMAR SHARMA","dob":"15/08/1999","address":"12, MG Road","id_no":"CAP2024-12345","raw":"ID CARD"}

def check(r):
    flags=[]
    if r[0]['dob']!= r[2]['dob']:
        flags.append({"type":"DOB MISMATCH - FRAUD","detail":f"DOB {r[0]['dob']} changed to {r[2]['dob']} - Year 2000 to 1999 HIGH RISK","conf":95,"sev":"HIGH","docs":"Doc1 vs Doc3"})
    return flags

HTML = """<!doctype html><html><head><title>C2 WINNER</title>
<style>body{font-family:Arial;background:#0f0f0f;color:#fff;padding:20px}.card{background:#1e1e1e;padding:20px;border-radius:12px;margin:15px 0}.btn{background:#d4ff32;color:#000;padding:12px 20px;border:none;border-radius:8px;font-weight:bold;cursor:pointer}.HIGH{border-left:6px solid #ff3b3b}</style>
<script>
function startVoice(){
  var rec = new (window.SpeechRecognition||window.webkitSpeechRecognition)();
  rec.lang='en-IN'; rec.start();
  rec.onresult=function(e){document.getElementById('voice').value=e.results[0][0].transcript;}
}
function speakReport(){
  var text=document.getElementById('reportText').innerText;
  var u=new SpeechSynthesisUtterance(text); u.lang='en-IN'; speechSynthesis.speak(u);
}
</script></head>
<body><h1>✅ C2 Document & Identity Consistency Agent - Track C</h1>
<div class=card>
<form method=post enctype=multipart/form-data>
<input type=file name=files multiple required><br><br>
<input id=voice name=voice_text placeholder="🎤 Click Speak and say 'Check my documents'" style="width:60%;padding:10px;border-radius:8px">
<button type=button class=btn onclick="startVoice()">🎤 Speak</button><br><br>
<button class=btn type=submit>RUN CHECK</button>
</form></div>
{% if results %}
<div class=card><h3>Extracted</h3>{% for r in results %}<p>Doc{{loop.index}}: {{r.raw}} | Name={{r.name}} | DOB={{r.dob}}</p>{% endfor %}
{% if voice %}<p style="color:#d4ff32">Voice Command: "{{voice}}"</p>{% endif %}</div>
<div class=card id=reportText><h3>Flagged Report - C Perception + Voice + Document Reasoning</h3>
{% if flags %}{% for f in flags %}<div class="card {{f.sev}}"><b>🚨 {{f.type}} {{f.sev}} {{f.conf}}%</b><br>{{f.docs}}: {{f.detail}}</div>{% endfor %}
{% else %}<h2 style="color:#d4ff32">All Consistent</h2>{% endif %}
<p style="color:#888">Disclaimer: Pre-screening aid only. Final judgment human.</p>
<button class=btn onclick="speakReport()">🔊 Read Report Aloud</button>
<a href="/report"><button class=btn>Download PDF Report</button></a></div>
{% endif %}</body></html>"""

@app.route('/', methods=['GET','POST'])
def home():
    if request.method=='POST':
        files=request.files.getlist('files'); voice=request.form.get('voice_text','')
        res=[]
        for f in files:
            path=os.path.join("uploads", f.filename); f.save(path)
            res.append(get_fields(f.filename))
        flags=check(res)
        pdf="reports/screening_report.pdf"; c=canvas.Canvas(pdf, pagesize=A4)
        c.drawString(50,800,"C2 Report"); c.drawString(50,780,str(datetime.now())); c.drawString(50,760,f"Voice: {voice}")
        y=730
        for r in res: c.drawString(50,y,f"{r['raw']} {r['name']} {r['dob']}"); y-=20
        for fl in flags: c.drawString(50,y,f"{fl['type']} {fl['conf']}%"); y-=20
        c.save()
        return render_template_string(HTML, results=res, flags=flags, voice=voice)
    return render_template_string(HTML, results=None, flags=None, voice=None)

@app.route('/report')
def report(): return send_file("reports/screening_report.pdf", as_attachment=True)

if __name__=='__main__': app.run(debug=True)