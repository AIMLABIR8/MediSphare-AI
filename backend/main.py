import os
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from datetime import datetime
import requests
from dotenv import load_dotenv


# ================== LOAD ENV ==================
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# ================== FOLDERS ==================
UPLOAD_FOLDER = "backend/uploads"
REPORTS_FOLDER = "backend/reports"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORTS_FOLDER, exist_ok=True)

# ================== FASTAPI ==================
app = FastAPI(title="Medical AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================== RAG (OPTIONAL) ==================
try:
    from rag import load_rag_chain, analyze_medical_report, analyze_medical_image
    rag_chain = load_rag_chain()
    USE_RAG = True
except Exception as e:
    print("RAG Load Failed:", e)
    rag_chain = None
    USE_RAG = False

# ================== MODELS ==================
class QueryRequest(BaseModel):
    query: str

class Symptoms(BaseModel):
    symptoms: str

# ================== DISEASE DATABASE ==================
disease_db = {
    "Common Cold / Flu": ["fever", "cough", "sore throat", "runny nose", "fatigue"],
    "Migraine": ["headache", "nausea", "sensitivity to light", "vomiting"],
    "Heart Disease": ["chest pain", "shortness of breath", "fatigue", "dizziness"],
    "Diabetes": ["frequent urination", "increased thirst", "fatigue", "blurred vision"],
    "Gastritis": ["stomach pain", "nausea", "vomiting", "bloating"],
    "Kidney Infection": ["fever", "pain in side", "frequent urination", "nausea"],
    "Pneumonia": ["fever", "cough", "shortness of breath", "chest pain"],
    "Hypertension": ["headache", "dizziness", "blurred vision", "fatigue"],
}

disease_advice = {
    "Common Cold / Flu": "Rest, hydrate, consult a doctor if fever persists.",
    "Migraine": "Rest, avoid bright lights, consult a doctor if severe.",
    "Heart Disease": "Seek immediate medical attention.",
    "Diabetes": "Consult a doctor for blood sugar management.",
    "Gastritis": "Avoid spicy food and consult a doctor if pain persists.",
    "Kidney Infection": "Seek medical attention and stay hydrated.",
    "Pneumonia": "See a doctor urgently; antibiotics may be needed.",
    "Hypertension": "Monitor blood pressure and consult a doctor."
}

# ================== UTILS ==================
def calculate_risk(match_ratio: float):
    if match_ratio >= 0.6:
        return "High"
    elif match_ratio >= 0.3:
        return "Medium"
    else:
        return "Low"

def query_groq_ai(prompt: str):
    if not GROQ_API_KEY:
        return "⚠️ Groq API key missing. Add it in .env"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama3-70b-8192",  # 🔥 better model
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload)
        data = response.json()

        if response.status_code == 200:
            return data["choices"][0]["message"]["content"]
        else:
            return f"❌ Groq Error: {data}"
    except Exception as e:
        return f"❌ API Error: {str(e)}"

# ================== ROUTES ==================
@app.get("/")
def home():
    return {"message": "✅ Medical AI Backend Running"}


# ================== CHAT ==================
@app.post("/chat")
def chat(request: QueryRequest):

    # 🔬 USE RAG IF AVAILABLE
    if USE_RAG and rag_chain:
        try:
            response = rag_chain.invoke({'input': request.query})

            return {
                "answer": response["answer"],
                "sources": [
                    {
                        "metadata": doc.metadata,
                        "content": doc.page_content[:200]
                    }
                    for doc in response["context"]
                ]
            }

        except Exception as e:
            print("RAG Error:", e)

    # 🤖 FALLBACK → GROQ
    answer = query_groq_ai(request.query)
    return {"answer": answer, "sources": []}


# ================== FILE UPLOAD ==================
@app.post("/upload")
async def upload_report(file: UploadFile = File(...)):

    content = await file.read()

    if file.filename.lower().endswith(".pdf"):
        file_type = "PDF"
    elif file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        file_type = "Image"
    else:
        return JSONResponse({"error": "Only PDF/Image allowed"}, status_code=400)

    upload_path = os.path.join(UPLOAD_FOLDER, file.filename)

    with open(upload_path, "wb") as f:
        f.write(content)

    try:
        if file_type == "PDF":
            analysis = analyze_medical_report(upload_path)
        else:
            analysis = analyze_medical_image(upload_path)

        report_name = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        report_path = os.path.join(REPORTS_FOLDER, report_name)

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"""
MEDICAL REPORT
====================

File: {file.filename}
Time: {datetime.now()}

{analysis}

⚠️ AI Generated. Consult doctor.
""")

        return {
            "analysis": analysis,
            "report_filename": report_name
        }

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ================== DOWNLOAD REPORT ==================
@app.get("/download_report/{report_filename}")
def download_report(report_filename: str):

    path = os.path.join(REPORTS_FOLDER, report_filename)

    if not os.path.exists(path):
        return JSONResponse({"error": "Not found"}, status_code=404)

    return FileResponse(path, filename=report_filename)


# ================== DISEASE PREDICT ==================
@app.post("/predict")
def predict(data: Symptoms):

    user_symptoms = [s.strip().lower() for s in data.symptoms.split(",")]

    results = []

    for disease, symptoms in disease_db.items():
        match = sum(1 for s in user_symptoms if s in symptoms)

        if match > 0:
            ratio = match / len(symptoms)

            results.append({
                "disease": disease,
                "match_percent": round(ratio * 100, 1),
                "risk": calculate_risk(ratio),
                "advice": disease_advice[disease]
            })

    if not results:
        return {"message": "No match found. Consult doctor."}

    results.sort(key=lambda x: x["match_percent"], reverse=True)

    return {"predictions": results}

#================== IN-MEMORY DB ==================#
appointments = []
reviews_db = []

#================== 🏥 NEARBY HOSPITALS ==================#
@app.get("/hospitals")
def get_hospitals(lat: float, lng: float):

    url = "http://overpass-api.de/api/interpreter"

    query = f"""
    [out:json];
    node
      ["amenity"="hospital"]
      (around:5000,{lat},{lng});
    out;
    """

    response = requests.get(url, params={'data': query})
    data = response.json()

    hospitals = []

    for h in data.get("elements", []):
        hospitals.append({
            "name": h.get("tags", {}).get("name", "Unknown"),
            "lat": h.get("lat"),
            "lng": h.get("lon")
        })

    return {"hospitals": hospitals}

#================== 👨‍⚕️ DOCTOR FINDER ==================#
@app.get("/doctors")
def get_doctors(specialty: str):

    doctors = [
        {"name": "Dr. Sharma", "specialty": "Cardiologist", "location": "Kolkata"},
        {"name": "Dr. Roy", "specialty": "Dentist", "location": "Kolkata"},
        {"name": "Dr. Khan", "specialty": "Dermatologist", "location": "Kolkata"},
    ]

    result = [d for d in doctors if specialty.lower() in d["specialty"].lower()]

    if not result:
        return {"message": "No doctors found"}

    return result

#================== 📅 APPOINTMENT SYSTEM ==================#
class Appointment(BaseModel):
    name: str
    doctor: str
    date: str

@app.post("/appointment")
def book_appointment(app: Appointment):

    appointment = {
        "id": len(appointments) + 1,
        "name": app.name,
        "doctor": app.doctor,
        "date": app.date
    }

    appointments.append(appointment)

    return {"message": "Appointment booked", "data": appointment}


@app.get("/appointments")
def get_appointments():
    return appointments


#================== 💊 MEDICINE CHECKER ==================#
@app.get("/medicine")
def check_medicine(name: str):

    url = f"https://api.fda.gov/drug/label.json?search=openfda.brand_name:{name}&limit=1"

    try:
        res = requests.get(url)
        data = res.json()

        if "results" in data:
            return {
                "available": True,
                "info": data["results"][0].get("purpose", ["No info"])[0]
            }
        else:
            return {"available": False}

    except:
        return {"available": False}


#================== ⭐ REVIEWS SYSTEM ==================#

class Review(BaseModel):
    hospital: str
    review: str

@app.post("/reviews")
def add_review(r: Review):

    reviews_db.append({
        "hospital": r.hospital,
        "review": r.review,
        "time": str(datetime.now())
    })

    return {"message": "Review added"}


@app.get("/reviews")
def get_reviews():
    return reviews_db


#=============== AMBULANCE (SMART SIMULATION) ==================#
@app.get("/ambulance")
def ambulance():

    return {
        "status": "🚑 On the way",
        "distance": "1.8 km",
        "eta": "4 minutes",
        "driver": "Ramesh"
    }


# ================== COMPREHENSIVE MEDICINE DATABASE ==================

# Add this to your main.py - Complete Medicine Database with 50+ Medicines

MEDICINE_DB = {
    # Pain Relievers (8 medicines)
    "paracetamol": {
        "name": "Paracetamol (Acetaminophen)",
        "type": "OTC",
        "uses": "• Fever reduction\n• Mild to moderate pain relief\n• Headaches and migraines\n• Toothaches and dental pain\n• Muscle aches and backaches\n• Arthritis pain\n• Post-surgical pain\n• Cold and flu symptoms",
        "dosage": "• Adults: 500-1000mg every 4-6 hours\n• Maximum daily dose: 4000mg (4g)\n• Children: 10-15mg/kg every 4-6 hours\n• Elderly: Lower doses may be needed\n• Take with food if stomach upset occurs",
        "side_effects": "• Nausea and vomiting (rare at normal doses)\n• Allergic reactions (rash, hives)\n• Liver damage (with overdose)\n• Skin reactions (rare)\n• Headache (rare)",
        "warnings": "⚠️ Severe liver damage with overdose\n⚠️ Do not take with other products containing acetaminophen\n⚠️ Avoid alcohol consumption\n⚠️ Consult doctor if you have liver disease\n⚠️ Seek immediate help for overdose symptoms",
        "pregnancy_safety": "Category C - Generally considered safe during pregnancy when used as directed. Consult doctor before use.",
        "food_restrictions": "• Can be taken with or without food\n• Avoid alcohol completely\n• Stay hydrated with water",
        "alternatives": "• Ibuprofen (Advil, Motrin)\n• Aspirin\n• Naproxen (Aleve)\n• Diclofenac",
        "additional_info": "Most commonly used pain reliever worldwide. Does not reduce inflammation or affect blood clotting."
    },
    "ibuprofen": {
        "name": "Ibuprofen",
        "type": "OTC",
        "uses": "• Pain relief (menstrual, dental, muscle, back)\n• Fever reduction\n• Inflammation and swelling\n• Arthritis (rheumatoid and osteoarthritis)\n• Gout attacks\n• Ankylosing spondylitis\n• Juvenile arthritis\n• Post-surgical pain",
        "dosage": "• OTC Adults: 200-400mg every 4-6 hours (max 1200mg/day)\n• Prescription: Up to 800mg every 6-8 hours (max 3200mg/day)\n• Children: 5-10mg/kg every 6-8 hours\n• Take with food or milk",
        "side_effects": "• Stomach upset, nausea, heartburn\n• Diarrhea or constipation\n• Dizziness and headache\n• Fluid retention (edema)\n• Increased blood pressure\n• Kidney problems (long-term)",
        "warnings": "⚠️ Avoid with kidney disease\n⚠️ May increase risk of heart attack and stroke\n⚠️ Can cause stomach bleeding\n⚠️ May worsen asthma\n⚠️ Avoid during third trimester of pregnancy",
        "pregnancy_safety": "Category C - AVOID during third trimester. Use lowest effective dose in first two trimesters.",
        "food_restrictions": "• MUST take with food or milk\n• Avoid alcohol completely\n• Stay hydrated",
        "alternatives": "• Naproxen (Aleve)\n• Aspirin\n• Acetaminophen\n• Celecoxib (Celebrex)",
        "additional_info": "NSAID that works by blocking COX enzymes. Available as Advil, Motrin, and Nurofen."
    },
    "aspirin": {
        "name": "Aspirin (Acetylsalicylic Acid)",
        "type": "OTC",
        "uses": "• Pain relief (mild to moderate)\n• Fever reduction\n• Inflammation reduction\n• Heart attack prevention (low dose 81mg)\n• Stroke prevention\n• Migraine relief\n• Kawasaki disease treatment",
        "dosage": "• Pain/Fever: 325-650mg every 4-6 hours (max 4000mg/day)\n• Heart prevention: 81-100mg once daily\n• Stroke prevention: 75-100mg once daily\n• Take with food or milk",
        "side_effects": "• Stomach upset and heartburn\n• Nausea and vomiting\n• Easy bruising and bleeding\n• Ringing in ears (overdose sign)\n• Allergic reactions\n• Stomach bleeding (long-term)",
        "warnings": "⚠️ DO NOT give to children with viral infections (Reye's syndrome risk)\n⚠️ Can cause stomach bleeding\n⚠️ Stop 1 week before surgery\n⚠️ May trigger asthma attacks\n⚠️ Avoid during third trimester of pregnancy",
        "pregnancy_safety": "Category D - AVOID during third trimester. Low dose (81mg) may be used under doctor supervision.",
        "food_restrictions": "• Take with food or milk\n• Avoid alcohol completely\n• Drink plenty of water",
        "alternatives": "• Ibuprofen (Advil, Motrin)\n• Acetaminophen (Tylenol)\n• Clopidogrel (Plavix)\n• Warfarin",
        "additional_info": "One of the oldest and most studied medications. Low-dose 'baby aspirin' used for cardiovascular protection."
    },
    "naproxen": {
        "name": "Naproxen",
        "type": "OTC",
        "uses": "• Pain relief\n• Fever reduction\n• Inflammation\n• Arthritis\n• Menstrual cramps\n• Tendonitis\n• Bursitis\n• Gout attacks",
        "dosage": "• Adults: 220-440mg every 8-12 hours (max 660mg/day OTC)\n• Prescription: 250-500mg twice daily\n• Take with food or milk",
        "side_effects": "• Heartburn and stomach pain\n• Nausea\n• Dizziness\n• Drowsiness\n• Headache\n• Fluid retention\n• Ringing in ears",
        "warnings": "⚠️ Increased risk of heart attack and stroke\n⚠️ Can cause stomach bleeding\n⚠️ Avoid with kidney disease\n⚠️ May worsen asthma\n⚠️ Avoid during pregnancy",
        "pregnancy_safety": "Category C - Avoid during third trimester. Use lowest effective dose if necessary.",
        "food_restrictions": "• Take with food or milk\n• Avoid alcohol\n• Stay hydrated",
        "alternatives": "• Ibuprofen\n• Aspirin\n• Celecoxib\n• Meloxicam",
        "additional_info": "Longer-acting NSAID (every 12 hours). Available as Aleve, Naprosyn, and Anaprox."
    },
    "diclofenac": {
        "name": "Diclofenac",
        "type": "Prescription/OTC (topical)",
        "uses": "• Rheumatoid arthritis\n• Osteoarthritis\n• Ankylosing spondylitis\n• Acute pain\n• Menstrual cramps\n• Migraine (some forms)\n• Topical for joint pain",
        "dosage": "• Oral: 50mg 2-3 times daily (max 150mg/day)\n• Topical: Apply 4 times daily\n• Extended release: 100mg once daily",
        "side_effects": "• Stomach upset and ulcers\n• Nausea\n• Diarrhea\n• Headache\n• Dizziness\n• Rash\n• Liver enzyme elevation",
        "warnings": "⚠️ High risk of stomach ulcers\n⚠️ May increase cardiovascular risk\n⚠️ Can cause liver damage\n⚠️ Avoid with kidney disease\n⚠️ Not for use before surgery",
        "pregnancy_safety": "Category C - Avoid during third trimester. Not recommended during pregnancy.",
        "food_restrictions": "• Take with food\n• Avoid alcohol\n• Take with full glass of water",
        "alternatives": "• Ibuprofen\n• Naproxen\n• Celecoxib\n• Meloxicam",
        "additional_info": "Available as Voltaren, Cataflam, and Zipsor. Topical gel for localized pain."
    },
    "celecoxib": {
        "name": "Celecoxib",
        "type": "Prescription",
        "uses": "• Osteoarthritis\n• Rheumatoid arthritis\n• Ankylosing spondylitis\n• Acute pain\n• Menstrual cramps\n• Juvenile arthritis",
        "dosage": "• Osteoarthritis: 200mg once daily or 100mg twice daily\n• Rheumatoid arthritis: 100-200mg twice daily\n• Acute pain: 400mg first dose then 200mg",
        "side_effects": "• Stomach upset (less than other NSAIDs)\n• Diarrhea\n• Headache\n• Dizziness\n• Swelling of extremities\n• Increased blood pressure",
        "warnings": "⚠️ Increased risk of heart attack and stroke\n⚠️ Can cause serious stomach bleeding\n⚠️ Sulfa allergy - do not use\n⚠️ May worsen kidney function\n⚠️ Avoid in late pregnancy",
        "pregnancy_safety": "Category C - Avoid during third trimester. Not recommended during pregnancy.",
        "food_restrictions": "• Can be taken with or without food\n• Avoid alcohol\n• Stay hydrated",
        "alternatives": "• Ibuprofen\n• Naproxen\n• Meloxicam\n• Diclofenac",
        "additional_info": "COX-2 selective NSAID. Available as Celebrex. Less stomach irritation than other NSAIDs."
    },
    "ketorolac": {
        "name": "Ketorolac",
        "type": "Prescription",
        "uses": "• Moderate to severe acute pain\n• Post-surgical pain\n• Renal colic\n• Migraine headaches\n• Musculoskeletal pain",
        "dosage": "• Oral: 10mg every 4-6 hours (max 40mg/day)\n• IM/IV: 30-60mg single dose\n• Maximum treatment: 5 days\n• Not for chronic use",
        "side_effects": "• Stomach pain\n• Nausea\n• Drowsiness\n• Dizziness\n• Headache\n• Fluid retention\n• Increased bleeding risk",
        "warnings": "⚠️ Do not use for more than 5 days\n⚠️ High risk of stomach bleeding and ulcers\n⚠️ Avoid with kidney disease\n⚠️ Can increase bleeding risk\n⚠️ Not for use before surgery",
        "pregnancy_safety": "Category C - Avoid during pregnancy, especially third trimester.",
        "food_restrictions": "• Take with food or milk\n• Avoid alcohol\n• Stay hydrated",
        "alternatives": "• Ibuprofen\n• Diclofenac\n• Tramadol\n• Morphine (for severe pain)",
        "additional_info": "Potent NSAID for short-term pain management. Injectable form available. Available as Toradol."
    },
    "nimesulide": {
        "name": "Nimesulide",
        "type": "Prescription",
        "uses": "• Acute pain\n• Fever\n• Osteoarthritis\n• Primary dysmenorrhea\n• Dental pain\n• Post-surgical inflammation",
        "dosage": "• Adults: 100mg twice daily\n• Maximum: 200mg/day\n• Short-term use only (15 days max)\n• Take after meals",
        "side_effects": "• Nausea\n• Diarrhea\n• Stomach pain\n• Heartburn\n• Dizziness\n• Rash\n• Liver enzyme elevation",
        "warnings": "⚠️ Risk of liver damage (withdrawn in many countries)\n⚠️ Short-term use only\n⚠️ Avoid in liver disease\n⚠️ Not for children\n⚠️ Monitor liver function",
        "pregnancy_safety": "Category C - Avoid during pregnancy and breastfeeding.",
        "food_restrictions": "• Take after meals\n• Avoid alcohol\n• Avoid with other NSAIDs",
        "alternatives": "• Ibuprofen\n• Paracetamol\n• Diclofenac\n• Celecoxib",
        "additional_info": "NSAID with selective COX-2 inhibition. Not available in some countries due to liver toxicity concerns."
    },
    
    # Antibiotics (8 medicines)
    "amoxicillin": {
        "name": "Amoxicillin",
        "type": "Prescription",
        "uses": "• Bacterial infections of ear, nose, and throat\n• Pneumonia and bronchitis\n• Urinary tract infections (UTIs)\n• Skin and soft tissue infections\n• Dental abscesses\n• H. pylori infection\n• Lyme disease",
        "dosage": "• Adults: 250-500mg every 8 hours or 500-875mg every 12 hours\n• Children: 20-40mg/kg/day divided every 8-12 hours\n• Complete full course",
        "side_effects": "• Diarrhea (most common)\n• Nausea and vomiting\n• Skin rash\n• Yeast infections\n• Headache\n• Metallic taste",
        "warnings": "⚠️ Complete full course even if feeling better\n⚠️ Not effective against viral infections\n⚠️ May cause severe allergic reactions\n⚠️ Can reduce effectiveness of oral contraceptives",
        "pregnancy_safety": "Category B - Generally considered safe during pregnancy. Compatible with breastfeeding.",
        "food_restrictions": "• Can be taken with or without food\n• Avoid alcohol during treatment\n• Take with full glass of water",
        "alternatives": "• Cephalexin (Keflex)\n• Azithromycin (Zithromax)\n• Clindamycin\n• Doxycycline",
        "additional_info": "Penicillin-class antibiotic. Often combined with clavulanic acid (Augmentin) to overcome resistance."
    },
    "azithromycin": {
        "name": "Azithromycin",
        "type": "Prescription",
        "uses": "• Respiratory tract infections\n• Pneumonia\n• Bronchitis\n• Sinusitis\n• Pharyngitis\n• Skin infections\n• STDs (chlamydia, gonorrhea)\n• Ear infections",
        "dosage": "• Z-Pak: 500mg day 1, then 250mg days 2-5\n• STD: 1g single dose\n• Children: 10mg/kg day 1, then 5mg/kg days 2-5",
        "side_effects": "• Diarrhea\n• Nausea\n• Abdominal pain\n• Vomiting\n• Headache\n• Liver enzyme elevation (rare)",
        "warnings": "⚠️ May cause heart rhythm problems (QT prolongation)\n⚠️ Can cause severe allergic reactions\n⚠️ May worsen myasthenia gravis\n⚠️ Not for patients with liver disease",
        "pregnancy_safety": "Category B - Generally considered safe during pregnancy. Compatible with breastfeeding.",
        "food_restrictions": "• Take on empty stomach (1 hour before or 2 hours after food)\n• Avoid antacids containing aluminum or magnesium",
        "alternatives": "• Amoxicillin\n• Clarithromycin\n• Doxycycline\n• Levofloxacin",
        "additional_info": "Macrolide antibiotic with long half-life. Z-Pak is 5-day course. Available as Zithromax."
    },
    "cephalexin": {
        "name": "Cephalexin",
        "type": "Prescription",
        "uses": "• Respiratory tract infections\n• Skin and soft tissue infections\n• Bone infections\n• Urinary tract infections\n• Ear infections\n• Dental infections",
        "dosage": "• Adults: 250-500mg every 6 hours or 500mg every 12 hours\n• Children: 25-50mg/kg/day divided every 6-12 hours\n• Severe infections: Up to 4g/day",
        "side_effects": "• Diarrhea\n• Nausea\n• Vomiting\n• Dyspepsia\n• Abdominal pain\n• Rash\n• Genital itching",
        "warnings": "⚠️ Cross-allergy with penicillins (10%)\n⚠️ Complete full course\n⚠️ May cause C. diff diarrhea\n⚠️ Can reduce contraceptive effectiveness",
        "pregnancy_safety": "Category B - Generally considered safe during pregnancy. Compatible with breastfeeding.",
        "food_restrictions": "• Can be taken with or without food\n• Take with food if stomach upset occurs\n• Avoid alcohol",
        "alternatives": "• Amoxicillin\n• Cefuroxime\n• Cefdinir\n• Clindamycin",
        "additional_info": "First-generation cephalosporin antibiotic. Available as Keflex and Biocef."
    },
    "ciprofloxacin": {
        "name": "Ciprofloxacin",
        "type": "Prescription",
        "uses": "• Urinary tract infections\n• Respiratory infections\n• Skin infections\n• Bone and joint infections\n• Infectious diarrhea\n• Typhoid fever\n• Anthrax exposure",
        "dosage": "• Adults: 250-750mg every 12 hours\n• Complicated UTIs: 500-750mg every 12 hours\n• Duration: 7-14 days typically",
        "side_effects": "• Nausea\n• Diarrhea\n• Vomiting\n• Rash\n• Headache\n• Restlessness\n• Tendonitis (rare)",
        "warnings": "⚠️ Risk of tendon rupture (especially Achilles)\n⚠️ May worsen myasthenia gravis\n⚠️ Can cause peripheral neuropathy\n⚠️ Avoid in children (cartilage damage risk)\n⚠️ May cause photosensitivity",
        "pregnancy_safety": "Category C - Avoid during pregnancy. Avoid during breastfeeding.",
        "food_restrictions": "• Take on empty stomach\n• Avoid dairy products, calcium-fortified juices\n• Stay well hydrated",
        "alternatives": "• Levofloxacin\n• Nitrofurantoin (for UTIs)\n• Cefixime\n• Doxycycline",
        "additional_info": "Fluoroquinolone antibiotic. Available as Cipro. Has strong activity against gram-negative bacteria."
    },
    "doxycycline": {
        "name": "Doxycycline",
        "type": "Prescription",
        "uses": "• Respiratory infections\n• Acne\n• Rosacea\n• Lyme disease\n• Malaria prevention\n• Rocky Mountain spotted fever\n• Chlamydia",
        "dosage": "• Adults: 100mg every 12 hours day 1, then 100mg daily\n• Acne: 50-100mg daily\n• Malaria: 100mg daily starting 1-2 days before travel",
        "side_effects": "• Photosensitivity (sun sensitivity)\n• Nausea\n• Diarrhea\n• Vomiting\n• Esophagitis\n• Yeast infections\n• Tooth discoloration (children)",
        "warnings": "⚠️ Avoid in children under 8 (tooth discoloration)\n⚠️ Can cause severe sunburn\n⚠️ May reduce contraceptive effectiveness\n⚠️ Avoid with isotretinoin\n⚠️ Can cause pill esophagitis",
        "pregnancy_safety": "Category D - AVOID during pregnancy. Avoid during breastfeeding.",
        "food_restrictions": "• Take with full glass of water\n• Avoid dairy products within 2 hours\n• Do not lie down for 30 minutes after taking",
        "alternatives": "• Minocycline\n• Tetracycline\n• Azithromycin\n• Amoxicillin",
        "additional_info": "Tetracycline antibiotic. Available as Vibramycin, Doryx. Effective against atypical bacteria."
    },
    "clindamycin": {
        "name": "Clindamycin",
        "type": "Prescription",
        "uses": "• Skin and soft tissue infections\n• Respiratory infections\n• Bone and joint infections\n• Dental infections\n• Pelvic inflammatory disease\n• Bacterial vaginosis\n• Malaria (combination)",
        "dosage": "• Adults: 150-300mg every 6 hours\n• Severe infections: 300-450mg every 6 hours\n• Children: 8-20mg/kg/day divided every 6-8 hours",
        "side_effects": "• Diarrhea (common)\n• Nausea\n• Vomiting\n• Abdominal pain\n• Rash\n• Metallic taste (IV form)\n• C. diff colitis",
        "warnings": "⚠️ High risk of C. difficile associated diarrhea\n⚠️ Can cause severe pseudomembranous colitis\n⚠️ May cause liver damage\n⚠️ Not for meningitis treatment\n⚠️ Avoid with history of colitis",
        "pregnancy_safety": "Category B - Generally considered safe. Use only if clearly needed.",
        "food_restrictions": "• Can be taken with or without food\n• Take with full glass of water\n• Avoid alcohol",
        "alternatives": "• Amoxicillin-clavulanate\n• Cephalexin\n• Doxycycline\n• Linezolid",
        "additional_info": "Lincosamide antibiotic. Available as Cleocin. Excellent for anaerobic and skin infections."
    },
    "metronidazole": {
        "name": "Metronidazole",
        "type": "Prescription",
        "uses": "• Bacterial vaginosis\n• Trichomoniasis\n• Giardiasis\n• Amebiasis\n• Anaerobic bacterial infections\n• Dental infections\n• H. pylori (combination)",
        "dosage": "• Bacterial vaginosis: 500mg twice daily for 7 days\n• Trichomoniasis: 2g single dose\n• Anaerobic infections: 500mg every 6-8 hours\n• Children: 15-30mg/kg/day divided",
        "side_effects": "• Metallic taste\n• Nausea\n• Headache\n• Loss of appetite\n• Dark urine\n• Peripheral neuropathy (long-term)\n• Dizziness",
        "warnings": "⚠️ AVOID ALCOHOL (severe disulfiram-like reaction)\n⚠️ May cause peripheral neuropathy with prolonged use\n⚠️ Can cause seizures\n⚠️ Avoid with blood thinners (increases effect)\n⚠️ May darken urine (harmless)",
        "pregnancy_safety": "Category B - Use with caution. Avoid during first trimester if possible.",
        "food_restrictions": "• Take with food to reduce stomach upset\n• ABSOLUTELY NO ALCOHOL during and for 3 days after\n• Avoid grapefruit",
        "alternatives": "• Tinidazole\n• Secnidazole\n• Clindamycin\n• Vancomycin (for C. diff)",
        "additional_info": "Antibiotic and antiprotozoal. Available as Flagyl. Causes severe reaction with alcohol."
    },
    "levofloxacin": {
        "name": "Levofloxacin",
        "type": "Prescription",
        "uses": "• Pneumonia (community-acquired)\n• Chronic bronchitis\n• Sinusitis\n• Urinary tract infections\n• Prostatitis\n• Skin infections\n• Anthrax exposure",
        "dosage": "• Community-acquired pneumonia: 750mg daily for 5 days\n• UTI: 250-500mg daily for 3-10 days\n• Prostatitis: 500mg daily for 28 days\n• Take at same time each day",
        "side_effects": "• Nausea\n• Diarrhea\n• Headache\n• Dizziness\n• Insomnia\n• Tendonitis\n• Photosensitivity",
        "warnings": "⚠️ Risk of tendon rupture (all ages)\n⚠️ May cause peripheral neuropathy\n⚠️ Can worsen myasthenia gravis\n⚠️ Avoid in children\n⚠️ May cause QT prolongation",
        "pregnancy_safety": "Category C - Avoid during pregnancy and breastfeeding.",
        "food_restrictions": "• Can be taken with or without food\n• Stay well hydrated\n• Avoid calcium supplements within 2 hours",
        "alternatives": "• Ciprofloxacin\n• Moxifloxacin\n• Azithromycin\n• Doxycycline",
        "additional_info": "Fluoroquinolone antibiotic. Available as Levaquin. Good for respiratory and urinary infections."
    },
    
    # Cardiovascular (8 medicines)
    "lisinopril": {
        "name": "Lisinopril",
        "type": "Prescription",
        "uses": "• High blood pressure\n• Heart failure\n• Heart attack recovery\n• Diabetic kidney disease\n• Prevention of stroke and heart attack",
        "dosage": "• Hypertension: 10-40mg once daily\n• Heart failure: 5-20mg once daily\n• Starting dose: 10mg\n• Maximum: 40mg/day",
        "side_effects": "• Dry cough (common)\n• Dizziness\n• Headache\n• Increased potassium\n• Fatigue\n• Angioedema (rare)",
        "warnings": "⚠️ Can cause birth defects - avoid pregnancy\n⚠️ May cause kidney problems\n⚠️ Monitor potassium levels\n⚠️ May cause low blood pressure\n⚠️ Avoid with ARBs or aliskiren",
        "pregnancy_safety": "Category D - AVOID during pregnancy. Causes fetal harm.",
        "food_restrictions": "• Can be taken with or without food\n• Avoid salt substitutes (may increase potassium)\n• Limit alcohol",
        "alternatives": "• Losartan\n• Enalapril\n• Amlodipine\n• Hydrochlorothiazide",
        "additional_info": "ACE inhibitor. Available as Prinivil, Zestril. Dry cough affects 10-20% of users."
    },
    "amlodipine": {
        "name": "Amlodipine",
        "type": "Prescription",
        "uses": "• High blood pressure\n• Angina (chest pain)\n• Coronary artery disease\n• Vasospastic angina\n• Prevention of heart attack and stroke",
        "dosage": "• Starting: 5mg once daily\n• Maintenance: 5-10mg once daily\n• Maximum: 10mg/day\n• Elderly: 2.5mg starting",
        "side_effects": "• Swelling of ankles/feet (edema)\n• Dizziness\n• Flushing\n• Palpitations\n• Fatigue\n• Headache\n• Nausea",
        "warnings": "⚠️ May worsen heart failure\n⚠️ Can cause severe low blood pressure\n⚠️ Grapefruit juice interaction\n⚠️ Use caution in liver disease",
        "pregnancy_safety": "Category C - Use only if clearly needed. Consult doctor before use.",
        "food_restrictions": "• Avoid grapefruit and grapefruit juice\n• Can be taken with or without food\n• Limit alcohol",
        "alternatives": "• Nifedipine\n• Felodipine\n• Losartan\n• Lisinopril",
        "additional_info": "Calcium channel blocker. Available as Norvasc. Long-acting (once daily)."
    },
    "atorvastatin": {
        "name": "Atorvastatin",
        "type": "Prescription",
        "uses": "• High cholesterol\n• Triglyceride reduction\n• Heart attack prevention\n• Stroke prevention\n• Prevention of cardiovascular events",
        "dosage": "• Starting: 10-20mg once daily\n• Maintenance: 10-80mg once daily\n• Maximum: 80mg/day\n• Take at same time each day",
        "side_effects": "• Muscle pain\n• Joint pain\n• Diarrhea\n• Nausea\n• Increased blood sugar\n• Liver enzyme elevation",
        "warnings": "⚠️ Risk of muscle damage (rhabdomyolysis)\n⚠️ Monitor liver function\n⚠️ Avoid grapefruit juice\n⚠️ May increase diabetes risk",
        "pregnancy_safety": "Category X - DO NOT use during pregnancy. Stop 1-2 months before trying to conceive.",
        "food_restrictions": "• Avoid grapefruit and grapefruit juice\n• Can be taken with or without food\n• Limit alcohol",
        "alternatives": "• Rosuvastatin\n• Simvastatin\n• Ezetimibe\n• Pravastatin",
        "additional_info": "Statin medication. Available as Lipitor. One of most prescribed drugs worldwide."
    },
    "rosuvastatin": {
        "name": "Rosuvastatin",
        "type": "Prescription",
        "uses": "• High cholesterol\n• Triglyceride reduction\n• Heart attack prevention\n• Stroke prevention\n• Atherosclerosis treatment",
        "dosage": "• Starting: 5-10mg once daily\n• Maintenance: 5-40mg once daily\n• Maximum: 40mg/day\n• Asian patients: 5mg starting",
        "side_effects": "• Muscle pain\n• Headache\n• Nausea\n• Abdominal pain\n• Increased blood sugar\n• Liver enzyme elevation",
        "warnings": "⚠️ Risk of muscle damage (higher than other statins)\n⚠️ Monitor liver and kidney function\n⚠️ May increase diabetes risk\n⚠️ Avoid with cyclosporine",
        "pregnancy_safety": "Category X - DO NOT use during pregnancy. Stop before conception.",
        "food_restrictions": "• Can be taken with or without food\n• Avoid grapefruit juice\n• Limit alcohol",
        "alternatives": "• Atorvastatin\n• Simvastatin\n• Pravastatin\n• Ezetimibe",
        "additional_info": "Most potent statin. Available as Crestor. Better for lowering LDL cholesterol."
    },
    "losartan": {
        "name": "Losartan",
        "type": "Prescription",
        "uses": "• High blood pressure\n• Diabetic kidney disease\n• Heart failure\n• Stroke prevention\n• Left ventricular hypertrophy",
        "dosage": "• Hypertension: 50mg once daily (up to 100mg)\n• Heart failure: 12.5-50mg once daily\n• Diabetic nephropathy: 50-100mg once daily",
        "side_effects": "• Dizziness\n• Fatigue\n• Low blood pressure\n• Increased potassium\n• Back pain\n• Diarrhea",
        "warnings": "⚠️ Can cause birth defects - avoid pregnancy\n⚠️ May increase potassium levels\n⚠️ Can worsen kidney disease\n⚠️ Avoid with aliskiren in diabetics",
        "pregnancy_safety": "Category D - AVOID during pregnancy. Causes fetal harm.",
        "food_restrictions": "• Can be taken with or without food\n• Avoid salt substitutes (may increase potassium)\n• Limit alcohol",
        "alternatives": "• Valsartan (Diovan)\n• Irbesartan (Avapro)\n• Candesartan (Atacand)\n• Lisinopril",
        "additional_info": "ARB medication. Available as Cozaar. Better tolerated than ACE inhibitors (no cough)."
    },
    "clopidogrel": {
        "name": "Clopidogrel",
        "type": "Prescription",
        "uses": "• Recent heart attack\n• Recent stroke\n• Peripheral artery disease\n• Acute coronary syndrome\n• Stent thrombosis prevention",
        "dosage": "• 75mg once daily\n• Loading dose: 300-600mg (for ACS)\n• Take at same time each day",
        "side_effects": "• Bleeding (nosebleeds, bruising)\n• Diarrhea\n• Abdominal pain\n• Dyspepsia\n• Rash\n• TTP (rare)",
        "warnings": "⚠️ Increased bleeding risk\n⚠️ Stop 5 days before surgery\n⚠️ May be ineffective in poor metabolizers\n⚠️ Can cause TTP (medical emergency)",
        "pregnancy_safety": "Category B - Use only if clearly needed. Consult doctor.",
        "food_restrictions": "• Can be taken with or without food\n• No grapefruit interaction\n• Avoid alcohol",
        "alternatives": "• Ticagrelor (Brilinta)\n• Prasugrel (Effient)\n• Aspirin\n• Dipyridamole",
        "additional_info": "Antiplatelet agent. Available as Plavix. Often combined with aspirin (DAPT)."
    },
    "metoprolol": {
        "name": "Metoprolol",
        "type": "Prescription",
        "uses": "• High blood pressure\n• Angina (chest pain)\n• Heart failure\n• Heart attack prevention\n• Migraine prevention\n• Atrial fibrillation",
        "dosage": "• Hypertension: 50-100mg once daily (succinate)\n• Heart failure: 12.5-200mg once daily\n• Angina: 50-100mg twice daily (tartrate)\n• Maximum: 400mg/day",
        "side_effects": "• Fatigue\n• Dizziness\n• Slow heart rate (bradycardia)\n• Cold hands and feet\n• Shortness of breath\n• Depression\n• Sexual dysfunction",
        "warnings": "⚠️ Do not stop abruptly (may cause heart attack)\n⚠️ May mask signs of low blood sugar\n⚠️ Use caution in asthma/COPD\n⚠️ May worsen heart failure if too high dose",
        "pregnancy_safety": "Category C - Use only if benefits outweigh risks. May cause fetal bradycardia.",
        "food_restrictions": "• Take with food to reduce absorption variation\n• Avoid alcohol\n• Consistent timing each day",
        "alternatives": "• Atenolol\n• Bisoprolol\n• Carvedilol\n• Propranolol",
        "additional_info": "Beta-blocker. Available as Lopressor (tartrate) and Toprol XL (succinate). Cardio-selective."
    },
    "hydrochlorothiazide": {
        "name": "Hydrochlorothiazide",
        "type": "Prescription",
        "uses": "• High blood pressure\n• Edema (fluid retention)\n• Heart failure\n• Kidney stones (calcium)\n• Nephrogenic diabetes insipidus",
        "dosage": "• Hypertension: 12.5-25mg once daily\n• Edema: 25-100mg daily or every other day\n• Maximum: 200mg/day (short-term)",
        "side_effects": "• Increased urination\n• Low potassium (hypokalemia)\n• Low sodium\n• Dizziness\n• Headache\n• Increased blood sugar\n• Increased uric acid",
        "warnings": "⚠️ Monitor potassium and sodium levels\n⚠️ May worsen gout\n⚠️ Can cause sulfa allergy reactions\n⚠️ May increase blood sugar\n⚠️ Photosensitivity risk",
        "pregnancy_safety": "Category B - Generally safe in pregnancy. Avoid in breastfeeding.",
        "food_restrictions": "• Take with food to reduce stomach upset\n• Take in morning (to avoid nighttime urination)\n• Limit salt intake",
        "alternatives": "• Chlorthalidone\n• Furosemide (Lasix)\n• Spironolactone\n• Lisinopril",
        "additional_info": "Thiazide diuretic. Available as HydroDIURIL, Microzide. First-line for hypertension."
    },
    
    # Diabetes (5 medicines)
    "metformin": {
        "name": "Metformin",
        "type": "Prescription",
        "uses": "• Type 2 diabetes mellitus\n• Insulin resistance syndrome\n• Polycystic ovary syndrome (PCOS)\n• Prediabetes (prevention)\n• Gestational diabetes\n• Weight management",
        "dosage": "• Starting: 500mg twice daily or 850mg once daily\n• Maintenance: 1500-2000mg/day divided\n• Extended release: 500-2000mg once daily\n• Maximum: 2550mg/day",
        "side_effects": "• Nausea, vomiting, diarrhea\n• Stomach upset\n• Metallic taste\n• Decreased appetite\n• Vitamin B12 deficiency (long-term)\n• Lactic acidosis (rare)",
        "warnings": "⚠️ Risk of lactic acidosis (rare emergency)\n⚠️ Stop before contrast dye procedures\n⚠️ Monitor kidney function\n⚠️ Avoid excessive alcohol",
        "pregnancy_safety": "Category B - Generally considered safe during pregnancy. Often used for gestational diabetes.",
        "food_restrictions": "• Take WITH meals to reduce GI side effects\n• Avoid excessive alcohol\n• Extended release with evening meal",
        "alternatives": "• Glipizide\n• Sitagliptin\n• Pioglitazone\n• Empagliflozin",
        "additional_info": "First-line medication for type 2 diabetes. Does not cause weight gain. Available as Glucophage."
    },
    "glipizide": {
        "name": "Glipizide",
        "type": "Prescription",
        "uses": "• Type 2 diabetes mellitus\n• Adjunct to diet and exercise\n• Combination therapy with metformin",
        "dosage": "• Starting: 5mg once daily (before breakfast)\n• Maintenance: 5-20mg daily\n• Extended release: 5-10mg once daily\n• Maximum: 40mg/day",
        "side_effects": "• Hypoglycemia (low blood sugar)\n• Nausea\n• Diarrhea\n• Dizziness\n• Weight gain\n• Skin rash",
        "warnings": "⚠️ Risk of severe hypoglycemia\n⚠️ May cause weight gain\n⚠️ Avoid with sulfa allergies\n⚠️ Can cause SIADH (low sodium)",
        "pregnancy_safety": "Category C - Use only if clearly needed. May cause prolonged hypoglycemia in newborns.",
        "food_restrictions": "• Take 30 minutes before meals\n• Consistent meal timing important\n• Avoid alcohol (may cause hypoglycemia)",
        "alternatives": "• Glimepiride\n• Glyburide\n• Metformin\n• Sitagliptin",
        "additional_info": "Sulfonylurea. Available as Glucotrol. Increases insulin secretion from pancreas."
    },
    "sitagliptin": {
        "name": "Sitagliptin",
        "type": "Prescription",
        "uses": "• Type 2 diabetes mellitus\n• Adjunct to diet and exercise\n• Combination with metformin or other agents",
        "dosage": "• 100mg once daily\n• Kidney disease: 25-50mg once daily\n• Take same time each day",
        "side_effects": "• Upper respiratory infection\n• Headache\n• Stomach upset\n• Joint pain\n• Pancreatitis (rare)\n• Allergic reactions",
        "warnings": "⚠️ Risk of pancreatitis\n⚠️ May cause severe joint pain\n⚠️ Can cause bullous pemphigoid (rare)\n⚠️ Monitor kidney function",
        "pregnancy_safety": "Category B - Use only if clearly needed. Consult doctor before use.",
        "food_restrictions": "• Can be taken with or without food\n• No specific restrictions",
        "alternatives": "• Linagliptin\n• Saxagliptin\n• Metformin\n• Empagliflozin",
        "additional_info": "DPP-4 inhibitor. Available as Januvia. Weight neutral. Once daily dosing."
    },
    "empagliflozin": {
        "name": "Empagliflozin",
        "type": "Prescription",
        "uses": "• Type 2 diabetes mellitus\n• Heart failure\n• Chronic kidney disease\n• Cardiovascular risk reduction\n• Weight management",
        "dosage": "• Diabetes: 10-25mg once daily\n• Heart failure: 10mg once daily\n• Maximum: 25mg/day\n• Take in morning",
        "side_effects": "• Urinary tract infections\n• Genital yeast infections\n• Increased urination\n• Thirst\n• Dehydration\n• Ketoacidosis (rare)",
        "warnings": "⚠️ Risk of ketoacidosis (even with normal blood sugar)\n⚠️ May cause dehydration and low blood pressure\n⚠️ Risk of Fournier's gangrene (rare)\n⚠️ Lower limb amputation risk\n⚠️ Not for type 1 diabetes",
        "pregnancy_safety": "Category C - Avoid during second and third trimesters. Not recommended during breastfeeding.",
        "food_restrictions": "• Take in morning (to avoid nighttime urination)\n• Stay well hydrated\n• No specific food restrictions",
        "alternatives": "• Dapagliflozin (Farxiga)\n• Canagliflozin (Invokana)\n• Metformin\n• GLP-1 agonists",
        "additional_info": "SGLT2 inhibitor. Available as Jardiance. Proven cardiovascular and kidney benefits."
    },
    "insulin glargine": {
        "name": "Insulin Glargine",
        "type": "Prescription",
        "uses": "• Type 1 diabetes mellitus\n• Type 2 diabetes mellitus\n• Gestational diabetes\n• Long-acting basal insulin replacement",
        "dosage": "• Type 1: 0.2-0.4 units/kg once daily\n• Type 2: 0.1-0.2 units/kg once daily\n• Adjust based on blood glucose\n• Inject at same time daily",
        "side_effects": "• Hypoglycemia (low blood sugar)\n• Injection site reactions\n• Weight gain\n• Lipodystrophy\n• Allergic reactions (rare)",
        "warnings": "⚠️ Risk of severe hypoglycemia\n⚠️ Do not mix with other insulins\n⚠️ Not for IV use\n⚠️ May cause hypokalemia\n⚠️ Rotate injection sites",
        "pregnancy_safety": "Category B - Generally considered safe during pregnancy. Standard treatment for gestational diabetes.",
        "food_restrictions": "• No specific food restrictions\n• Maintain consistent carbohydrate intake\n• Avoid alcohol (increases hypoglycemia risk)",
        "alternatives": "• Insulin detemir (Levemir)\n• Insulin degludec (Tresiba)\n• NPH insulin\n• Insulin pumps",
        "additional_info": "Long-acting basal insulin. Available as Lantus, Basaglar, Toujeo. Duration 24 hours."
    },
    
    # Acid Reducers (4 medicines)
    "omeprazole": {
        "name": "Omeprazole",
        "type": "OTC/Prescription",
        "uses": "• GERD\n• Heartburn\n• Acid reflux\n• Stomach ulcers\n• Zollinger-Ellison syndrome\n• H. pylori treatment",
        "dosage": "• OTC: 20mg daily for 14 days\n• Prescription: 20-40mg daily\n• Maintenance: 10-20mg daily\n• Maximum: 120mg/day",
        "side_effects": "• Headache\n• Nausea\n• Diarrhea\n• Constipation\n• Abdominal pain\n• Vitamin B12 deficiency (long-term)",
        "warnings": "⚠️ Long-term use may increase fracture risk\n⚠️ May mask stomach cancer symptoms\n⚠️ Risk of C. diff infection\n⚠️ May interact with clopidogrel",
        "pregnancy_safety": "Category C - Use only if clearly needed. Consult doctor before use.",
        "food_restrictions": "• Take 30-60 minutes before a meal (usually breakfast)\n• Swallow capsule whole",
        "alternatives": "• Esomeprazole (Nexium)\n• Pantoprazole (Protonix)\n• Lansoprazole (Prevacid)\n• Famotidine (Pepcid)",
        "additional_info": "Proton pump inhibitor (PPI). Available as Prilosec (OTC) and generic."
    },
    "pantoprazole": {
        "name": "Pantoprazole",
        "type": "Prescription",
        "uses": "• GERD\n• Erosive esophagitis\n• Stomach ulcers\n• Zollinger-Ellison syndrome\n• H. pylori treatment",
        "dosage": "• GERD: 40mg once daily\n• Maintenance: 20-40mg daily\n• IV: 40mg once daily\n• Maximum: 240mg/day",
        "side_effects": "• Headache\n• Diarrhea\n• Nausea\n• Dizziness\n• Joint pain\n• Vitamin B12 deficiency (long-term)",
        "warnings": "⚠️ Long-term use: fracture risk, B12 deficiency\n⚠️ May increase risk of C. diff\n⚠️ Can cause acute interstitial nephritis\n⚠️ May mask gastric cancer symptoms",
        "pregnancy_safety": "Category B - Generally considered safe. Consult doctor before use.",
        "food_restrictions": "• Take before meals\n• Swallow whole, do not crush or chew\n• Can be taken with antacids",
        "alternatives": "• Omeprazole (Prilosec)\n• Esomeprazole (Nexium)\n• Lansoprazole (Prevacid)\n• Famotidine (Pepcid)",
        "additional_info": "PPI with fewer drug interactions. Available as Protonix. IV form available."
    },
    "famotidine": {
        "name": "Famotidine",
        "type": "OTC/Prescription",
        "uses": "• GERD\n• Heartburn\n• Stomach ulcers\n• Duodenal ulcers\n• Zollinger-Ellison syndrome\n• Prevention of ulcers",
        "dosage": "• OTC: 10-20mg every 12 hours\n• Prescription: 20-40mg daily\n• Ulcer treatment: 40mg once daily\n• Maximum: 160mg/day",
        "side_effects": "• Headache\n• Dizziness\n• Constipation\n• Diarrhea\n• Fatigue\n• Depression (rare)",
        "warnings": "⚠️ May mask gastric cancer symptoms\n⚠️ Can cause confusion in elderly\n⚠️ Avoid in severe kidney disease\n⚠️ May cause thrombocytopenia (rare)",
        "pregnancy_safety": "Category B - Generally considered safe. Commonly used during pregnancy.",
        "food_restrictions": "• Can be taken with or without food\n• No specific restrictions",
        "alternatives": "• Omeprazole (Prilosec)\n• Ranitidine (Zantac)\n• Cimetidine (Tagamet)\n• Calcium carbonate (Tums)",
        "additional_info": "H2 blocker. Available as Pepcid. Less potent than PPIs but faster onset."
    },
    "ranitidine": {
        "name": "Ranitidine",
        "type": "OTC (limited availability)",
        "uses": "• GERD\n• Heartburn\n• Stomach ulcers\n• Duodenal ulcers\n• Zollinger-Ellison syndrome",
        "dosage": "• OTC: 75-150mg once or twice daily\n• Prescription: 150mg twice daily or 300mg nightly\n• Maximum: 600mg/day",
        "side_effects": "• Headache\n• Constipation\n• Diarrhea\n• Nausea\n• Dizziness\n• Rare: liver damage",
        "warnings": "⚠️ Limited availability due to NDMA contamination recalls\n⚠️ May contain low levels of carcinogen\n⚠️ Many products discontinued\n⚠️ Consider alternative medications",
        "pregnancy_safety": "Category B - Generally considered safe. Alternative H2 blockers available.",
        "food_restrictions": "• Can be taken with or without food\n• No specific restrictions",
        "alternatives": "• Famotidine (Pepcid)\n• Omeprazole (Prilosec)\n• Cimetidine (Tagamet)\n• Nizatidine (Axid)",
        "additional_info": "H2 blocker. Many formulations recalled due to NDMA contamination. Consider safer alternatives."
    },
    
    # Mental Health (5 medicines)
    "sertraline": {
        "name": "Sertraline",
        "type": "Prescription",
        "uses": "• Depression (major depressive disorder)\n• Anxiety disorders\n• Panic disorder\n• OCD\n• PTSD\n• Social anxiety disorder\n• PMDD",
        "dosage": "• Depression/OCD: 50-200mg once daily\n• Anxiety/PTSD: 25-200mg once daily\n• PMDD: 50-150mg daily\n• Starting: 25-50mg",
        "side_effects": "• Nausea\n• Diarrhea\n• Insomnia\n• Drowsiness\n• Dry mouth\n• Sexual dysfunction\n• Weight changes",
        "warnings": "⚠️ Increased risk of suicidal thoughts (young adults)\n⚠️ Serotonin syndrome risk\n⚠️ May cause bleeding risk\n⚠️ Withdrawal symptoms if stopped abruptly",
        "pregnancy_safety": "Category C - Use only if benefits outweigh risks. Third trimester use may cause neonatal effects.",
        "food_restrictions": "• Can be taken with or without food\n• Take at consistent time each day\n• Avoid alcohol",
        "alternatives": "• Fluoxetine (Prozac)\n• Paroxetine (Paxil)\n• Citalopram (Celexa)\n• Escitalopram (Lexapro)",
        "additional_info": "SSRI antidepressant. Available as Zoloft. Takes 2-4 weeks for full effect."
    },
    "fluoxetine": {
        "name": "Fluoxetine",
        "type": "Prescription",
        "uses": "• Depression\n• OCD\n• Bulimia nervosa\n• Panic disorder\n• PMDD\n• Bipolar depression (with olanzapine)",
        "dosage": "• Depression: 20-80mg once daily\n• OCD: 20-60mg once daily\n• Bulimia: 60mg once daily\n• PMDD: 20mg daily or 90mg weekly",
        "side_effects": "• Nausea\n• Insomnia\n• Drowsiness\n• Anxiety\n• Sexual dysfunction\n• Weight changes\n• Dry mouth",
        "warnings": "⚠️ Suicidal ideation risk (young adults)\n⚠️ Serotonin syndrome risk\n⚠️ May cause bleeding\n⚠️ Withdrawal less severe (long half-life)",
        "pregnancy_safety": "Category C - Use with caution. Third trimester use may cause neonatal complications.",
        "food_restrictions": "• Can be taken with or without food\n• Take in morning (may cause insomnia)\n• Avoid alcohol",
        "alternatives": "• Sertraline (Zoloft)\n• Paroxetine (Paxil)\n• Citalopram (Celexa)\n• Escitalopram (Lexapro)",
        "additional_info": "First SSRI developed. Available as Prozac. Longest half-life (1-3 days)."
    },
    "alprazolam": {
        "name": "Alprazolam",
        "type": "Controlled Substance (Schedule IV)",
        "uses": "• Anxiety disorders\n• Panic disorder\n• Anxiety associated with depression\n• Short-term anxiety relief",
        "dosage": "• Anxiety: 0.25-0.5mg 2-3 times daily\n• Panic disorder: 0.5-1mg daily (IR) or 1-10mg (XR)\n• Maximum: 4mg/day (IR), 10mg/day (XR)",
        "side_effects": "• Drowsiness\n• Dizziness\n• Fatigue\n• Dry mouth\n• Memory problems\n• Slurred speech\n• Dependence risk",
        "warnings": "⚠️ HIGH RISK OF DEPENDENCE AND ADDICTION\n⚠️ Severe withdrawal (seizures, death)\n⚠️ Do not stop abruptly\n⚠️ Avoid with opioids (respiratory depression)",
        "pregnancy_safety": "Category D - AVOID during pregnancy. Causes neonatal withdrawal.",
        "food_restrictions": "• Avoid grapefruit juice\n• Avoid alcohol completely\n• Take with food if stomach upset",
        "alternatives": "• Lorazepam (Ativan)\n• Clonazepam (Klonopin)\n• Diazepam (Valium)\n• Buspirone (Buspar)",
        "additional_info": "Benzodiazepine. Available as Xanax. High abuse potential. Short-acting."
    },
    "escitalopram": {
        "name": "Escitalopram",
        "type": "Prescription",
        "uses": "• Major depressive disorder\n• Generalized anxiety disorder\n• Social anxiety disorder\n• Panic disorder\n• OCD\n• PTSD",
        "dosage": "• Depression/Anxiety: 10-20mg once daily\n• Starting: 10mg\n• Elderly: 5-10mg daily\n• Maximum: 20mg/day",
        "side_effects": "• Nausea\n• Insomnia\n• Fatigue\n• Drowsiness\n• Dry mouth\n• Sexual dysfunction\n• Weight changes",
        "warnings": "⚠️ Suicidal ideation risk (young adults)\n⚠️ Serotonin syndrome risk\n⚠️ May cause QT prolongation\n⚠️ Withdrawal symptoms if stopped abruptly",
        "pregnancy_safety": "Category C - Use only if benefits outweigh risks. Third trimester use may cause neonatal effects.",
        "food_restrictions": "• Can be taken with or without food\n• Take at consistent time each day\n• Avoid alcohol",
        "alternatives": "• Sertraline (Zoloft)\n• Fluoxetine (Prozac)\n• Paroxetine (Paxil)\n• Citalopram (Celexa)",
        "additional_info": "SSRI antidepressant. Available as Lexapro. Better tolerated than other SSRIs."
    },
    "diazepam": {
        "name": "Diazepam",
        "type": "Controlled Substance (Schedule IV)",
        "uses": "• Anxiety disorders\n• Alcohol withdrawal\n• Muscle spasms\n• Seizure disorders\n• Pre-procedure sedation\n• Panic disorder",
        "dosage": "• Anxiety: 2-10mg 2-4 times daily\n• Alcohol withdrawal: 5-10mg every 4-6 hours\n• Muscle spasm: 2-10mg 3-4 times daily\n• Maximum: 40mg/day",
        "side_effects": "• Drowsiness\n• Dizziness\n• Fatigue\n• Muscle weakness\n• Ataxia\n• Dependence\n• Memory problems",
        "warnings": "⚠️ High risk of dependence\n⚠️ Severe withdrawal (seizures)\n⚠️ Do not stop abruptly\n⚠️ Avoid with opioids (respiratory depression)\n⚠️ May cause falls in elderly",
        "pregnancy_safety": "Category D - AVOID during pregnancy. Causes neonatal withdrawal and floppy infant syndrome.",
        "food_restrictions": "• Avoid grapefruit juice\n• Avoid alcohol completely\n• Take with food if stomach upset",
        "alternatives": "• Lorazepam (Ativan)\n• Clonazepam (Klonopin)\n• Alprazolam (Xanax)\n• Buspirone (Buspar)",
        "additional_info": "Benzodiazepine. Available as Valium. Long-acting. Also used for status epilepticus."
    },
    
    # Respiratory (3 medicines)
    "albuterol": {
        "name": "Albuterol",
        "type": "Prescription",
        "uses": "• Asthma (acute attacks)\n• COPD\n• Bronchospasm\n• Exercise-induced bronchospasm",
        "dosage": "• Inhaler: 1-2 puffs every 4-6 hours as needed\n• Nebulizer: 2.5mg 3-4 times daily\n• Children: 0.63-1.25mg via nebulizer\n• Maximum: 12 puffs/day",
        "side_effects": "• Tremor\n• Nervousness\n• Headache\n• Palpitations\n• Fast heart rate\n• Muscle cramps",
        "warnings": "⚠️ Overuse may worsen asthma\n⚠️ May cause paradoxical bronchospasm\n⚠️ Can cause hypokalemia\n⚠️ Use caution in heart disease",
        "pregnancy_safety": "Category C - Generally considered safe. Use lowest effective dose.",
        "food_restrictions": "• No food restrictions\n• Avoid caffeine (adds to side effects)",
        "alternatives": "• Levalbuterol (Xopenex)\n• Formoterol (Foradil)\n• Salmeterol (Serevent)\n• Ipratropium (Atrovent)",
        "additional_info": "Short-acting beta agonist (SABA). Available as ProAir, Ventolin. Rescue inhaler."
    },
    "fluticasone": {
        "name": "Fluticasone",
        "type": "Prescription",
        "uses": "• Asthma (maintenance)\n• Allergic rhinitis\n• COPD\n• Nasal polyps",
        "dosage": "• Inhaler: 88-440mcg twice daily\n• Nasal spray: 1-2 sprays each nostril daily\n• Discus: 100-500mcg twice daily",
        "side_effects": "• Oral thrush (with inhaler)\n• Hoarseness\n• Sore throat\n• Nosebleeds (nasal)\n• Cough\n• Headache",
        "warnings": "⚠️ Rinse mouth after use to prevent thrush\n⚠️ May cause growth suppression in children\n⚠️ Can cause adrenal crisis if stopped abruptly\n⚠️ Not for acute attacks",
        "pregnancy_safety": "Category C - Generally considered safe. Use lowest effective dose.",
        "food_restrictions": "• No food restrictions\n• Rinse mouth after use",
        "alternatives": "• Budesonide (Pulmicort)\n• Mometasone (Asmanex)\n• Beclomethasone (Qvar)\n• Ciclesonide (Alvesco)",
        "additional_info": "Corticosteroid. Available as Flovent (inhaler) and Flonase (nasal spray)."
    },
    "montelukast": {
        "name": "Montelukast",
        "type": "Prescription",
        "uses": "• Asthma prophylaxis\n• Allergic rhinitis\n• Exercise-induced bronchospasm\n• Seasonal allergies",
        "dosage": "• Adults: 10mg once daily (evening)\n• Children 6-14: 5mg once daily\n• Children 2-5: 4mg once daily\n• Take in evening for asthma",
        "side_effects": "• Headache\n• Stomach pain\n• Thirst\n• Fatigue\n• Neuropsychological events (rare)\n• Upper respiratory infection",
        "warnings": "⚠️ FDA warning for neuropsychiatric events (agitation, depression, suicidal thoughts)\n⚠️ Not for acute asthma attacks\n⚠️ May cause eosinophilic granulomatosis (rare)\n⚠️ Monitor for behavior changes",
        "pregnancy_safety": "Category B - Use only if clearly needed. Consult doctor before use.",
        "food_restrictions": "• Take on empty stomach (1 hour before or 2 hours after food)\n• Take at same time each day",
        "alternatives": "• Zafirlukast (Accolate)\n• Zileuton (Zyflo)\n• Inhaled corticosteroids\n• Antihistamines",
        "additional_info": "Leukotriene receptor antagonist. Available as Singulair. Oral medication for asthma."
    },
    
    # Additional Common Medicines (remaining to reach 50+)
    "levothyroxine": {
        "name": "Levothyroxine",
        "type": "Prescription",
        "uses": "• Hypothyroidism\n• Thyroid hormone replacement\n• Thyroid cancer suppression\n• Myxedema coma",
        "dosage": "• Starting: 1.6mcg/kg/day\n• Maintenance: 50-200mcg once daily\n• Elderly: 12.5-25mcg starting\n• Take at same time daily",
        "side_effects": "• Palpitations\n• Insomnia\n• Nervousness\n• Tremor\n• Weight loss\n• Increased appetite",
        "warnings": "⚠️ Do not stop abruptly\n⚠️ Regular thyroid function monitoring\n⚠️ May increase anticoagulant effect\n⚠️ Can cause cardiac arrhythmias",
        "pregnancy_safety": "Category A - Safe and necessary during pregnancy. Continue treatment.",
        "food_restrictions": "• Take on empty stomach (30-60 minutes before breakfast)\n• Avoid calcium, iron supplements (separate by 4 hours)\n• Avoid soy products, walnuts",
        "alternatives": "• Liothyronine (Cytomel)\n• Natural thyroid extract (Armour Thyroid)",
        "additional_info": "Synthetic T4 hormone. Available as Synthroid, Levoxyl. Lifelong treatment."
    },
    "gabapentin": {
        "name": "Gabapentin",
        "type": "Prescription",
        "uses": "• Neuropathic pain\n• Postherpetic neuralgia\n• Seizures (partial)\n• Restless legs syndrome\n• Hot flashes",
        "dosage": "• Neuropathic pain: 300-600mg 3 times daily\n• Seizures: 900-1800mg divided\n• Restless legs: 300-600mg once daily (evening)\n• Maximum: 3600mg/day",
        "side_effects": "• Drowsiness\n• Dizziness\n• Fatigue\n• Ataxia (unsteadiness)\n• Swelling of hands/feet\n• Weight gain",
        "warnings": "⚠️ May cause respiratory depression (especially with opioids)\n⚠️ Suicidal ideation risk\n⚠️ Can cause withdrawal seizures if stopped abruptly\n⚠️ Risk of misuse",
        "pregnancy_safety": "Category C - Use only if benefits outweigh risks. May cause developmental effects.",
        "food_restrictions": "• Can be taken with or without food\n• Avoid alcohol\n• Stay hydrated",
        "alternatives": "• Pregabalin (Lyrica)\n• Carbamazepine (Tegretol)\n• Amitriptyline\n• Duloxetine (Cymbalta)",
        "additional_info": "GABA analog. Available as Neurontin. Also used for anxiety and alcohol withdrawal."
    },
    "tramadol": {
        "name": "Tramadol",
        "type": "Controlled Substance (Schedule IV)",
        "uses": "• Moderate to severe pain\n• Chronic pain\n• Post-surgical pain\n• Neuropathic pain\n• Osteoarthritis pain",
        "dosage": "• Immediate release: 50-100mg every 4-6 hours\n• Extended release: 100-300mg once daily\n• Maximum: 400mg/day (IR), 300mg/day (ER)",
        "side_effects": "• Nausea\n• Dizziness\n• Drowsiness\n• Constipation\n• Headache\n• Seizures (high risk)\n• Serotonin syndrome",
        "warnings": "⚠️ Seizure risk (lowers seizure threshold)\n⚠️ Serotonin syndrome risk\n⚠️ Respiratory depression\n⚠️ Dependence and withdrawal",
        "pregnancy_safety": "Category C - Avoid during pregnancy. May cause neonatal withdrawal syndrome.",
        "food_restrictions": "• Can be taken with or without food\n• Avoid alcohol completely\n• Stay hydrated",
        "alternatives": "• Hydrocodone\n• Oxycodone\n• Codeine\n• Tapentadol (Nucynta)",
        "additional_info": "Synthetic opioid with SNRI effects. Available as Ultram. Lower abuse potential."
    },
    "tamsulosin": {
        "name": "Tamsulosin",
        "type": "Prescription",
        "uses": "• Benign prostatic hyperplasia (BPH)\n• Kidney stones (expulsion therapy)\n• Difficulty urinating",
        "dosage": "• BPH: 0.4mg once daily\n• Can increase to 0.8mg once daily\n• Take 30 minutes after same meal each day",
        "side_effects": "• Dizziness\n• Runny nose\n• Abnormal ejaculation (retrograde)\n• Headache\n• Weakness\n• Low blood pressure",
        "warnings": "⚠️ May cause floppy iris syndrome (cataract surgery)\n⚠️ Can cause low blood pressure (especially first dose)\n⚠️ Not for women or children",
        "pregnancy_safety": "Not for use in women. For men only.",
        "food_restrictions": "• Take with a meal (same meal each day)\n• Swallow capsule whole\n• Avoid grapefruit juice",
        "alternatives": "• Doxazosin (Cardura)\n• Finasteride (Proscar)\n• Terazosin (Hytrin)\n• Alfuzosin (Uroxatral)",
        "additional_info": "Alpha-1 blocker. Available as Flomax. Selective for prostate."
    },
    "finasteride": {
        "name": "Finasteride",
        "type": "Prescription",
        "uses": "• Benign prostatic hyperplasia (BPH)\n• Male pattern baldness (androgenetic alopecia)",
        "dosage": "• BPH: 5mg once daily\n• Hair loss: 1mg once daily\n• Take at same time each day",
        "side_effects": "• Decreased libido\n• Erectile dysfunction\n• Decreased ejaculate volume\n• Breast tenderness\n• Depression",
        "warnings": "⚠️ Women should NOT handle crushed tablets\n⚠️ May affect PSA test results\n⚠️ Can cause persistent sexual side effects\n⚠️ May increase risk of high-grade prostate cancer",
        "pregnancy_safety": "Category X - ABSOLUTELY CONTRAINDICATED in women who are or may become pregnant.",
        "food_restrictions": "• Can be taken with or without food\n• No specific restrictions",
        "alternatives": "• Dutasteride (Avodart)\n• Minoxidil (Rogaine - topical)\n• Saw palmetto (herbal)",
        "additional_info": "5-alpha-reductase inhibitor. Available as Proscar (5mg) and Propecia (1mg)."
    },
    "melatonin": {
        "name": "Melatonin",
        "type": "OTC Supplement",
        "uses": "• Insomnia\n• Jet lag\n• Shift work sleep disorder\n• Delayed sleep phase syndrome",
        "dosage": "• Insomnia: 3-10mg 1-2 hours before bed\n• Jet lag: 0.5-5mg at bedtime (destination time)\n• Children: 1-3mg (under doctor supervision)",
        "side_effects": "• Drowsiness (morning)\n• Headache\n• Dizziness\n• Nausea\n• Vivid dreams\n• Daytime sleepiness",
        "warnings": "⚠️ May interact with blood thinners\n⚠️ Can affect blood sugar (caution in diabetes)\n⚠️ May lower blood pressure\n⚠️ Avoid driving until you know effects",
        "pregnancy_safety": "Category C - Limited data. Consult doctor before use during pregnancy.",
        "food_restrictions": "• Avoid caffeine before bedtime\n• No other restrictions",
        "alternatives": "• Valerian root\n• Diphenhydramine (Benadryl)\n• Doxylamine (Unisom)\n• Zolpidem (Ambien)",
        "additional_info": "Natural hormone that regulates sleep-wake cycle. Available OTC as supplement."
    },
    "cetirizine": {
        "name": "Cetirizine",
        "type": "OTC",
        "uses": "• Allergic rhinitis (hay fever)\n• Hives (urticaria)\n• Itching\n• Runny nose\n• Watery eyes",
        "dosage": "• Adults: 5-10mg once daily\n• Children 6-12: 5-10mg daily\n• Children 2-5: 2.5-5mg daily",
        "side_effects": "• Drowsiness (less than older antihistamines)\n• Dry mouth\n• Fatigue\n• Sore throat\n• Dizziness",
        "warnings": "⚠️ May cause drowsiness (use caution driving)\n⚠️ Avoid with alcohol\n⚠️ Use caution in kidney disease (reduce dose)",
        "pregnancy_safety": "Category B - Generally considered safe. Consult doctor before use.",
        "food_restrictions": "• Can be taken with or without food\n• Avoid alcohol",
        "alternatives": "• Loratadine (Claritin)\n• Fexofenadine (Allegra)\n• Diphenhydramine (Benadryl)",
        "additional_info": "Second-generation antihistamine. Available as Zyrtec. Less sedating."
    },
    "loratadine": {
        "name": "Loratadine",
        "type": "OTC",
        "uses": "• Allergic rhinitis\n• Hives (urticaria)\n• Itching\n• Hay fever symptoms",
        "dosage": "• Adults: 10mg once daily\n• Children 6-12: 10mg daily\n• Children 2-5: 5mg daily",
        "side_effects": "• Headache\n• Dry mouth\n• Fatigue\n• Sore throat\n• Nausea\n• Very low drowsiness",
        "warnings": "⚠️ Non-drowsy for most people\n⚠️ Use caution in kidney or liver disease\n⚠️ May cause allergic reactions (rare)",
        "pregnancy_safety": "Category B - Generally considered safe. Commonly used during pregnancy.",
        "food_restrictions": "• Can be taken with or without food\n• No grapefruit interaction",
        "alternatives": "• Cetirizine (Zyrtec)\n• Fexofenadine (Allegra)\n• Diphenhydramine (Benadryl)",
        "additional_info": "Non-drowsy antihistamine. Available as Claritin. Once daily dosing."
    },
    "simvastatin": {
        "name": "Simvastatin",
        "type": "Prescription",
        "uses": "• High cholesterol\n• Triglyceride reduction\n• Heart attack prevention\n• Stroke prevention",
        "dosage": "• Starting: 10-20mg once daily (evening)\n• Maintenance: 5-40mg once daily\n• Maximum: 80mg/day (restricted)",
        "side_effects": "• Muscle pain\n• Headache\n• Nausea\n• Constipation\n• Increased liver enzymes",
        "warnings": "⚠️ Severe grapefruit interaction\n⚠️ Risk of muscle damage (rhabdomyolysis)\n⚠️ Avoid with certain antibiotics\n⚠️ Monitor liver function",
        "pregnancy_safety": "Category X - DO NOT use during pregnancy.",
        "food_restrictions": "• Take in evening (better absorption)\n• AVOID GRAPEFRUIT completely\n• Can be taken with or without food",
        "alternatives": "• Atorvastatin (Lipitor)\n• Rosuvastatin (Crestor)\n• Pravastatin (Pravachol)",
        "additional_info": "Statin medication. Available as Zocor. Take in evening for best effect."
    },
    "pregabalin": {
        "name": "Pregabalin",
        "type": "Controlled Substance (Schedule V)",
        "uses": "• Neuropathic pain (diabetic neuropathy)\n• Postherpetic neuralgia\n• Fibromyalgia\n• Partial seizures\n• Generalized anxiety disorder",
        "dosage": "• Neuropathic pain: 150-600mg daily (divided)\n• Fibromyalgia: 300-450mg daily\n• Seizures: 150-600mg daily\n• Anxiety: 150-600mg daily",
        "side_effects": "• Dizziness\n• Drowsiness\n• Dry mouth\n• Swelling (edema)\n• Blurred vision\n• Weight gain",
        "warnings": "⚠️ Dependence and withdrawal risk\n⚠️ May cause euphoria (abuse potential)\n⚠️ Can cause angioedema\n⚠️ May impair driving",
        "pregnancy_safety": "Category C - Use only if benefits outweigh risks. May cause developmental effects.",
        "food_restrictions": "• Can be taken with or without food\n• Avoid alcohol\n• Stay hydrated",
        "alternatives": "• Gabapentin (Neurontin)\n• Duloxetine (Cymbalta)\n• Amitriptyline",
        "additional_info": "GABA analog. Available as Lyrica. Schedule V controlled substance."
    }
}

print(f"✅ Loaded {len(MEDICINE_DB)} medicines into database")

@app.get("/medicine-info")
def get_medicine_info(name: str):
    """Get comprehensive information about any medicine - 50+ medicines available"""
    
    # Normalize input
    medicine_key = name.lower().strip()
    
    # Try exact match
    if medicine_key in MEDICINE_DB:
        return MEDICINE_DB[medicine_key]
    
    # Try partial match
    for key, value in MEDICINE_DB.items():
        if medicine_key in key or key in medicine_key:
            return value
    
    # Brand name mapping
    brand_mapping = {
        "tylenol": "paracetamol", "advil": "ibuprofen", "motrin": "ibuprofen",
        "aleve": "naproxen", "voltaren": "diclofenac", "celebrex": "celecoxib",
        "toradol": "ketorolac", "zithromax": "azithromycin", "keflex": "cephalexin",
        "cipro": "ciprofloxacin", "vibramycin": "doxycycline", "cleocin": "clindamycin",
        "flagyl": "metronidazole", "levaquin": "levofloxacin", "norvasc": "amlodipine",
        "lipitor": "atorvastatin", "crestor": "rosuvastatin", "cozaar": "losartan",
        "plavix": "clopidogrel", "lopressor": "metoprolol", "glucophage": "metformin",
        "glucotrol": "glipizide", "januvia": "sitagliptin", "jardiance": "empagliflozin",
        "lantus": "insulin glargine", "prilosec": "omeprazole", "protonix": "pantoprazole",
        "pepcid": "famotidine", "zantac": "ranitidine", "zoloft": "sertraline",
        "prozac": "fluoxetine", "xanax": "alprazolam", "lexapro": "escitalopram",
        "valium": "diazepam", "ventolin": "albuterol", "flovent": "fluticasone",
        "flonase": "fluticasone", "singulair": "montelukast", "synthroid": "levothyroxine",
        "neurontin": "gabapentin", "ultram": "tramadol", "flomax": "tamsulosin",
        "proscar": "finasteride", "propecia": "finasteride", "zyrtec": "cetirizine",
        "claritin": "loratadine", "zocor": "simvastatin", "lyrica": "pregabalin"
    }
    
    if medicine_key in brand_mapping:
        return MEDICINE_DB[brand_mapping[medicine_key]]
    
    # AI fallback for unknown medicines
    try:
        prompt = f"""Provide detailed medical information for the medicine: {name}
        
If you don't know about this medicine, respond with exactly: MEDICINE_NOT_FOUND"""

        ai_response = query_groq_ai(prompt)
        
        if "MEDICINE_NOT_FOUND" in ai_response:
            return {"error": f"Medicine '{name}' not found in database"}
        
        return {"name": name, "type": "Information from AI", "uses": ai_response[:500], 
                "dosage": "Please consult doctor", "side_effects": "Consult healthcare provider",
                "warnings": "Medical advice recommended", "pregnancy_safety": "Consult doctor",
                "food_restrictions": "No specific information", "alternatives": "Consult pharmacist",
                "additional_info": "AI-generated information. Please verify with healthcare provider"}
        
    except Exception as e:
        return {"error": f"Could not retrieve information for '{name}'"}

@app.get("/medicine-count")
def get_medicine_count():
    """Return the number of medicines in the database"""
    return {"count": len(MEDICINE_DB)}

# ================== GENERIC MEDICINE DATABASE ==================

# ================== COMPLETE GENERIC MEDICINE DATABASE (50+ MEDICINES) ==================

GENERIC_MEDICINES_DB = {
    # ==================== PAIN RELIEVERS & FEVER (10 Medicines) ====================
    "crocin": {
        "brand_name": "Crocin",
        "generic_name": "Paracetamol",
        "composition": "Paracetamol 500mg",
        "composition_detail": "Each tablet contains Paracetamol 500mg. Used for fever and mild to moderate pain relief.",
        "brand_price": 35.00,
        "generic_price": 8.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, Micro Labs, Cipla, Sun Pharma, Alkem, Mankind",
        "availability": "All Jan Aushadhi Kendras, generic pharmacies, online stores (Netmeds, PharmEasy, 1mg)",
        "why_generic": "Same active ingredient (Paracetamol 500mg) at 77% lower cost. No brand marketing expenses.",
        "quality_assurance": "CDSCO approved. Meets Indian Pharmacopoeia standards. Same bioavailability."
    },
    "dolo": {
        "brand_name": "Dolo 650",
        "generic_name": "Paracetamol",
        "composition": "Paracetamol 650mg",
        "composition_detail": "Each tablet contains Paracetamol 650mg. Used for fever and moderate pain.",
        "brand_price": 45.00,
        "generic_price": 10.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, Micro Labs, Cipla, Sun Pharma, Alkem",
        "availability": "Jan Aushadhi Kendras, generic medical stores, online pharmacies",
        "why_generic": "Same Paracetamol 650mg at 78% lower cost. Identical therapeutic effect.",
        "quality_assurance": "CDSCO approved. Bioequivalent to branded version. GMP certified."
    },
    "calpol": {
        "brand_name": "Calpol",
        "generic_name": "Paracetamol",
        "composition": "Paracetamol 500mg",
        "composition_detail": "Each tablet contains Paracetamol 500mg. For fever and pain relief.",
        "brand_price": 38.00,
        "generic_price": 8.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, various generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies nationwide",
        "why_generic": "79% savings with same Paracetamol 500mg. No difference in effectiveness.",
        "quality_assurance": "Approved by DCGI. Manufactured in WHO-GMP certified facilities."
    },
    "paracip": {
        "brand_name": "Paracip",
        "generic_name": "Paracetamol",
        "composition": "Paracetamol 500mg",
        "composition_detail": "Each tablet contains Paracetamol 500mg for pain and fever.",
        "brand_price": 32.00,
        "generic_price": 8.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Available at generic medicine stores and online",
        "why_generic": "Save 75% by choosing generic Paracetamol. Same medicine, lower price.",
        "quality_assurance": "CDSCO approved. Meets all quality parameters."
    },
    "metacin": {
        "brand_name": "Metacin",
        "generic_name": "Paracetamol",
        "composition": "Paracetamol 500mg",
        "composition_detail": "Paracetamol 500mg tablets for fever and pain relief.",
        "brand_price": 30.00,
        "generic_price": 8.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Various generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "73% savings with generic Paracetamol. No compromise on quality.",
        "quality_assurance": "GMP certified. Bioequivalence established."
    },
    "brufen": {
        "brand_name": "Brufen",
        "generic_name": "Ibuprofen",
        "composition": "Ibuprofen 400mg",
        "composition_detail": "Each tablet contains Ibuprofen 400mg. Used for pain, inflammation, and fever.",
        "brand_price": 55.00,
        "generic_price": 15.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, Cipla, Sun Pharma, Alkem, Abbott",
        "availability": "Jan Aushadhi Kendras, generic pharmacies, online stores",
        "why_generic": "Save 73% with generic Ibuprofen. Same anti-inflammatory effect.",
        "quality_assurance": "CDSCO approved. Bioequivalent to brand. GMP manufactured."
    },
    "combiflam": {
        "brand_name": "Combiflam",
        "generic_name": "Ibuprofen + Paracetamol",
        "composition": "Ibuprofen 400mg + Paracetamol 325mg",
        "composition_detail": "Combination of Ibuprofen 400mg and Paracetamol 325mg for stronger pain relief.",
        "brand_price": 65.00,
        "generic_price": 18.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, various generic manufacturers, Sanofi",
        "availability": "Jan Aushadhi Kendras, generic medical stores",
        "why_generic": "72% savings with generic combination. Same dual action pain relief.",
        "quality_assurance": "DCGI approved. Fixed-dose combination approved. Quality assured."
    },
    "naprosyn": {
        "brand_name": "Naprosyn",
        "generic_name": "Naproxen",
        "composition": "Naproxen 250mg",
        "composition_detail": "Naproxen 250mg for arthritis, muscle pain, and inflammation.",
        "brand_price": 70.00,
        "generic_price": 20.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "71% savings with generic Naproxen. Same NSAID effectiveness.",
        "quality_assurance": "CDSCO approved. Bioequivalent. GMP certified."
    },
    "volini": {
        "brand_name": "Volini",
        "generic_name": "Diclofenac Gel",
        "composition": "Diclofenac Diethylamine 1.16%",
        "composition_detail": "Topical gel for localized pain relief in arthritis, sprains, and muscle pain.",
        "brand_price": 85.00,
        "generic_price": 25.00,
        "brand_detail": "per 30g tube",
        "generic_detail": "per 30g tube",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, all pharmacies",
        "why_generic": "71% savings with generic Diclofenac gel. Same topical pain relief.",
        "quality_assurance": "CDSCO approved. Same concentration and efficacy."
    },
    "voveran": {
        "brand_name": "Voveran",
        "generic_name": "Diclofenac",
        "composition": "Diclofenac Sodium 50mg",
        "composition_detail": "Diclofenac 50mg for pain, inflammation, and arthritis.",
        "brand_price": 48.00,
        "generic_price": 14.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "71% savings with generic Diclofenac. Same pain relief.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    },

    # ==================== ANTIBIOTICS (12 Medicines) ====================
    "augmentin": {
        "brand_name": "Augmentin",
        "generic_name": "Amoxicillin + Clavulanic Acid",
        "composition": "Amoxicillin 500mg + Clavulanic Acid 125mg",
        "composition_detail": "Combination antibiotic for bacterial infections. Amoxicillin 500mg with Clavulanic Acid 125mg.",
        "brand_price": 180.00,
        "generic_price": 45.00,
        "brand_detail": "per strip of 6 tablets",
        "generic_detail": "per strip of 6 tablets",
        "manufacturers": "Jan Aushadhi, Cipla, Alkem, Mankind, GSK",
        "availability": "Jan Aushadhi Kendras, generic pharmacies with prescription",
        "why_generic": "Save 75% with generic Co-amoxiclav. Same antibiotic effectiveness.",
        "quality_assurance": "CDSCO approved. Bioequivalence proven. WHO-GMP certified."
    },
    "azithral": {
        "brand_name": "Azithral",
        "generic_name": "Azithromycin",
        "composition": "Azithromycin 500mg",
        "composition_detail": "Azithromycin 500mg antibiotic for respiratory and bacterial infections.",
        "brand_price": 120.00,
        "generic_price": 35.00,
        "brand_detail": "per strip of 3 tablets",
        "generic_detail": "per strip of 3 tablets",
        "manufacturers": "Jan Aushadhi, various generic manufacturers, Alembic",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "71% savings with generic Azithromycin. Same Z-Pak effectiveness.",
        "quality_assurance": "Approved by DCGI. Bioequivalent. Manufactured in GMP facilities."
    },
    "sporidex": {
        "brand_name": "Sporidex",
        "generic_name": "Cephalexin",
        "composition": "Cephalexin 500mg",
        "composition_detail": "Cephalexin 500mg antibiotic for various bacterial infections.",
        "brand_price": 95.00,
        "generic_price": 28.00,
        "brand_detail": "per strip of 10 capsules",
        "generic_detail": "per strip of 10 capsules",
        "manufacturers": "Jan Aushadhi, generic manufacturers, Lupin",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "Save 71% with generic Cephalexin. Same cephalosporin antibiotic.",
        "quality_assurance": "CDSCO approved. Meets pharmacopoeia standards."
    },
    "ciprobid": {
        "brand_name": "Ciprobid",
        "generic_name": "Ciprofloxacin",
        "composition": "Ciprofloxacin 500mg",
        "composition_detail": "Ciprofloxacin 500mg antibiotic for urinary tract and bacterial infections.",
        "brand_price": 70.00,
        "generic_price": 20.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers, Cipla",
        "availability": "Jan Aushadhi Kendras, generic medical stores",
        "why_generic": "71% savings with generic Ciprofloxacin. Same fluoroquinolone antibiotic.",
        "quality_assurance": "DCGI approved. Bioequivalent. GMP certified."
    },
    "doxy": {
        "brand_name": "Doxy-1",
        "generic_name": "Doxycycline",
        "composition": "Doxycycline 100mg",
        "composition_detail": "Doxycycline 100mg for bacterial infections, acne, and malaria prevention.",
        "brand_price": 85.00,
        "generic_price": 25.00,
        "brand_detail": "per strip of 10 capsules",
        "generic_detail": "per strip of 10 capsules",
        "manufacturers": "Jan Aushadhi, generic manufacturers, Sun Pharma",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "71% savings with generic Doxycycline. Same tetracycline antibiotic.",
        "quality_assurance": "CDSCO approved. Bioequivalent. GMP certified."
    },
    "clindac": {
        "brand_name": "Clindac A",
        "generic_name": "Clindamycin",
        "composition": "Clindamycin 300mg",
        "composition_detail": "Clindamycin 300mg for skin, respiratory, and anaerobic infections.",
        "brand_price": 110.00,
        "generic_price": 32.00,
        "brand_detail": "per strip of 10 capsules",
        "generic_detail": "per strip of 10 capsules",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "71% savings with generic Clindamycin. Same lincosamide antibiotic.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    },
    "flagyl": {
        "brand_name": "Flagyl",
        "generic_name": "Metronidazole",
        "composition": "Metronidazole 400mg",
        "composition_detail": "Metronidazole 400mg for anaerobic bacterial and protozoal infections.",
        "brand_price": 45.00,
        "generic_price": 12.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers, Abbott",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "73% savings with generic Metronidazole. Same antibiotic effectiveness.",
        "quality_assurance": "DCGI approved. Bioequivalent. GMP certified."
    },
    "levoquin": {
        "brand_name": "Levoquin",
        "generic_name": "Levofloxacin",
        "composition": "Levofloxacin 500mg",
        "composition_detail": "Levofloxacin 500mg for respiratory and urinary tract infections.",
        "brand_price": 95.00,
        "generic_price": 28.00,
        "brand_detail": "per strip of 5 tablets",
        "generic_detail": "per strip of 5 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "71% savings with generic Levofloxacin. Same fluoroquinolone antibiotic.",
        "quality_assurance": "CDSCO approved. Bioequivalent. GMP certified."
    },
    "mox": {
        "brand_name": "Mox",
        "generic_name": "Amoxicillin",
        "composition": "Amoxicillin 500mg",
        "composition_detail": "Amoxicillin 500mg for various bacterial infections.",
        "brand_price": 60.00,
        "generic_price": 18.00,
        "brand_detail": "per strip of 10 capsules",
        "generic_detail": "per strip of 10 capsules",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "70% savings with generic Amoxicillin. Same penicillin antibiotic.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    },
    "cefakind": {
        "brand_name": "Cefakind",
        "generic_name": "Cefixime",
        "composition": "Cefixime 200mg",
        "composition_detail": "Cefixime 200mg for respiratory, urinary, and typhoid infections.",
        "brand_price": 130.00,
        "generic_price": 38.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "71% savings with generic Cefixime. Same cephalosporin antibiotic.",
        "quality_assurance": "CDSCO approved. Bioequivalent. GMP certified."
    },
    "claribid": {
        "brand_name": "Claribid",
        "generic_name": "Clarithromycin",
        "composition": "Clarithromycin 500mg",
        "composition_detail": "Clarithromycin 500mg for respiratory and H. pylori infections.",
        "brand_price": 140.00,
        "generic_price": 40.00,
        "brand_detail": "per strip of 6 tablets",
        "generic_detail": "per strip of 6 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "71% savings with generic Clarithromycin. Same macrolide antibiotic.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    },
    "nitrofur": {
        "brand_name": "Nitrofurantoin",
        "generic_name": "Nitrofurantoin",
        "composition": "Nitrofurantoin 100mg",
        "composition_detail": "Nitrofurantoin 100mg for urinary tract infections.",
        "brand_price": 55.00,
        "generic_price": 16.00,
        "brand_detail": "per strip of 10 capsules",
        "generic_detail": "per strip of 10 capsules",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "71% savings with generic Nitrofurantoin. Same UTI antibiotic.",
        "quality_assurance": "CDSCO approved. Bioequivalent. GMP certified."
    },

    # ==================== CARDIOVASCULAR (10 Medicines) ====================
    "lipitor": {
        "brand_name": "Lipitor",
        "generic_name": "Atorvastatin",
        "composition": "Atorvastatin 10mg",
        "composition_detail": "Atorvastatin 10mg for cholesterol management and heart attack prevention.",
        "brand_price": 80.00,
        "generic_price": 20.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers, Pfizer, Sun Pharma",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "75% savings with generic Atorvastatin. Same statin for cholesterol.",
        "quality_assurance": "DCGI approved. Bioequivalent. GMP certified."
    },
    "crestor": {
        "brand_name": "Crestor",
        "generic_name": "Rosuvastatin",
        "composition": "Rosuvastatin 10mg",
        "composition_detail": "Rosuvastatin 10mg for high cholesterol and heart protection.",
        "brand_price": 95.00,
        "generic_price": 25.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers, AstraZeneca",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "74% savings with generic Rosuvastatin. Same potent statin.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    },
    "lopressor": {
        "brand_name": "Lopressor",
        "generic_name": "Metoprolol",
        "composition": "Metoprolol 50mg",
        "composition_detail": "Metoprolol 50mg for high blood pressure and heart conditions.",
        "brand_price": 50.00,
        "generic_price": 14.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers, Novartis",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "72% savings with generic Metoprolol. Same beta-blocker effectiveness.",
        "quality_assurance": "DCGI approved. Bioequivalent. GMP certified."
    },
    "amlopres": {
        "brand_name": "Amlopres",
        "generic_name": "Amlodipine",
        "composition": "Amlodipine 5mg",
        "composition_detail": "Amlodipine 5mg for hypertension and angina.",
        "brand_price": 45.00,
        "generic_price": 12.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers, Cipla",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "73% savings with generic Amlodipine. Same calcium channel blocker.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    },
    "cozaar": {
        "brand_name": "Cozaar",
        "generic_name": "Losartan",
        "composition": "Losartan 50mg",
        "composition_detail": "Losartan 50mg for hypertension and diabetic kidney disease.",
        "brand_price": 65.00,
        "generic_price": 18.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers, Merck",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "72% savings with generic Losartan. Same ARB effectiveness.",
        "quality_assurance": "DCGI approved. Bioequivalent. GMP certified."
    },
    "plavix": {
        "brand_name": "Plavix",
        "generic_name": "Clopidogrel",
        "composition": "Clopidogrel 75mg",
        "composition_detail": "Clopidogrel 75mg for preventing blood clots after heart attack or stroke.",
        "brand_price": 110.00,
        "generic_price": 30.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers, Sanofi",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "73% savings with generic Clopidogrel. Same antiplatelet effect.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    },
    "zestril": {
        "brand_name": "Zestril",
        "generic_name": "Lisinopril",
        "composition": "Lisinopril 5mg",
        "composition_detail": "Lisinopril 5mg for hypertension and heart failure.",
        "brand_price": 55.00,
        "generic_price": 15.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers, AstraZeneca",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "73% savings with generic Lisinopril. Same ACE inhibitor.",
        "quality_assurance": "DCGI approved. Bioequivalent. GMP certified."
    },
    "cardace": {
        "brand_name": "Cardace",
        "generic_name": "Ramipril",
        "composition": "Ramipril 5mg",
        "composition_detail": "Ramipril 5mg for hypertension and heart failure prevention.",
        "brand_price": 60.00,
        "generic_price": 17.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "72% savings with generic Ramipril. Same ACE inhibitor effectiveness.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    },
    "aten": {
        "brand_name": "Aten",
        "generic_name": "Atenolol",
        "composition": "Atenolol 50mg",
        "composition_detail": "Atenolol 50mg for hypertension and angina prevention.",
        "brand_price": 40.00,
        "generic_price": 11.00,
        "brand_detail": "per strip of 14 tablets",
        "generic_detail": "per strip of 14 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "73% savings with generic Atenolol. Same beta-blocker.",
        "quality_assurance": "DCGI approved. Bioequivalent. GMP certified."
    },
    "vasogard": {
        "brand_name": "Vasogard",
        "generic_name": "Aspirin 75mg",
        "composition": "Aspirin 75mg",
        "composition_detail": "Low-dose Aspirin 75mg for heart attack and stroke prevention.",
        "brand_price": 25.00,
        "generic_price": 6.00,
        "brand_detail": "per strip of 14 tablets",
        "generic_detail": "per strip of 14 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, all pharmacies",
        "why_generic": "76% savings with generic Aspirin. Same cardioprotective effect.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    },

    # ==================== DIABETES (8 Medicines) ====================
    "glyciphage": {
        "brand_name": "Glyciphage",
        "generic_name": "Metformin",
        "composition": "Metformin 500mg",
        "composition_detail": "Metformin 500mg for type 2 diabetes management.",
        "brand_price": 35.00,
        "generic_price": 10.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, various generic manufacturers, Franco-Indian",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "71% savings with generic Metformin. Same diabetes control.",
        "quality_assurance": "CDSCO approved. Bioequivalent. WHO-GMP certified."
    },
    "glucored": {
        "brand_name": "Glucored",
        "generic_name": "Glibenclamide + Metformin",
        "composition": "Glibenclamide 5mg + Metformin 500mg",
        "composition_detail": "Combination for type 2 diabetes management.",
        "brand_price": 45.00,
        "generic_price": 13.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "71% savings with generic combination. Same diabetes control.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    },
    "glipizide": {
        "brand_name": "Glipizide",
        "generic_name": "Glipizide",
        "composition": "Glipizide 5mg",
        "composition_detail": "Glipizide 5mg for type 2 diabetes (sulfonylurea).",
        "brand_price": 40.00,
        "generic_price": 12.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "70% savings with generic Glipizide. Same diabetes medication.",
        "quality_assurance": "CDSCO approved. Bioequivalent. GMP certified."
    },
    "januvia": {
        "brand_name": "Januvia",
        "generic_name": "Sitagliptin",
        "composition": "Sitagliptin 100mg",
        "composition_detail": "Sitagliptin 100mg for type 2 diabetes (DPP-4 inhibitor).",
        "brand_price": 280.00,
        "generic_price": 75.00,
        "brand_detail": "per strip of 7 tablets",
        "generic_detail": "per strip of 7 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers, MSD",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "73% savings with generic Sitagliptin. Same DPP-4 inhibitor.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    },
    "jardiance": {
        "brand_name": "Jardiance",
        "generic_name": "Empagliflozin",
        "composition": "Empagliflozin 10mg",
        "composition_detail": "Empagliflozin 10mg for type 2 diabetes with cardiovascular benefits.",
        "brand_price": 350.00,
        "generic_price": 95.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "73% savings with generic Empagliflozin. Same SGLT2 inhibitor.",
        "quality_assurance": "CDSCO approved. Bioequivalent. GMP certified."
    },
    "glimy": {
        "brand_name": "Glimy",
        "generic_name": "Glimepiride",
        "composition": "Glimepiride 2mg",
        "composition_detail": "Glimepiride 2mg for type 2 diabetes (sulfonylurea).",
        "brand_price": 38.00,
        "generic_price": 11.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "71% savings with generic Glimepiride. Same diabetes control.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    },
    "pioglit": {
        "brand_name": "Pioglit",
        "generic_name": "Pioglitazone",
        "composition": "Pioglitazone 15mg",
        "composition_detail": "Pioglitazone 15mg for type 2 diabetes (thiazolidinedione).",
        "brand_price": 65.00,
        "generic_price": 18.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "72% savings with generic Pioglitazone. Same insulin sensitizer.",
        "quality_assurance": "DCGI approved. Bioequivalent. GMP certified."
    },
    "voglibose": {
        "brand_name": "Voglibose",
        "generic_name": "Voglibose",
        "composition": "Voglibose 0.2mg",
        "composition_detail": "Voglibose 0.2mg for post-meal blood sugar control.",
        "brand_price": 70.00,
        "generic_price": 20.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "71% savings with generic Voglibose. Same alpha-glucosidase inhibitor.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    },

    # ==================== ACID REDUCERS (8 Medicines) ====================
    "pan": {
        "brand_name": "Pan-D",
        "generic_name": "Pantoprazole + Domperidone",
        "composition": "Pantoprazole 40mg + Domperidone 10mg",
        "composition_detail": "Combination for acid reflux and nausea.",
        "brand_price": 110.00,
        "generic_price": 30.00,
        "brand_detail": "per strip of 10 capsules",
        "generic_detail": "per strip of 10 capsules",
        "manufacturers": "Jan Aushadhi, various generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "73% savings with generic combination. Same acid reduction and anti-nausea effect.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    },
    "pan-40": {
        "brand_name": "Pan-40",
        "generic_name": "Pantoprazole",
        "composition": "Pantoprazole 40mg",
        "composition_detail": "Pantoprazole 40mg for acid reflux and GERD.",
        "brand_price": 70.00,
        "generic_price": 18.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "74% savings with generic Pantoprazole. Same PPI effectiveness.",
        "quality_assurance": "CDSCO approved. Bioequivalent. GMP certified."
    },
    "omee": {
        "brand_name": "Omee",
        "generic_name": "Omeprazole",
        "composition": "Omeprazole 20mg",
        "composition_detail": "Omeprazole 20mg for acid reflux and heartburn.",
        "brand_price": 45.00,
        "generic_price": 12.00,
        "brand_detail": "per strip of 10 capsules",
        "generic_detail": "per strip of 10 capsules",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, OTC at generic stores",
        "why_generic": "73% savings with generic Omeprazole. Same PPI for acid reduction.",
        "quality_assurance": "DCGI approved. Bioequivalent. GMP manufactured."
    },
    "pepcid": {
        "brand_name": "Pepcid",
        "generic_name": "Famotidine",
        "composition": "Famotidine 40mg",
        "composition_detail": "Famotidine 40mg for acid reflux and ulcers.",
        "brand_price": 60.00,
        "generic_price": 16.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "73% savings with generic Famotidine. Same H2 blocker.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    },
    "rabium": {
        "brand_name": "Rabium",
        "generic_name": "Rabeprazole",
        "composition": "Rabeprazole 20mg",
        "composition_detail": "Rabeprazole 20mg for GERD and acid reflux.",
        "brand_price": 85.00,
        "generic_price": 22.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "74% savings with generic Rabeprazole. Same PPI effectiveness.",
        "quality_assurance": "DCGI approved. Bioequivalent. GMP certified."
    },
    "ranitidine": {
        "brand_name": "Rantac",
        "generic_name": "Ranitidine",
        "composition": "Ranitidine 150mg",
        "composition_detail": "Ranitidine 150mg for acid reflux and ulcers.",
        "brand_price": 35.00,
        "generic_price": 9.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "74% savings with generic Ranitidine. Same H2 blocker.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    },
    "sucrafil": {
        "brand_name": "Sucrafil",
        "generic_name": "Sucralfate",
        "composition": "Sucralfate 1g",
        "composition_detail": "Sucralfate 1g for stomach ulcers and protection.",
        "brand_price": 75.00,
        "generic_price": 22.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "71% savings with generic Sucralfate. Same ulcer protection.",
        "quality_assurance": "CDSCO approved. Bioequivalent. GMP certified."
    },
    "digene": {
        "brand_name": "Digene",
        "generic_name": "Antacid + Simethicone",
        "composition": "Dried Aluminum Hydroxide + Magnesium Hydroxide + Simethicone",
        "composition_detail": "Antacid for acidity and gas relief.",
        "brand_price": 45.00,
        "generic_price": 12.00,
        "brand_detail": "per bottle of 170ml",
        "generic_detail": "per bottle of 170ml",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, all pharmacies",
        "why_generic": "73% savings with generic antacid. Same acidity relief.",
        "quality_assurance": "CDSCO approved. Same composition. Quality assured."
    },

    # ==================== VITAMINS & SUPPLEMENTS (6 Medicines) ====================
    "becosules": {
        "brand_name": "Becosules",
        "generic_name": "Vitamin B Complex",
        "composition": "Vitamin B Complex (B1, B2, B3, B5, B6, B12)",
        "composition_detail": "Complete Vitamin B Complex for energy and nerve health.",
        "brand_price": 85.00,
        "generic_price": 25.00,
        "brand_detail": "per strip of 10 capsules",
        "generic_detail": "per strip of 10 capsules",
        "manufacturers": "Jan Aushadhi, various generic manufacturers, Pfizer",
        "availability": "Jan Aushadhi Kendras, all generic stores",
        "why_generic": "71% savings with generic Vitamin B Complex. Same essential vitamins.",
        "quality_assurance": "CDSCO approved. Same USP grade vitamins. GMP manufactured."
    },
    "supradyn": {
        "brand_name": "Supradyn",
        "generic_name": "Multivitamin + Multimineral",
        "composition": "Complete multivitamin with minerals",
        "composition_detail": "Daily multivitamin for overall health and immunity.",
        "brand_price": 120.00,
        "generic_price": 35.00,
        "brand_detail": "per strip of 15 tablets",
        "generic_detail": "per strip of 15 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "71% savings with generic multivitamin. Same nutritional support.",
        "quality_assurance": "CDSCO approved. Same vitamin concentrations. Quality assured."
    },
    "calcimax": {
        "brand_name": "Calcimax",
        "generic_name": "Calcium + Vitamin D3",
        "composition": "Calcium Carbonate 500mg + Vitamin D3 250IU",
        "composition_detail": "Calcium and Vitamin D3 for bone health.",
        "brand_price": 90.00,
        "generic_price": 25.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "72% savings with generic Calcium + Vitamin D3. Same bone health support.",
        "quality_assurance": "CDSCO approved. Bioequivalent. GMP certified."
    },
    "vitamin c": {
        "brand_name": "Celin",
        "generic_name": "Vitamin C",
        "composition": "Vitamin C 500mg",
        "composition_detail": "Vitamin C 500mg for immunity and antioxidant support.",
        "brand_price": 40.00,
        "generic_price": 10.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, all pharmacies",
        "why_generic": "75% savings with generic Vitamin C. Same immunity support.",
        "quality_assurance": "CDSCO approved. USP grade. Quality assured."
    },
    "vitamin d3": {
        "brand_name": "Calcirol",
        "generic_name": "Vitamin D3",
        "composition": "Vitamin D3 60000IU",
        "composition_detail": "Vitamin D3 60000IU for deficiency treatment.",
        "brand_price": 120.00,
        "generic_price": 35.00,
        "brand_detail": "per pack of 4 capsules",
        "generic_detail": "per pack of 4 capsules",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "71% savings with generic Vitamin D3. Same vitamin D supplementation.",
        "quality_assurance": "CDSCO approved. Bioequivalent. GMP certified."
    },
    "zincovit": {
        "brand_name": "Zincovit",
        "generic_name": "Zinc + Vitamin C",
        "composition": "Zinc 50mg + Vitamin C 500mg",
        "composition_detail": "Zinc and Vitamin C for immunity and cold prevention.",
        "brand_price": 65.00,
        "generic_price": 18.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "72% savings with generic Zinc + Vitamin C. Same immunity support.",
        "quality_assurance": "CDSCO approved. Same composition. Quality assured."
    },

    # ==================== ALLERGY & RESPIRATORY (6 Medicines) ====================
    "citrizine": {
        "brand_name": "Citrizine",
        "generic_name": "Cetirizine",
        "composition": "Cetirizine 10mg",
        "composition_detail": "Cetirizine 10mg for allergies and hay fever.",
        "brand_price": 40.00,
        "generic_price": 10.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers, Cipla",
        "availability": "Jan Aushadhi Kendras, OTC at generic stores",
        "why_generic": "75% savings with generic Cetirizine. Same antihistamine effect.",
        "quality_assurance": "DCGI approved. Bioequivalent. Quality assured."
    },
    "claritin": {
        "brand_name": "Claritin",
        "generic_name": "Loratadine",
        "composition": "Loratadine 10mg",
        "composition_detail": "Loratadine 10mg for non-drowsy allergy relief.",
        "brand_price": 55.00,
        "generic_price": 15.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "73% savings with generic Loratadine. Same non-drowsy antihistamine.",
        "quality_assurance": "CDSCO approved. Bioequivalent. GMP certified."
    },
    "ventolin": {
        "brand_name": "Ventolin",
        "generic_name": "Salbutamol",
        "composition": "Salbutamol 100mcg",
        "composition_detail": "Salbutamol inhaler for asthma and COPD relief.",
        "brand_price": 180.00,
        "generic_price": 50.00,
        "brand_detail": "per 200-dose inhaler",
        "generic_detail": "per 200-dose inhaler",
        "manufacturers": "Jan Aushadhi, generic manufacturers, GSK",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "72% savings with generic Salbutamol. Same bronchodilator effect.",
        "quality_assurance": "CDSCO approved. Bioequivalent. GMP certified."
    },
    "flovent": {
        "brand_name": "Flovent",
        "generic_name": "Fluticasone",
        "composition": "Fluticasone 125mcg",
        "composition_detail": "Fluticasone inhaler for asthma maintenance.",
        "brand_price": 450.00,
        "generic_price": 120.00,
        "brand_detail": "per 120-dose inhaler",
        "generic_detail": "per 120-dose inhaler",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "73% savings with generic Fluticasone. Same corticosteroid.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    },
    "montair": {
        "brand_name": "Montair",
        "generic_name": "Montelukast",
        "composition": "Montelukast 10mg",
        "composition_detail": "Montelukast 10mg for asthma and allergy prevention.",
        "brand_price": 85.00,
        "generic_price": 24.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "72% savings with generic Montelukast. Same leukotriene inhibitor.",
        "quality_assurance": "CDSCO approved. Bioequivalent. GMP certified."
    },
    "asthalin": {
        "brand_name": "Asthalin",
        "generic_name": "Salbutamol",
        "composition": "Salbutamol 2mg",
        "composition_detail": "Salbutamol 2mg tablet for asthma and COPD.",
        "brand_price": 30.00,
        "generic_price": 8.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "73% savings with generic Salbutamol. Same bronchodilator.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    },

    # ==================== MISCELLANEOUS (Additional to reach 60+) ====================
    "thyronorm": {
        "brand_name": "Thyronorm",
        "generic_name": "Thyroxine",
        "composition": "Thyroxine Sodium 50mcg",
        "composition_detail": "Thyroxine 50mcg for hypothyroidism treatment.",
        "brand_price": 45.00,
        "generic_price": 12.00,
        "brand_detail": "per strip of 100 tablets",
        "generic_detail": "per strip of 100 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "73% savings with generic Thyroxine. Same thyroid hormone replacement.",
        "quality_assurance": "CDSCO approved. Bioequivalent. GMP certified."
    },
    "gabapin": {
        "brand_name": "Gabapin",
        "generic_name": "Gabapentin",
        "composition": "Gabapentin 300mg",
        "composition_detail": "Gabapentin 300mg for neuropathic pain.",
        "brand_price": 95.00,
        "generic_price": 28.00,
        "brand_detail": "per strip of 10 capsules",
        "generic_detail": "per strip of 10 capsules",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "71% savings with generic Gabapentin. Same neuropathic pain relief.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    },
    "tramazac": {
        "brand_name": "Tramazac",
        "generic_name": "Tramadol",
        "composition": "Tramadol 50mg",
        "composition_detail": "Tramadol 50mg for moderate to severe pain.",
        "brand_price": 65.00,
        "generic_price": 18.00,
        "brand_detail": "per strip of 10 capsules",
        "generic_detail": "per strip of 10 capsules",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "72% savings with generic Tramadol. Same pain relief.",
        "quality_assurance": "CDSCO approved. Bioequivalent. GMP certified."
    },
    "flomax": {
        "brand_name": "Flomax",
        "generic_name": "Tamsulosin",
        "composition": "Tamsulosin 0.4mg",
        "composition_detail": "Tamsulosin 0.4mg for BPH urinary symptoms.",
        "brand_price": 85.00,
        "generic_price": 24.00,
        "brand_detail": "per strip of 10 capsules",
        "generic_detail": "per strip of 10 capsules",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "72% savings with generic Tamsulosin. Same alpha-blocker.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    },
    "proscar": {
        "brand_name": "Proscar",
        "generic_name": "Finasteride",
        "composition": "Finasteride 5mg",
        "composition_detail": "Finasteride 5mg for BPH treatment.",
        "brand_price": 70.00,
        "generic_price": 20.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "71% savings with generic Finasteride. Same 5-alpha-reductase inhibitor.",
        "quality_assurance": "CDSCO approved. Bioequivalent. GMP certified."
    },
    "urispas": {
        "brand_name": "Urispas",
        "generic_name": "Flavoxate",
        "composition": "Flavoxate 200mg",
        "composition_detail": "Flavoxate 200mg for urinary bladder spasms.",
        "brand_price": 60.00,
        "generic_price": 17.00,
        "brand_detail": "per strip of 10 tablets",
        "generic_detail": "per strip of 10 tablets",
        "manufacturers": "Jan Aushadhi, generic manufacturers",
        "availability": "Jan Aushadhi Kendras, generic pharmacies",
        "why_generic": "72% savings with generic Flavoxate. Same antispasmodic effect.",
        "quality_assurance": "CDSCO approved. Bioequivalent. Quality assured."
    }
}

print(f"✅ Loaded {len(GENERIC_MEDICINES_DB)} generic medicines into database")

@app.get("/generic-finder")
def find_generic_medicine(name: str):
    """Find generic alternative for brand medicine - 50+ medicines available"""
    
    # Normalize input
    medicine_key = name.lower().strip()
    
    # Try exact match
    if medicine_key in GENERIC_MEDICINES_DB:
        return GENERIC_MEDICINES_DB[medicine_key]
    
    # Try partial match
    for key, value in GENERIC_MEDICINES_DB.items():
        if medicine_key in key or key in medicine_key:
            return value
    
    # Common brand variations mapping
    brand_variations = {
        "dolo 650": "dolo", "crocin advance": "crocin", "calpol 500": "calpol",
        "paracip 500": "paracip", "metacin 500": "metacin", "ibuprofen 400": "brufen",
        "combiflam": "combiflam", "augmentin 625": "augmentin", "azithral 500": "azithral",
        "sporidex 500": "sporidex", "ciprobid 500": "ciprobid", "doxy 1": "doxy",
        "clindac a": "clindac", "flagyl 400": "flagyl", "levoquin 500": "levoquin",
        "mox 500": "mox", "cefakind 200": "cefakind", "claribid 500": "claribid",
        "pan d": "pan", "pan 40": "pan-40", "omee 20": "omee", "pepcid 40": "pepcid",
        "rabium 20": "rabium", "rantac 150": "ranitidine", "sucrafil 1": "sucrafil",
        "glyciphage 500": "glyciphage", "glucored": "glucored", "glipizide 5": "glipizide",
        "januvia 100": "januvia", "jardiance 10": "jardiance", "glimy 2": "glimy",
        "lipitor 10": "lipitor", "crestor 10": "crestor", "lopressor 50": "lopressor",
        "amlopres 5": "amlopres", "cozaar 50": "cozaar", "plavix 75": "plavix",
        "zestril 5": "zestril", "cardace 5": "cardace", "aten 50": "aten",
        "becosules": "becosules", "supradyn": "supradyn", "calcimax": "calcimax",
        "celin": "vitamin c", "calcirol": "vitamin d3", "zincovit": "zincovit",
        "citrizine 10": "citrizine", "claritin 10": "claritin", "ventolin": "ventolin",
        "flovent": "flovent", "montair 10": "montair", "asthalin": "asthalin",
        "thyronorm 50": "thyronorm", "gabapin 300": "gabapin", "tramazac 50": "tramazac",
        "flomax 0.4": "flomax", "proscar 5": "proscar", "urispas 200": "urispas"
    }
    
    if medicine_key in brand_variations:
        return GENERIC_MEDICINES_DB[brand_variations[medicine_key]]
    
    return {"error": f"No generic alternative found for '{name}'. Try searching with a different brand name."}

@app.get("/generic-statistics")
def get_generic_statistics():
    """Get statistics about generic medicine savings"""
    total_medicines = len(GENERIC_MEDICINES_DB)
    total_savings = 0
    
    for medicine in GENERIC_MEDICINES_DB.values():
        savings_percent = ((medicine["brand_price"] - medicine["generic_price"]) / medicine["brand_price"]) * 100
        total_savings += savings_percent
    
    avg_percent = total_savings / total_medicines if total_medicines > 0 else 0
    
    return {
        "total_generics_available": total_medicines,
        "average_savings_percent": round(avg_percent, 1),
        "message": f"Generic medicines save you an average of {round(avg_percent, 1)}% compared to branded medicines!",
        "max_savings": "Up to 80% on some medicines"
    }

@app.get("/all-generic-medicines")
def get_all_generic_medicines():
    """Get list of all available generic medicines"""
    return {
        "count": len(GENERIC_MEDICINES_DB),
        "medicines": list(GENERIC_MEDICINES_DB.keys()),
        "brand_names": [value["brand_name"] for value in GENERIC_MEDICINES_DB.values()]
    }

# ================== FOOD & MEDICINE INTERACTION DATABASE (50+ MEDICINES) ==================

FOOD_INTERACTION_DB = {
    # Blood Thinners
    "warfarin": {
        "medicine_name": "Warfarin (Blood Thinner)",
        "category": "Anticoagulant",
        "overall_risk": "HIGH",
        "critical_warnings": [
            {"icon": "fa-leaf", "text": "DO NOT drastically change intake of Vitamin K rich foods (green leafy vegetables) without consulting doctor"},
            {"icon": "fa-wine-bottle", "text": "Avoid alcohol completely - increases bleeding risk"},
            {"icon": "fa-pills", "text": "Many herbal supplements interact (garlic, ginseng, ginkgo)"}
        ],
        "alcohol": "❌ AVOID completely. Alcohol increases bleeding risk and affects blood thinning effects. Can cause dangerous internal bleeding.",
        "grapefruit": "⚠️ Moderate interaction. Can affect warfarin levels. Limit intake and maintain consistent consumption.",
        "dairy": "✅ No significant interaction. Can be taken normally.",
        "caffeine": "⚠️ Moderate interaction. May affect warfarin metabolism. Maintain consistent intake.",
        "potassium_foods": "✅ No specific restriction for potassium.",
        "vitamin_k_foods": "❌ CRITICAL: Maintain consistent intake of Vitamin K foods (spinach, kale, broccoli, cabbage). Don't drastically change amounts.",
        "timing_advice": "Take at the same time each day (usually evening). Can be taken with or without food. Regular INR monitoring required.",
        "additional_advice": "Avoid cranberry juice, green tea, and herbal supplements. Tell all doctors you're on warfarin before any procedure."
    },
    "aspirin": {
        "medicine_name": "Aspirin",
        "category": "Antiplatelet / Pain Reliever",
        "overall_risk": "MODERATE",
        "critical_warnings": [
            {"icon": "fa-wine-bottle", "text": "Avoid alcohol - increases stomach bleeding risk"},
            {"icon": "fa-utensils", "text": "Take with food to protect stomach"},
            {"icon": "fa-pills", "text": "Avoid with other NSAIDs (ibuprofen, naproxen)"}
        ],
        "alcohol": "❌ AVOID or strictly limit. Increases risk of stomach bleeding and ulcers. No alcohol if taking for heart protection.",
        "grapefruit": "✅ No significant interaction. Can be taken normally.",
        "dairy": "✅ No interaction. Can be taken with milk to reduce stomach upset.",
        "caffeine": "⚠️ Mild interaction. May increase stomach acid. Limit if stomach sensitive.",
        "potassium_foods": "✅ No specific restriction.",
        "vitamin_k_foods": "✅ No interaction with Vitamin K.",
        "timing_advice": "Take with food or milk to reduce stomach upset. For heart protection, take at same time daily (usually evening).",
        "additional_advice": "Don't take with ibuprofen or naproxen. Stop 7 days before surgery. Enteric-coated tablets reduce stomach irritation."
    },
    
    # Diabetes Medications
    "metformin": {
        "medicine_name": "Metformin",
        "category": "Anti-diabetic (Biguanide)",
        "overall_risk": "MODERATE",
        "critical_warnings": [
            {"icon": "fa-wine-bottle", "text": "Avoid excessive alcohol - risk of lactic acidosis"},
            {"icon": "fa-utensils", "text": "Take WITH meals to reduce stomach side effects"},
            {"icon": "fa-pills", "text": "Avoid before contrast dye procedures"}
        ],
        "alcohol": "⚠️ Limit alcohol. Excessive alcohol increases risk of lactic acidosis (rare but serious). Occasional moderate use may be OK.",
        "grapefruit": "✅ No significant interaction with grapefruit.",
        "dairy": "✅ No interaction. Can be taken with food.",
        "caffeine": "✅ No significant interaction.",
        "potassium_foods": "✅ No specific restriction.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "ALWAYS take WITH meals to reduce nausea and diarrhea. Extended release taken with evening meal. Never take on empty stomach.",
        "additional_advice": "Avoid skipping meals. May cause vitamin B12 deficiency with long-term use. Monitor kidney function regularly."
    },
    "glipizide": {
        "medicine_name": "Glipizide",
        "category": "Anti-diabetic (Sulfonylurea)",
        "overall_risk": "MODERATE",
        "critical_warnings": [
            {"icon": "fa-wine-bottle", "text": "Avoid alcohol - can cause severe low blood sugar"},
            {"icon": "fa-clock", "text": "Take 30 minutes before meals"},
            {"icon": "fa-utensils", "text": "Don't skip meals - risk of hypoglycemia"}
        ],
        "alcohol": "❌ Avoid alcohol. Causes severe low blood sugar (hypoglycemia), nausea, headache, flushing.",
        "grapefruit": "✅ No significant interaction.",
        "dairy": "✅ No interaction.",
        "caffeine": "✅ No significant interaction.",
        "potassium_foods": "✅ No specific restriction.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "Take 30 minutes BEFORE breakfast. Consistent meal timing is critical. Never skip meals.",
        "additional_advice": "Always carry sugar source (candy, juice) for hypoglycemia. Monitor blood sugar regularly."
    },
    
    # Cholesterol Medications
    "atorvastatin": {
        "medicine_name": "Atorvastatin (Lipitor)",
        "category": "Statin (Cholesterol Lowering)",
        "overall_risk": "HIGH",
        "critical_warnings": [
            {"icon": "fa-apple-alt", "text": "AVOID grapefruit and grapefruit juice completely"},
            {"icon": "fa-wine-bottle", "text": "Limit alcohol - may increase liver damage risk"},
            {"icon": "fa-pills", "text": "Report muscle pain immediately"}
        ],
        "alcohol": "⚠️ Limit alcohol. Excessive alcohol increases risk of liver damage. Moderate use may be OK.",
        "grapefruit": "❌ CRITICAL: AVOID grapefruit and grapefruit juice completely. Increases drug levels and risk of muscle damage.",
        "dairy": "✅ No interaction. Can be taken normally.",
        "caffeine": "✅ No significant interaction.",
        "potassium_foods": "✅ No restriction.",
        "vitamin_k_foods": "✅ No interaction with Vitamin K.",
        "timing_advice": "Can be taken any time but be consistent. Take with food if stomach upset. Evening dosing may be more effective.",
        "additional_advice": "Report unexplained muscle pain, weakness, or dark urine immediately. Avoid excessive alcohol. Regular liver function tests."
    },
    "rosuvastatin": {
        "medicine_name": "Rosuvastatin (Crestor)",
        "category": "Statin (Cholesterol Lowering)",
        "overall_risk": "MODERATE",
        "critical_warnings": [
            {"icon": "fa-apple-alt", "text": "Avoid grapefruit - less interaction than atorvastatin but still caution"},
            {"icon": "fa-wine-bottle", "text": "Limit alcohol to moderate"},
            {"icon": "fa-pills", "text": "Report muscle pain immediately"}
        ],
        "alcohol": "⚠️ Limit to moderate. Excessive alcohol increases liver risk.",
        "grapefruit": "⚠️ Caution advised. Less interaction than other statins but avoid large amounts.",
        "dairy": "✅ No interaction.",
        "caffeine": "✅ No significant interaction.",
        "potassium_foods": "✅ No restriction.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "Can be taken any time. Consistent daily dosing important.",
        "additional_advice": "Report muscle pain, weakness, or dark urine. Regular monitoring of liver and kidney function."
    },
    
    # Blood Pressure Medications
    "lisinopril": {
        "medicine_name": "Lisinopril",
        "category": "ACE Inhibitor",
        "overall_risk": "MODERATE",
        "critical_warnings": [
            {"icon": "fa-wine-bottle", "text": "Limit alcohol - can cause low blood pressure"},
            {"icon": "fa-apple-alt", "text": "Avoid salt substitutes (high potassium)"},
            {"icon": "fa-banana", "text": "Monitor potassium intake"}
        ],
        "alcohol": "⚠️ Limit alcohol. Can cause dizziness, low blood pressure, and fainting. Avoid if lightheaded.",
        "grapefruit": "✅ No significant interaction.",
        "dairy": "✅ No interaction.",
        "caffeine": "✅ No significant interaction.",
        "potassium_foods": "⚠️ Caution with high potassium foods (bananas, oranges, spinach, potatoes). Monitor potassium levels.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "Take at same time daily. Can be taken with or without food. Take before bed if dizziness occurs.",
        "additional_advice": "Avoid salt substitutes (contain potassium). Stay hydrated. Report persistent dry cough to doctor."
    },
    "amlodipine": {
        "medicine_name": "Amlodipine",
        "category": "Calcium Channel Blocker",
        "overall_risk": "MODERATE",
        "critical_warnings": [
            {"icon": "fa-apple-alt", "text": "Avoid grapefruit - increases drug levels"},
            {"icon": "fa-wine-bottle", "text": "Limit alcohol - may increase dizziness"},
            {"icon": "fa-leaf", "text": "No special restrictions"}
        ],
        "alcohol": "⚠️ Limit alcohol. May increase dizziness and low blood pressure.",
        "grapefruit": "⚠️ Caution advised. Grapefruit can increase amlodipine levels. Avoid large amounts.",
        "dairy": "✅ No interaction.",
        "caffeine": "✅ No significant interaction.",
        "potassium_foods": "✅ No specific restriction.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "Take at same time each day. Can be taken with or without food. Morning dosing recommended.",
        "additional_advice": "May cause ankle swelling. Report irregular heartbeat or severe dizziness. Avoid driving until you know effects."
    },
    "losartan": {
        "medicine_name": "Losartan",
        "category": "ARB (Angiotensin Receptor Blocker)",
        "overall_risk": "LOW",
        "critical_warnings": [
            {"icon": "fa-wine-bottle", "text": "Limit alcohol - may cause low blood pressure"},
            {"icon": "fa-apple-alt", "text": "Avoid salt substitutes (high potassium)"}
        ],
        "alcohol": "⚠️ Limit alcohol. Can cause dizziness and low blood pressure.",
        "grapefruit": "✅ No significant interaction.",
        "dairy": "✅ No interaction.",
        "caffeine": "✅ No significant interaction.",
        "potassium_foods": "⚠️ Monitor potassium intake. Avoid salt substitutes.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "Take at same time daily. Can be taken with or without food.",
        "additional_advice": "Stay hydrated. Report dizziness, fainting, or irregular heartbeat. Regular potassium monitoring."
    },
    
    # Antibiotics
    "amoxicillin": {
        "medicine_name": "Amoxicillin",
        "category": "Antibiotic (Penicillin)",
        "overall_risk": "LOW",
        "critical_warnings": [
            {"icon": "fa-wine-bottle", "text": "Avoid alcohol - reduces antibiotic effectiveness"},
            {"icon": "fa-utensils", "text": "Can take with or without food"},
            {"icon": "fa-pills", "text": "Complete full course even if feeling better"}
        ],
        "alcohol": "⚠️ Avoid alcohol. Reduces effectiveness and may increase side effects. Wait 48 hours after finishing course.",
        "grapefruit": "✅ No interaction.",
        "dairy": "✅ No significant interaction. Can be taken with milk.",
        "caffeine": "✅ No interaction.",
        "potassium_foods": "✅ No restriction.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "Take at evenly spaced intervals. Can be taken with or without food. Complete full course.",
        "additional_advice": "May reduce birth control effectiveness. Use backup contraception. Report severe diarrhea (C. diff risk)."
    },
    "azithromycin": {
        "medicine_name": "Azithromycin (Zithromax)",
        "category": "Antibiotic (Macrolide)",
        "overall_risk": "LOW",
        "critical_warnings": [
            {"icon": "fa-wine-bottle", "text": "Avoid alcohol during treatment"},
            {"icon": "fa-utensils", "text": "Take on empty stomach for best absorption"},
            {"icon": "fa-pills", "text": "Complete full course"}
        ],
        "alcohol": "⚠️ Avoid alcohol. May increase side effects and reduce effectiveness.",
        "grapefruit": "✅ No significant interaction.",
        "dairy": "⚠️ Avoid dairy products within 2 hours of taking (reduces absorption).",
        "caffeine": "✅ No interaction.",
        "potassium_foods": "✅ No restriction.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "Take on empty stomach (1 hour before or 2 hours after food). Take at same time each day.",
        "additional_advice": "Avoid antacids containing aluminum or magnesium. May cause heart rhythm issues in susceptible people."
    },
    "ciprofloxacin": {
        "medicine_name": "Ciprofloxacin",
        "category": "Antibiotic (Fluoroquinolone)",
        "overall_risk": "MODERATE",
        "critical_warnings": [
            {"icon": "fa-coffee", "text": "Avoid caffeine - increases stimulant effects"},
            {"icon": "fa-cheese", "text": "Avoid dairy, calcium-fortified drinks within 6 hours"},
            {"icon": "fa-wine-bottle", "text": "Avoid alcohol during treatment"}
        ],
        "alcohol": "⚠️ Avoid alcohol. Increases risk of CNS side effects and liver toxicity.",
        "grapefruit": "✅ No interaction.",
        "dairy": "❌ Avoid dairy products, calcium-fortified juices, antacids within 6 hours of dose (reduces absorption significantly).",
        "caffeine": "⚠️ Avoid or limit caffeine. Cipro increases caffeine effects (jitters, insomnia, rapid heartbeat).",
        "potassium_foods": "✅ No restriction.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "Take on empty stomach (2 hours after meals). Stay well hydrated. Separate from dairy by 6 hours.",
        "additional_advice": "Report tendon pain immediately (risk of rupture). Avoid sunlight - use sunscreen. Not for children."
    },
    
    # Mental Health Medications
    "sertraline": {
        "medicine_name": "Sertraline (Zoloft)",
        "category": "SSRI Antidepressant",
        "overall_risk": "MODERATE",
        "critical_warnings": [
            {"icon": "fa-wine-bottle", "text": "AVOID alcohol - dangerous interaction"},
            {"icon": "fa-apple-alt", "text": "Grapefruit may increase side effects"},
            {"icon": "fa-pills", "text": "Don't stop suddenly - withdrawal risk"}
        ],
        "alcohol": "❌ AVOID alcohol completely. Increases sedation, dizziness, and risk of liver damage. Dangerous interaction.",
        "grapefruit": "⚠️ Caution advised. Grapefruit may increase sertraline levels and side effects.",
        "dairy": "✅ No interaction.",
        "caffeine": "⚠️ Limit caffeine. May increase anxiety, jitteriness, insomnia.",
        "potassium_foods": "✅ No restriction.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "Take in morning to reduce insomnia. Can be taken with or without food. Take with food if stomach upset.",
        "additional_advice": "May take 2-4 weeks for full effect. Report worsening depression or suicidal thoughts. Risk of serotonin syndrome with other meds."
    },
    "alprazolam": {
        "medicine_name": "Alprazolam (Xanax)",
        "category": "Benzodiazepine",
        "overall_risk": "HIGH",
        "critical_warnings": [
            {"icon": "fa-wine-bottle", "text": "DANGEROUS interaction with alcohol - can cause respiratory depression, death"},
            {"icon": "fa-apple-alt", "text": "Avoid grapefruit - increases sedation"},
            {"icon": "fa-coffee", "text": "Caffeine may reduce effectiveness"}
        ],
        "alcohol": "❌ ABSOLUTELY NO ALCOHOL. Life-threatening interaction causing severe sedation, respiratory depression, coma, death.",
        "grapefruit": "⚠️ Avoid grapefruit. Increases alprazolam levels and sedation effects.",
        "dairy": "✅ No interaction.",
        "caffeine": "⚠️ Caffeine may reduce anti-anxiety effects. Limit intake.",
        "potassium_foods": "✅ No restriction.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "Take as prescribed. Avoid driving until you know effects. Do not stop suddenly (seizure risk).",
        "additional_advice": "HIGH RISK OF ADDICTION. Take exactly as prescribed. Withdrawal can be life-threatening. Never share with others."
    },
    
    # Thyroid Medication
    "levothyroxine": {
        "medicine_name": "Levothyroxine (Thyroxine)",
        "category": "Thyroid Hormone",
        "overall_risk": "MODERATE",
        "critical_warnings": [
            {"icon": "fa-utensils", "text": "Take on EMPTY stomach - critical for absorption"},
            {"icon": "fa-cheese", "text": "Avoid calcium, iron supplements within 4 hours"},
            {"icon": "fa-apple-alt", "text": "Avoid grapefruit juice"}
        ],
        "alcohol": "✅ Moderate alcohol is generally safe. Excessive may affect thyroid function.",
        "grapefruit": "⚠️ Avoid grapefruit juice. May affect absorption.",
        "dairy": "⚠️ Avoid calcium supplements and large amounts of dairy within 4 hours of dose.",
        "caffeine": "✅ No significant interaction.",
        "potassium_foods": "✅ No restriction.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "CRITICAL: Take on empty stomach, 30-60 minutes before breakfast. Same time daily. Separate from other meds by 4 hours.",
        "additional_advice": "Don't take with soy products, walnuts, high-fiber foods. Regular thyroid tests required. Don't stop without doctor advice."
    },
    
    # Pain Relievers
    "ibuprofen": {
        "medicine_name": "Ibuprofen (Advil, Motrin)",
        "category": "NSAID Pain Reliever",
        "overall_risk": "MODERATE",
        "critical_warnings": [
            {"icon": "fa-wine-bottle", "text": "Avoid alcohol - increases stomach bleeding risk"},
            {"icon": "fa-utensils", "text": "Take WITH food to protect stomach"},
            {"icon": "fa-pills", "text": "Don't exceed recommended dose"}
        ],
        "alcohol": "❌ AVOID alcohol. Drastically increases risk of stomach bleeding and ulcers.",
        "grapefruit": "✅ No interaction.",
        "dairy": "✅ OK. Take with milk to reduce stomach upset.",
        "caffeine": "✅ No significant interaction. May increase stomach acid.",
        "potassium_foods": "✅ No restriction.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "ALWAYS take with food or milk. Use lowest effective dose for shortest time.",
        "additional_advice": "Don't take with other NSAIDs (aspirin, naproxen). Avoid if kidney disease or stomach ulcers."
    },
    
    # Acid Reducers
    "omeprazole": {
        "medicine_name": "Omeprazole (Prilosec)",
        "category": "Proton Pump Inhibitor (PPI)",
        "overall_risk": "LOW",
        "critical_warnings": [
            {"icon": "fa-utensils", "text": "Take BEFORE meals for best effect"},
            {"icon": "fa-pills", "text": "Long-term use may affect vitamin B12"},
            {"icon": "fa-clock", "text": "Take at same time daily"}
        ],
        "alcohol": "⚠️ Limit alcohol. May worsen stomach issues.",
        "grapefruit": "✅ No interaction.",
        "dairy": "✅ No interaction.",
        "caffeine": "✅ No interaction.",
        "potassium_foods": "✅ No restriction.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "Take 30-60 minutes BEFORE breakfast. Swallow capsule whole. Complete 14-day OTC course.",
        "additional_advice": "Long-term use may increase fracture risk and B12 deficiency. Don't take with clopidogrel (Plavix)."
    },
    
    # Add more medicines to reach 50+
    "paracetamol": {
        "medicine_name": "Paracetamol (Acetaminophen)",
        "category": "Pain Reliever / Fever Reducer",
        "overall_risk": "MODERATE",
        "critical_warnings": [
            {"icon": "fa-wine-bottle", "text": "AVOID alcohol - severe liver damage risk"},
            {"icon": "fa-pills", "text": "Don't exceed 4000mg/day"},
            {"icon": "fa-utensils", "text": "Can take with or without food"}
        ],
        "alcohol": "❌ AVOID alcohol. Increases risk of severe liver damage, especially with chronic use.",
        "grapefruit": "✅ No interaction.",
        "dairy": "✅ No interaction.",
        "caffeine": "✅ No significant interaction.",
        "potassium_foods": "✅ No restriction.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "Can take with or without food. Take with food if stomach upset.",
        "additional_advice": "Leading cause of acute liver failure. Don't take with other acetaminophen products. Seek help for overdose."
    },
    "prednisone": {
        "medicine_name": "Prednisone",
        "category": "Corticosteroid",
        "overall_risk": "MODERATE",
        "critical_warnings": [
            {"icon": "fa-utensils", "text": "Take with food to protect stomach"},
            {"icon": "fa-wine-bottle", "text": "Limit alcohol - increases stomach bleeding risk"},
            {"icon": {"icon": "fa-banana", "text": "Monitor potassium and sodium"}}
        ],
        "alcohol": "⚠️ Limit alcohol. Increases risk of stomach ulcers and bleeding.",
        "grapefruit": "✅ No interaction.",
        "dairy": "✅ No interaction.",
        "caffeine": "✅ No interaction.",
        "potassium_foods": "⚠️ May cause potassium loss. Eat potassium-rich foods.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "Take with food in the morning (to reduce insomnia). Never stop suddenly - must taper.",
        "additional_advice": "Increases infection risk, blood sugar, blood pressure. Long-term use causes osteoporosis."
    },
    "clopidogrel": {
        "medicine_name": "Clopidogrel (Plavix)",
        "category": "Antiplatelet",
        "overall_risk": "HIGH",
        "critical_warnings": [
            {"icon": "fa-wine-bottle", "text": "Avoid alcohol - increases bleeding risk"},
            {"icon": "fa-apple-alt", "text": "Avoid omeprazole, esomeprazole (PPIs)"},
            {"icon": "fa-leaf", "text": "Avoid St. John's Wort, garlic supplements"}
        ],
        "alcohol": "❌ AVOID alcohol. Increases bleeding risk. No safe amount.",
        "grapefruit": "✅ No significant interaction.",
        "dairy": "✅ No interaction.",
        "caffeine": "✅ No interaction.",
        "potassium_foods": "✅ No restriction.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "Take at same time daily. Can be taken with or without food.",
        "additional_advice": "Stop 5-7 days before surgery. Report unusual bleeding or bruising. May interact with many medications."
    },
    "tramadol": {
        "medicine_name": "Tramadol",
        "category": "Opioid Pain Reliever",
        "overall_risk": "HIGH",
        "critical_warnings": [
            {"icon": "fa-wine-bottle", "text": "DANGEROUS with alcohol - respiratory depression, death"},
            {"icon": {"icon": "fa-pills", "text": "Seizure risk - avoid with other serotonergic drugs"}},
            {"icon": "fa-car", "text": "Do not drive - causes severe drowsiness"}
        ],
        "alcohol": "❌ ABSOLUTELY NO ALCOHOL. Life-threatening respiratory depression and CNS depression.",
        "grapefruit": "✅ No interaction.",
        "dairy": "✅ No interaction.",
        "caffeine": "✅ No interaction.",
        "potassium_foods": "✅ No restriction.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "Take as prescribed. Can be taken with or without food. Never crush extended-release tablets.",
        "additional_advice": "HIGH RISK OF ADDICTION. Seizure risk. Serotonin syndrome risk with SSRIs. Constipation common."
    },
    "gabapentin": {
        "medicine_name": "Gabapentin (Neurontin)",
        "category": "Anticonvulsant / Neuropathic Pain",
        "overall_risk": "MODERATE",
        "critical_warnings": [
            {"icon": "fa-wine-bottle", "text": "Avoid alcohol - increases sedation"},
            {"icon": "fa-pills", "text": "Don't stop suddenly - seizure risk"},
            {"icon": "fa-car", "text": "May cause drowsiness - avoid driving"}
        ],
        "alcohol": "❌ Avoid alcohol. Increases dizziness, drowsiness, and breathing problems.",
        "grapefruit": "✅ No interaction.",
        "dairy": "✅ No interaction.",
        "caffeine": "✅ No interaction.",
        "potassium_foods": "✅ No restriction.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "Take with food to reduce side effects. Take at same times daily.",
        "additional_advice": "May cause weight gain, swelling of extremities. Withdrawal seizures if stopped abruptly."
    }
}

# Add more medicines to reach 50+
additional_interactions = {
    "diazepam": {
        "medicine_name": "Diazepam (Valium)",
        "category": "Benzodiazepine",
        "overall_risk": "HIGH",
        "critical_warnings": [{"icon": "fa-wine-bottle", "text": "DANGEROUS with alcohol - respiratory depression"}],
        "alcohol": "❌ NO ALCOHOL. Life-threatening interaction.",
        "grapefruit": "⚠️ Avoid grapefruit.",
        "dairy": "✅ No interaction.",
        "caffeine": "⚠️ May reduce effects.",
        "potassium_foods": "✅ No restriction.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "Take as prescribed. High addiction risk.",
        "additional_advice": "Do not stop suddenly. Severe withdrawal."
    },
    "fluoxetine": {
        "medicine_name": "Fluoxetine (Prozac)",
        "category": "SSRI Antidepressant",
        "overall_risk": "MODERATE",
        "critical_warnings": [{"icon": "fa-wine-bottle", "text": "Avoid alcohol"}],
        "alcohol": "❌ Avoid alcohol.",
        "grapefruit": "⚠️ Caution advised.",
        "dairy": "✅ No interaction.",
        "caffeine": "⚠️ Limit caffeine.",
        "potassium_foods": "✅ No restriction.",
        "vitamin_k_foods": "✅ No interaction.",
        "timing_advice": "Take in morning. Long half-life.",
        "additional_advice": "May take 4-6 weeks for effect."
    }
}

FOOD_INTERACTION_DB.update(additional_interactions)

print(f"✅ Loaded {len(FOOD_INTERACTION_DB)} food interaction profiles")

@app.get("/food-interaction")
def get_food_interaction(name: str):
    """Get food and drug interaction information for medicines"""
    
    medicine_key = name.lower().strip()
    
    # Try exact match
    if medicine_key in FOOD_INTERACTION_DB:
        return FOOD_INTERACTION_DB[medicine_key]
    
    # Try partial match
    for key, value in FOOD_INTERACTION_DB.items():
        if medicine_key in key or key in medicine_key:
            return value
    
    # Brand name mapping
    brand_mapping = {
        "xanax": "alprazolam", "valium": "diazepam", "prozac": "fluoxetine",
        "zoloft": "sertraline", "lipitor": "atorvastatin", "crestor": "rosuvastatin",
        "plavix": "clopidogrel", "prinivil": "lisinopril", "zestril": "lisinopril",
        "norvasc": "amlodipine", "cozaar": "losartan", "glucophage": "metformin",
        "glucotrol": "glipizide", "augmentin": "amoxicillin", "zithromax": "azithromycin",
        "cipro": "ciprofloxacin", "synthroid": "levothyroxine", "neurontin": "gabapentin",
        "ultram": "tramadol", "advil": "ibuprofen", "motrin": "ibuprofen", "tylenol": "paracetamol"
    }
    
    if medicine_key in brand_mapping:
        return FOOD_INTERACTION_DB[brand_mapping[medicine_key]]
    
    return {"error": f"No interaction information found for '{name}'"}

@app.get("/interaction-statistics")
def get_interaction_statistics():
    """Get statistics about food interactions"""
    return {
        "total_medicines": len(FOOD_INTERACTION_DB),
        "high_risk_count": sum(1 for m in FOOD_INTERACTION_DB.values() if m.get("overall_risk") == "HIGH"),
        "moderate_risk_count": sum(1 for m in FOOD_INTERACTION_DB.values() if m.get("overall_risk") == "MODERATE"),
        "low_risk_count": sum(1 for m in FOOD_INTERACTION_DB.values() if m.get("overall_risk") == "LOW"),
        "message": "Always check food interactions before taking medications!"
    }




# ================== PHARMACY FINDER BACKEND SUPPORT ==================

import requests
from fastapi import Query

@app.get("/pharmacy/nearby")
def get_nearby_pharmacies(lat: float = Query(...), lng: float = Query(...), radius: int = 5000):
    """Get nearby pharmacies using OpenStreetMap Overpass API"""
    
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    query = f"""
    [out:json];
    (
        node["amenity"="pharmacy"](around:{radius},{lat},{lng});
        way["amenity"="pharmacy"](around:{radius},{lat},{lng});
    );
    out body;
    >;
    out skel qt;
    """
    
    try:
        response = requests.post(overpass_url, data=query)
        data = response.json()
        
        pharmacies = []
        for element in data.get("elements", []):
            if element.get("tags", {}).get("amenity") == "pharmacy":
                tags = element.get("tags", {})
                pharmacies.append({
                    "id": element.get("id"),
                    "name": tags.get("name", "Unknown Pharmacy"),
                    "lat": element.get("lat"),
                    "lng": element.get("lon"),
                    "address": tags.get("addr:full", tags.get("addr:street", "Address not available")),
                    "phone": tags.get("phone", tags.get("contact:phone", "Not available")),
                    "opening_hours": tags.get("opening_hours", "Not specified"),
                    "website": tags.get("website", ""),
                    "wheelchair": tags.get("wheelchair", "no")
                })
        
        return {"pharmacies": pharmacies, "count": len(pharmacies)}
        
    except Exception as e:
        return {"error": str(e), "pharmacies": []}

@app.get("/pharmacy/city-search")
def search_pharmacy_by_city(city: str):
    """Search for pharmacies in a specific city"""
    
    # First get city coordinates
    nominatim_url = "https://nominatim.openstreetmap.org/search"
    
    try:
        geo_response = requests.get(
            nominatim_url,
            params={"q": f"{city}, India", "format": "json", "limit": 1}
        )
        geo_data = geo_response.json()
        
        if not geo_data:
            return {"error": "City not found"}
        
        lat = float(geo_data[0]["lat"])
        lng = float(geo_data[0]["lon"])
        
        # Then get pharmacies
        return get_nearby_pharmacies(lat=lat, lng=lng, radius=10000)
        
    except Exception as e:
        return {"error": str(e)}
    

# ================== AI HEALTH RISK PREDICTOR ==================

from pydantic import BaseModel
from typing import Optional

class HealthData(BaseModel):
    age: int
    weight: float
    bmi: Optional[float] = None
    gender: str = "male"
    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None
    blood_sugar: Optional[int] = None
    smoking: str = "never"
    alcohol: str = "never"
    activity: str = "sedentary"
    diet: str = "average"
    family_history: str = "none"
    sleep_quality: str = "good"
    stress_level: str = "moderate"

@app.post("/predict-health-risk")
async def predict_health_risk(data: HealthData):
    """AI-powered health risk prediction for hypertension and heart disease"""
    
    # ========== HYPERTENSION RISK CALCULATION ==========
    hypertension_score = 0
    hypertension_factors = []
    
    # Age factor (0-25 points)
    if data.age > 60:
        hypertension_score += 25
        hypertension_factors.append(f"Age {data.age} years (+25%)")
    elif data.age > 50:
        hypertension_score += 20
        hypertension_factors.append(f"Age {data.age} years (+20%)")
    elif data.age > 40:
        hypertension_score += 12
        hypertension_factors.append(f"Age {data.age} years (+12%)")
    elif data.age > 30:
        hypertension_score += 5
        hypertension_factors.append(f"Age {data.age} years (+5%)")
    
    # BMI factor (0-20 points)
    if data.bmi:
        if data.bmi > 35:
            hypertension_score += 20
            hypertension_factors.append(f"BMI {data.bmi:.1f} (Obese Class II/III) (+20%)")
        elif data.bmi > 30:
            hypertension_score += 15
            hypertension_factors.append(f"BMI {data.bmi:.1f} (Obese) (+15%)")
        elif data.bmi > 25:
            hypertension_score += 8
            hypertension_factors.append(f"BMI {data.bmi:.1f} (Overweight) (+8%)")
        elif data.bmi < 18.5:
            hypertension_score += 3
            hypertension_factors.append(f"BMI {data.bmi:.1f} (Underweight) (+3%)")
    
    # Smoking factor (0-20 points)
    smoking_scores = {"heavy": 20, "regular": 15, "occasional": 8, "former": 3, "never": 0}
    hypertension_score += smoking_scores.get(data.smoking, 0)
    if data.smoking != "never":
        hypertension_factors.append(f"{data.smoking.capitalize()} smoker (+{smoking_scores[data.smoking]}%)")
    
    # Alcohol factor (0-15 points)
    alcohol_scores = {"heavy": 15, "regular": 10, "moderate": 5, "occasional": 2, "never": 0}
    hypertension_score += alcohol_scores.get(data.alcohol, 0)
    if data.alcohol != "never":
        hypertension_factors.append(f"{data.alcohol.capitalize()} alcohol use (+{alcohol_scores[data.alcohol]}%)")
    
    # Physical activity factor (0-15 points)
    activity_scores = {"sedentary": 15, "light": 10, "moderate": 5, "active": -5, "very_active": -10}
    hypertension_score += activity_scores.get(data.activity, 0)
    if data.activity in ["sedentary", "light"]:
        hypertension_factors.append(f"{data.activity.capitalize()} lifestyle (+{activity_scores[data.activity]}%)")
    elif data.activity in ["active", "very_active"]:
        hypertension_factors.append(f"{data.activity.capitalize()} lifestyle ({activity_scores[data.activity]}%)")
    
    # Diet factor (0-15 points)
    diet_scores = {"poor": 15, "average": 8, "good": -5, "excellent": -10}
    hypertension_score += diet_scores.get(data.diet, 0)
    if data.diet in ["poor", "average"]:
        hypertension_factors.append(f"{data.diet.capitalize()} diet (+{diet_scores[data.diet]}%)")
    elif data.diet in ["good", "excellent"]:
        hypertension_factors.append(f"{data.diet.capitalize()} diet ({diet_scores[data.diet]}%)")
    
    # Family history (0-20 points)
    family_scores = {"both": 20, "hypertension": 15, "heart_disease": 10, "none": 0}
    hypertension_score += family_scores.get(data.family_history, 0)
    if data.family_history != "none":
        hypertension_factors.append(f"Family history of {data.family_history} (+{family_scores[data.family_history]}%)")
    
    # Sleep quality (0-10 points)
    sleep_scores = {"poor": 10, "fair": 5, "good": -3, "excellent": -5}
    hypertension_score += sleep_scores.get(data.sleep_quality, 0)
    if data.sleep_quality in ["poor", "fair"]:
        hypertension_factors.append(f"{data.sleep_quality.capitalize()} sleep quality (+{sleep_scores[data.sleep_quality]}%)")
    
    # Stress level (0-15 points)
    stress_scores = {"severe": 15, "high": 10, "moderate": 5, "low": 0}
    hypertension_score += stress_scores.get(data.stress_level, 0)
    if data.stress_level in ["severe", "high"]:
        hypertension_factors.append(f"{data.stress_level.capitalize()} stress level (+{stress_scores[data.stress_level]}%)")
    
    # BP reading if provided (0-30 points)
    if data.systolic_bp and data.diastolic_bp:
        if data.systolic_bp > 140 or data.diastolic_bp > 90:
            hypertension_score += 30
            hypertension_factors.append(f"Current elevated BP ({data.systolic_bp}/{data.diastolic_bp}) (+30%)")
        elif data.systolic_bp > 130 or data.diastolic_bp > 85:
            hypertension_score += 15
            hypertension_factors.append(f"Borderline BP ({data.systolic_bp}/{data.diastolic_bp}) (+15%)")
        elif data.systolic_bp < 120 and data.diastolic_bp < 80:
            hypertension_score -= 10
            hypertension_factors.append(f"Optimal BP reading ({data.systolic_bp}/{data.diastolic_bp}) (-10%)")
    
    # Cap at 0-100
    hypertension_score = max(0, min(100, hypertension_score))
    
    # ========== HEART DISEASE RISK CALCULATION ==========
    heart_score = 0
    heart_factors = []
    
    # Age factor (0-30 points)
    if data.age > 60:
        heart_score += 30
        heart_factors.append(f"Age {data.age} years (+30%)")
    elif data.age > 50:
        heart_score += 20
        heart_factors.append(f"Age {data.age} years (+20%)")
    elif data.age > 40:
        heart_score += 12
        heart_factors.append(f"Age {data.age} years (+12%)")
    elif data.age > 30:
        heart_score += 5
        heart_factors.append(f"Age {data.age} years (+5%)")
    
    # Gender factor (men slightly higher risk)
    if data.gender == "male" and data.age > 45:
        heart_score += 5
        heart_factors.append("Male gender over 45 (+5%)")
    
    # BMI factor (0-20 points)
    if data.bmi:
        if data.bmi > 35:
            heart_score += 20
            heart_factors.append(f"BMI {data.bmi:.1f} (Severe obesity) (+20%)")
        elif data.bmi > 30:
            heart_score += 15
            heart_factors.append(f"BMI {data.bmi:.1f} (Obese) (+15%)")
        elif data.bmi > 25:
            heart_score += 8
            heart_factors.append(f"BMI {data.bmi:.1f} (Overweight) (+8%)")
    
    # Smoking factor (0-25 points)
    smoking_heart_scores = {"heavy": 25, "regular": 20, "occasional": 10, "former": 5, "never": 0}
    heart_score += smoking_heart_scores.get(data.smoking, 0)
    if data.smoking != "never":
        heart_factors.append(f"{data.smoking.capitalize()} smoker (+{smoking_heart_scores[data.smoking]}%)")
    
    # Blood sugar factor (0-20 points)
    if data.blood_sugar:
        if data.blood_sugar > 200:
            heart_score += 20
            heart_factors.append(f"Blood sugar {data.blood_sugar} mg/dL (Very high) (+20%)")
        elif data.blood_sugar > 140:
            heart_score += 15
            heart_factors.append(f"Blood sugar {data.blood_sugar} mg/dL (High) (+15%)")
        elif data.blood_sugar > 100:
            heart_score += 8
            heart_factors.append(f"Blood sugar {data.blood_sugar} mg/dL (Prediabetes) (+8%)")
    
    # Physical activity (0-20 points)
    activity_heart_scores = {"sedentary": 20, "light": 12, "moderate": 5, "active": -10, "very_active": -15}
    heart_score += activity_heart_scores.get(data.activity, 0)
    if data.activity in ["sedentary", "light"]:
        heart_factors.append(f"{data.activity.capitalize()} lifestyle (+{activity_heart_scores[data.activity]}%)")
    elif data.activity in ["active", "very_active"]:
        heart_factors.append(f"{data.activity.capitalize()} lifestyle ({activity_heart_scores[data.activity]}%)")
    
    # Diet factor (0-15 points)
    diet_heart_scores = {"poor": 15, "average": 8, "good": -8, "excellent": -15}
    heart_score += diet_heart_scores.get(data.diet, 0)
    if data.diet in ["poor", "average"]:
        heart_factors.append(f"{data.diet.capitalize()} diet (+{diet_heart_scores[data.diet]}%)")
    elif data.diet in ["good", "excellent"]:
        heart_factors.append(f"{data.diet.capitalize()} diet ({diet_heart_scores[data.diet]}%)")
    
    # Family history (0-25 points)
    family_heart_scores = {"both": 25, "heart_disease": 20, "hypertension": 10, "none": 0}
    heart_score += family_heart_scores.get(data.family_history, 0)
    if data.family_history != "none":
        heart_factors.append(f"Family history of {data.family_history} (+{family_heart_scores[data.family_history]}%)")
    
    # Alcohol factor (0-15 points)
    alcohol_heart_scores = {"heavy": 15, "regular": 10, "moderate": 3, "occasional": 0, "never": 0}
    heart_score += alcohol_heart_scores.get(data.alcohol, 0)
    if data.alcohol in ["heavy", "regular"]:
        heart_factors.append(f"{data.alcohol.capitalize()} alcohol use (+{alcohol_heart_scores[data.alcohol]}%)")
    
    # Stress level (0-15 points)
    stress_heart_scores = {"severe": 15, "high": 10, "moderate": 5, "low": 0}
    heart_score += stress_heart_scores.get(data.stress_level, 0)
    if data.stress_level in ["severe", "high"]:
        heart_factors.append(f"{data.stress_level.capitalize()} stress level (+{stress_heart_scores[data.stress_level]}%)")
    
    # Hypertension linkage (heart disease risk increases with hypertension)
    hypertension_adjusted = hypertension_score / 100
    heart_score += hypertension_adjusted * 15
    if hypertension_score > 40:
        heart_factors.append(f"High hypertension risk ({hypertension_score}%) increases heart disease risk")
    
    # Cap at 0-100
    heart_score = max(0, min(100, heart_score))
    
    # Overall health score
    overall_score = round(100 - ((hypertension_score + heart_score) / 2))
    
    # Generate recommendations
    recommendations = []
    
    if overall_score < 60:
        recommendations.append("🏥 Schedule a comprehensive health checkup with your doctor")
    
    if hypertension_score > 40:
        recommendations.append("❤️ Monitor your blood pressure regularly at home")
        recommendations.append("🧂 Reduce sodium intake - limit salt in cooking and avoid processed foods")
        recommendations.append("🏃 Exercise for at least 30 minutes daily to help lower blood pressure")
    
    if heart_score > 40:
        recommendations.append("🍎 Adopt a heart-healthy Mediterranean diet rich in fruits, vegetables, and whole grains")
        recommendations.append("🏋️ Include cardio exercise 5 times per week (brisk walking, jogging, swimming)")
        recommendations.append("🩸 Get your cholesterol and blood sugar levels checked regularly")
    
    if data.smoking != "never":
        recommendations.append("🚭 Quit smoking - it's the single best thing you can do for your heart health")
    
    if data.alcohol in ["heavy", "regular"]:
        recommendations.append("🍷 Reduce alcohol consumption to moderate levels (1-2 drinks per day max)")
    
    if data.activity in ["sedentary", "light"]:
        recommendations.append("🏃 Start with 15-minute walks daily and gradually increase duration")
    
    if data.diet in ["poor", "average"]:
        recommendations.append("🥗 Eat more fruits, vegetables, whole grains, and lean proteins")
    
    if data.sleep_quality in ["poor", "fair"]:
        recommendations.append("😴 Aim for 7-8 hours of quality sleep - maintain a consistent sleep schedule")
    
    if data.stress_level in ["severe", "high"]:
        recommendations.append("🧘 Practice stress management techniques like meditation, deep breathing, or yoga")
    
    # General recommendations
    if len(recommendations) < 3:
        recommendations.append("💧 Drink 8-10 glasses of water daily")
        recommendations.append("🩺 Get annual health checkups")
        recommendations.append("📱 Track your health metrics regularly")
    
    return {
        "hypertension_risk": round(hypertension_score),
        "heart_disease_risk": round(heart_score),
        "overall_score": overall_score,
        "hypertension_factors": hypertension_factors[:5],
        "heart_factors": heart_factors[:5],
        "recommendations": recommendations[:8]
    }


# ================== HOSPITAL COST ESTIMATOR ==================

from pydantic import BaseModel

class CostEstimateRequest(BaseModel):
    disease: str
    city_tier: str
    insurance: str

# Comprehensive treatment cost database
TREATMENT_COSTS = {
    "appendicitis": {
        "name": "Appendicitis (Appendix Removal Surgery)",
        "government": {"min": 15000, "max": 30000, "wait_time": "2-4 weeks"},
        "private_budget": {"min": 50000, "max": 80000, "wait_time": "3-5 days"},
        "premium": {"min": 100000, "max": 150000, "wait_time": "1-2 days"},
        "cost_breakdown": [
            {"name": "Surgeon Fees", "cost": 25000},
            {"name": "Anesthesia", "cost": 8000},
            {"name": "Hospital Room (3-5 days)", "cost": 15000},
            {"name": "Operation Theatre", "cost": 12000},
            {"name": "Medicines & Consumables", "cost": 10000},
            {"name": "Diagnostic Tests", "cost": 5000}
        ],
        "savings_tips": [
            "Choose government hospital for lowest cost (saves 60-70%)",
            "Check if you qualify for Ayushman Bharat scheme",
            "Compare prices between 2-3 private hospitals",
            "Avoid unnecessary diagnostic tests"
        ]
    },
    "gallbladder": {
        "name": "Gallbladder Removal (Cholecystectomy)",
        "government": {"min": 18000, "max": 35000, "wait_time": "3-4 weeks"},
        "private_budget": {"min": 55000, "max": 90000, "wait_time": "3-5 days"},
        "premium": {"min": 120000, "max": 180000, "wait_time": "1-2 days"},
        "cost_breakdown": [
            {"name": "Surgeon Fees", "cost": 30000},
            {"name": "Anesthesia", "cost": 10000},
            {"name": "Hospital Room (2-3 days)", "cost": 12000},
            {"name": "Laparoscopic Equipment", "cost": 15000},
            {"name": "Medicines", "cost": 8000},
            {"name": "Diagnostic Tests", "cost": 5000}
        ],
        "savings_tips": [
            "Laparoscopic surgery costs more but recovery is faster",
            "Daycare surgery options available in some hospitals",
            "Check for cashless insurance facilities"
        ]
    },
    "hernia": {
        "name": "Hernia Repair Surgery",
        "government": {"min": 12000, "max": 25000, "wait_time": "2-3 weeks"},
        "private_budget": {"min": 40000, "max": 70000, "wait_time": "2-4 days"},
        "premium": {"min": 80000, "max": 120000, "wait_time": "1-2 days"},
        "cost_breakdown": [
            {"name": "Surgeon Fees", "cost": 20000},
            {"name": "Mesh (Implant)", "cost": 15000},
            {"name": "Anesthesia", "cost": 8000},
            {"name": "Hospital Room (1-2 days)", "cost": 8000},
            {"name": "Operation Theatre", "cost": 10000},
            {"name": "Medicines", "cost": 5000}
        ],
        "savings_tips": [
            "Laparoscopic hernia repair costs more but less pain",
            "Daycare surgery available for small hernias",
            "Some government hospitals provide free mesh"
        ]
    },
    "kidney_stone": {
        "name": "Kidney Stone Removal (Lithotripsy/Laser)",
        "government": {"min": 10000, "max": 20000, "wait_time": "2-4 weeks"},
        "private_budget": {"min": 35000, "max": 60000, "wait_time": "2-3 days"},
        "premium": {"min": 70000, "max": 100000, "wait_time": "1-2 days"},
        "cost_breakdown": [
            {"name": "Urologist Fees", "cost": 15000},
            {"name": "Lithotripsy/Laser", "cost": 25000},
            {"name": "Anesthesia", "cost": 8000},
            {"name": "Hospital Room (1-2 days)", "cost": 8000},
            {"name": "Diagnostic Tests (CT/KUB)", "cost": 5000},
            {"name": "Medicines", "cost": 4000}
        ],
        "savings_tips": [
            "ESWL is cheaper than laser surgery",
            "Small stones may pass naturally with medication",
            "Drink plenty of water to prevent recurrence"
        ]
    },
    "cataract": {
        "name": "Cataract Surgery (Phacoemulsification)",
        "government": {"min": 5000, "max": 10000, "wait_time": "4-6 weeks"},
        "private_budget": {"min": 20000, "max": 35000, "wait_time": "1-2 days"},
        "premium": {"min": 50000, "max": 80000, "wait_time": "Same day"},
        "cost_breakdown": [
            {"name": "Surgeon Fees", "cost": 15000},
            {"name": "Intraocular Lens (IOL)", "cost": 10000},
            {"name": "Operation Theatre", "cost": 8000},
            {"name": "Phaco Machine", "cost": 5000},
            {"name": "Medicines & Eye Drops", "cost": 3000},
            {"name": "Pre-op Tests", "cost": 2000}
        ],
        "savings_tips": [
            "Government hospitals offer free cataract surgery",
            "IOL cost varies greatly - choose basic lens for savings",
            "Many NGOs provide free eye camps"
        ]
    },
    "angioplasty": {
        "name": "Angioplasty (Heart Stent)",
        "government": {"min": 50000, "max": 80000, "wait_time": "2-3 weeks"},
        "private_budget": {"min": 150000, "max": 200000, "wait_time": "2-3 days"},
        "premium": {"min": 250000, "max": 350000, "wait_time": "1-2 days"},
        "cost_breakdown": [
            {"name": "Interventional Cardiologist", "cost": 50000},
            {"name": "Stent (Drug-eluting)", "cost": 80000},
            {"name": "Cath Lab Charges", "cost": 40000},
            {"name": "Hospital Room (2-3 days)", "cost": 20000},
            {"name": "Angiography", "cost": 15000},
            {"name": "Medicines", "cost": 15000}
        ],
        "savings_tips": [
            "Ayushman Bharat covers heart procedures up to ₹5 lakhs",
            "Choose bare metal stent over drug-eluting for savings",
            "Corporate hospitals offer package deals"
        ]
    },
    "bypass": {
        "name": "Heart Bypass Surgery (CABG)",
        "government": {"min": 100000, "max": 150000, "wait_time": "4-6 weeks"},
        "private_budget": {"min": 250000, "max": 350000, "wait_time": "1-2 weeks"},
        "premium": {"min": 400000, "max": 600000, "wait_time": "3-5 days"},
        "cost_breakdown": [
            {"name": "Cardiac Surgeon Fees", "cost": 80000},
            {"name": "Anesthesia & Perfusionist", "cost": 40000},
            {"name": "Operation Theatre", "cost": 60000},
            {"name": "ICU Stay (5-7 days)", "cost": 100000},
            {"name": "Hospital Room (7-10 days)", "cost": 50000},
            {"name": "Medicines & Consumables", "cost": 40000},
            {"name": "Diagnostic Tests", "cost": 30000}
        ],
        "savings_tips": [
            "Major surgery - ensure you have good insurance",
            "Government hospitals offer subsidized heart surgery",
            "Corporate hospitals may offer package deals",
            "Rehabilitation costs additional"
        ]
    },
    "hip_replacement": {
        "name": "Hip Replacement Surgery",
        "government": {"min": 60000, "max": 100000, "wait_time": "6-8 weeks"},
        "private_budget": {"min": 180000, "max": 250000, "wait_time": "1-2 weeks"},
        "premium": {"min": 300000, "max": 450000, "wait_time": "3-5 days"},
        "cost_breakdown": [
            {"name": "Orthopedic Surgeon", "cost": 50000},
            {"name": "Hip Implant", "cost": 100000},
            {"name": "Anesthesia", "cost": 20000},
            {"name": "Operation Theatre", "cost": 40000},
            {"name": "Hospital Room (5-7 days)", "cost": 50000},
            {"name": "Physiotherapy", "cost": 20000},
            {"name": "Medicines", "cost": 20000}
        ],
        "savings_tips": [
            "Implant quality greatly affects cost",
            "Government hospitals have cheaper implants",
            "Physiotherapy is crucial for recovery - budget for it",
            "Check if insurance covers joint replacement"
        ]
    },
    "knee_replacement": {
        "name": "Knee Replacement Surgery",
        "government": {"min": 60000, "max": 100000, "wait_time": "6-8 weeks"},
        "private_budget": {"min": 170000, "max": 240000, "wait_time": "1-2 weeks"},
        "premium": {"min": 280000, "max": 420000, "wait_time": "3-5 days"},
        "cost_breakdown": [
            {"name": "Orthopedic Surgeon", "cost": 50000},
            {"name": "Knee Implant", "cost": 90000},
            {"name": "Anesthesia", "cost": 20000},
            {"name": "Operation Theatre", "cost": 40000},
            {"name": "Hospital Room (5-7 days)", "cost": 50000},
            {"name": "Physiotherapy", "cost": 25000},
            {"name": "Medicines", "cost": 15000}
        ],
        "savings_tips": [
            "Partial knee replacement cheaper than total",
            "Implant choice (Indian vs Imported) affects cost",
            "Some hospitals offer package deals",
            "Recovery time is 6-8 weeks"
        ]
    },
    "csection": {
        "name": "C-Section (Cesarean Delivery)",
        "government": {"min": 10000, "max": 20000, "wait_time": "Emergency only"},
        "private_budget": {"min": 40000, "max": 70000, "wait_time": "Scheduled"},
        "premium": {"min": 100000, "max": 150000, "wait_time": "Scheduled"},
        "cost_breakdown": [
            {"name": "Obstetrician Fees", "cost": 25000},
            {"name": "Anesthesia", "cost": 10000},
            {"name": "Hospital Room (3-4 days)", "cost": 20000},
            {"name": "Operation Theatre", "cost": 15000},
            {"name": "Newborn Care", "cost": 10000},
            {"name": "Medicines", "cost": 8000},
            {"name": "Diagnostic Tests", "cost": 5000}
        ],
        "savings_tips": [
            "PMJAY covers delivery costs for eligible families",
            "Normal delivery is significantly cheaper than C-section",
            "Choose hospital within your insurance network",
            "Package deals available in many hospitals"
        ]
    },
    "normal_delivery": {
        "name": "Normal Delivery (Vaginal Birth)",
        "government": {"min": 3000, "max": 8000, "wait_time": "Emergency only"},
        "private_budget": {"min": 20000, "max": 40000, "wait_time": "Scheduled"},
        "premium": {"min": 60000, "max": 100000, "wait_time": "Scheduled"},
        "cost_breakdown": [
            {"name": "Obstetrician Fees", "cost": 15000},
            {"name": "Delivery Room Charges", "cost": 10000},
            {"name": "Hospital Room (2-3 days)", "cost": 12000},
            {"name": "Newborn Care", "cost": 8000},
            {"name": "Medicines", "cost": 5000},
            {"name": "Diagnostic Tests", "cost": 3000}
        ],
        "savings_tips": [
            "Government hospitals offer free delivery",
            "PMJAY covers delivery costs",
            "Normal delivery has faster recovery than C-section",
            "Consider birth packages in private hospitals"
        ]
    },
    "dialysis": {
        "name": "Dialysis (Per Session)",
        "government": {"min": 500, "max": 1000, "wait_time": "1-2 weeks"},
        "private_budget": {"min": 2000, "max": 3500, "wait_time": "1-2 days"},
        "premium": {"min": 4000, "max": 6000, "wait_time": "Same day"},
        "cost_breakdown": [
            {"name": "Dialysis Procedure", "cost": 2000},
            {"name": "Dialyzer (Filter)", "cost": 800},
            {"name": "Nursing Care", "cost": 500},
            {"name": "Medicines (Erythropoietin)", "cost": 1000},
            {"name": "Lab Tests", "cost": 500}
        ],
        "savings_tips": [
            "Government hospitals offer heavily subsidized dialysis",
            "PMJAY covers 3-5 dialysis sessions per week",
            "Home dialysis may be cheaper long-term",
            "Check for dialysis packages"
        ]
    },
    "chemotherapy": {
        "name": "Chemotherapy (Per Cycle)",
        "government": {"min": 5000, "max": 15000, "wait_time": "1-2 weeks"},
        "private_budget": {"min": 20000, "max": 40000, "wait_time": "3-5 days"},
        "premium": {"min": 50000, "max": 100000, "wait_time": "1-2 days"},
        "cost_breakdown": [
            {"name": "Chemotherapy Drugs", "cost": 25000},
            {"name": "Oncologist Fees", "cost": 10000},
            {"name": "Daycare Charges", "cost": 5000},
            {"name": "Supportive Medications", "cost": 8000},
            {"name": "Lab Tests", "cost": 5000},
            {"name": "Nursing Care", "cost": 3000}
        ],
        "savings_tips": [
            "Generic chemotherapy drugs are much cheaper",
            "Government hospitals provide free cancer treatment",
            "Many NGOs support cancer patients",
            "Insurance is crucial for cancer treatment"
        ]
    },
    "mri": {
        "name": "MRI Scan (One Body Part)",
        "government": {"min": 2000, "max": 4000, "wait_time": "2-3 weeks"},
        "private_budget": {"min": 4000, "max": 7000, "wait_time": "1-2 days"},
        "premium": {"min": 8000, "max": 12000, "wait_time": "Same day"},
        "cost_breakdown": [
            {"name": "MRI Procedure", "cost": 5000},
            {"name": "Contrast Material (if needed)", "cost": 3000},
            {"name": "Radiologist Interpretation", "cost": 2000},
            {"name": "CD/Report Charges", "cost": 500}
        ],
        "savings_tips": [
            "Standalone diagnostic centers cheaper than hospitals",
            "Night/early morning slots often discounted",
            "Corporate packages offer discounted rates",
            "Check if doctor's prescription is required"
        ]
    },
    "ct_scan": {
        "name": "CT Scan (One Body Part)",
        "government": {"min": 1000, "max": 2000, "wait_time": "1-2 weeks"},
        "private_budget": {"min": 2000, "max": 4000, "wait_time": "1-2 days"},
        "premium": {"min": 5000, "max": 8000, "wait_time": "Same day"},
        "cost_breakdown": [
            {"name": "CT Procedure", "cost": 3500},
            {"name": "Contrast (if needed)", "cost": 2000},
            {"name": "Radiologist Interpretation", "cost": 1500},
            {"name": "Report Charges", "cost": 500}
        ],
        "savings_tips": [
            "Non-contrast CT is cheaper",
            "Multiple body parts scanned together cost less per part",
            "Standalone centers offer better rates"
        ]
    },
    "dental_implant": {
        "name": "Dental Implant (Single Tooth)",
        "government": {"min": 5000, "max": 10000, "wait_time": "4-6 weeks"},
        "private_budget": {"min": 20000, "max": 35000, "wait_time": "1-2 weeks"},
        "premium": {"min": 50000, "max": 80000, "wait_time": "3-5 days"},
        "cost_breakdown": [
            {"name": "Implant Fixture", "cost": 15000},
            {"name": "Abutment", "cost": 5000},
            {"name": "Crown (Ceramic)", "cost": 15000},
            {"name": "Oral Surgeon Fees", "cost": 10000},
            {"name": "CBCT Scan", "cost": 3000},
            {"name": "Medicines", "cost": 2000}
        ],
        "savings_tips": [
            "Indian implants are cheaper than imported",
            "Dental colleges offer reduced rates",
            "Some hospitals have dental packages",
            "Insurance rarely covers dental implants"
        ]
    },
    "tonsillectomy": {
        "name": "Tonsillectomy",
        "government": {"min": 8000, "max": 15000, "wait_time": "3-4 weeks"},
        "private_budget": {"min": 25000, "max": 45000, "wait_time": "1-2 weeks"},
        "premium": {"min": 60000, "max": 90000, "wait_time": "2-3 days"},
        "cost_breakdown": [
            {"name": "ENT Surgeon Fees", "cost": 15000},
            {"name": "Anesthesia", "cost": 8000},
            {"name": "Hospital Room (1-2 days)", "cost": 10000},
            {"name": "Operation Theatre", "cost": 12000},
            {"name": "Medicines", "cost": 5000},
            {"name": "Diagnostic Tests", "cost": 3000}
        ],
        "savings_tips": [
            "Laser tonsillectomy costs more than cold steel",
            "Daycare surgery option available",
            "Children recover faster than adults"
        ]
    },
    "fracture": {
        "name": "Fracture Treatment (With Surgery)",
        "government": {"min": 15000, "max": 30000, "wait_time": "2-3 weeks"},
        "private_budget": {"min": 50000, "max": 80000, "wait_time": "2-4 days"},
        "premium": {"min": 100000, "max": 150000, "wait_time": "1-2 days"},
        "cost_breakdown": [
            {"name": "Orthopedic Surgeon", "cost": 25000},
            {"name": "Implants (Plate/Screws)", "cost": 30000},
            {"name": "Anesthesia", "cost": 10000},
            {"name": "Operation Theatre", "cost": 20000},
            {"name": "Hospital Room (3-5 days)", "cost": 20000},
            {"name": "Physiotherapy", "cost": 10000},
            {"name": "Medicines", "cost": 8000}
        ],
        "savings_tips": [
            "Indian implants are cheaper than imported",
            "Conservative treatment (cast) avoids surgery costs",
            "Physiotherapy is essential for recovery"
        ]
    },
    "stroke": {
        "name": "Stroke Treatment (Hospitalization)",
        "government": {"min": 20000, "max": 40000, "wait_time": "Emergency"},
        "private_budget": {"min": 80000, "max": 120000, "wait_time": "Emergency"},
        "premium": {"min": 150000, "max": 250000, "wait_time": "Emergency"},
        "cost_breakdown": [
            {"name": "Neurologist Fees", "cost": 30000},
            {"name": "ICU Stay (5-7 days)", "cost": 100000},
            {"name": "MRI/CT Brain", "cost": 10000},
            {"name": "Thrombolysis (if applicable)", "cost": 50000},
            {"name": "Physiotherapy", "cost": 20000},
            {"name": "Medicines", "cost": 25000},
            {"name": "Speech Therapy (if needed)", "cost": 15000}
        ],
        "savings_tips": [
            "Emergency treatment - act FAST",
            "PMJAY covers stroke treatment",
            "Early treatment reduces long-term disability costs",
            "Rehabilitation costs are significant - budget accordingly"
        ]
    },
    "pneumonia": {
        "name": "Pneumonia Treatment (Hospitalization)",
        "government": {"min": 5000, "max": 15000, "wait_time": "Emergency"},
        "private_budget": {"min": 25000, "max": 45000, "wait_time": "Emergency"},
        "premium": {"min": 60000, "max": 100000, "wait_time": "Emergency"},
        "cost_breakdown": [
            {"name": "Physician Fees", "cost": 15000},
            {"name": "Hospital Room (5-7 days)", "cost": 35000},
            {"name": "Antibiotics & Medications", "cost": 15000},
            {"name": "Chest X-Ray", "cost": 2000},
            {"name": "Lab Tests", "cost": 5000},
            {"name": "Oxygen Support", "cost": 10000},
            {"name": "Nebulization", "cost": 3000}
        ],
        "savings_tips": [
            "Mild pneumonia can be treated at home (outpatient)",
            "Government hospitals provide effective treatment",
            "Prevention through vaccination saves money"
        ]
    }
}

@app.post("/estimate-treatment-cost")
async def estimate_treatment_cost(request: CostEstimateRequest):
    """Estimate treatment costs based on disease, city tier, and insurance"""
    
    if request.disease not in TREATMENT_COSTS:
        return {"error": "Treatment not found"}
    
    treatment = TREATMENT_COSTS[request.disease]
    
    # City tier multipliers
    city_multipliers = {
        "tier1": 1.0,
        "tier2": 0.85,
        "tier3": 0.70
    }
    
    multiplier = city_multipliers.get(request.city_tier, 1.0)
    
    city_display = {
        "tier1": "Tier 1 City (Metro)",
        "tier2": "Tier 2 City",
        "tier3": "Tier 3 City/Town"
    }.get(request.city_tier, "Selected City")
    
    # Apply city multiplier to costs
    govt_min = int(treatment["government"]["min"] * multiplier)
    govt_max = int(treatment["government"]["max"] * multiplier)
    private_min = int(treatment["private_budget"]["min"] * multiplier)
    private_max = int(treatment["private_budget"]["max"] * multiplier)
    premium_min = int(treatment["premium"]["min"] * multiplier)
    premium_max = int(treatment["premium"]["max"] * multiplier)
    
    # Adjust breakdown costs
    adjusted_breakdown = []
    for item in treatment["cost_breakdown"]:
        adjusted_breakdown.append({
            "name": item["name"],
            "cost": int(item["cost"] * multiplier)
        })
    
    # Insurance calculation
    insurance_impact = None
    if request.insurance == "partial":
        avg_cost = (private_min + private_max) // 2
        cover = avg_cost // 2
        insurance_impact = {
            "total_cost": avg_cost,
            "insurance_cover": cover,
            "out_of_pocket": avg_cost - cover
        }
    elif request.insurance == "full":
        avg_cost = (private_min + private_max) // 2
        insurance_impact = {
            "total_cost": avg_cost,
            "insurance_cover": avg_cost,
            "out_of_pocket": 0
        }
    elif request.insurance == "government":
        avg_cost = (private_min + private_max) // 2
        cover = min(avg_cost, 500000)  # PMJAY covers up to 5 lakhs
        insurance_impact = {
            "total_cost": avg_cost,
            "insurance_cover": cover,
            "out_of_pocket": max(0, avg_cost - cover),
            "scheme": "Ayushman Bharat (PMJAY)"
        }
    
    return {
        "treatment_name": treatment["name"],
        "city_display": city_display,
        "government": {
            "min": govt_min,
            "max": govt_max,
            "wait_time": treatment["government"]["wait_time"]
        },
        "private_budget": {
            "min": private_min,
            "max": private_max,
            "wait_time": treatment["private_budget"]["wait_time"]
        },
        "premium": {
            "min": premium_min,
            "max": premium_max,
            "wait_time": treatment["premium"]["wait_time"]
        },
        "cost_breakdown": adjusted_breakdown,
        "insurance_impact": insurance_impact,
        "savings_tips": treatment["savings_tips"]
    }



