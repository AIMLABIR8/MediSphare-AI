// ================== CONFIG ==================
const API_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? "http://127.0.0.1:8000" 
    : "/api";

// ================== PRESCRIPTION ANALYZER VARIABLES ==================
let currentPrescriptionImage = null;
let extractedPrescriptionText = '';

// ================== PRESCRIPTION ANALYZER FUNCTIONS ==================

function handlePrescriptionFile(input) {
    const file = input.files[0];
    if (file) {
        validateAndProcessPrescriptionFile(file);
    }
}

function validateAndProcessPrescriptionFile(file) {
    const validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
    if (!validTypes.includes(file.type)) {
        showPrescriptionError('Please upload a valid image file (JPG, PNG, or WEBP)');
        return;
    }

    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
        showPrescriptionError('File size must be less than 10MB');
        return;
    }

    displayPrescriptionImage(file);
}

function displayPrescriptionImage(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
        currentPrescriptionImage = e.target.result;
        document.getElementById('presPreviewImg').src = currentPrescriptionImage;
        document.getElementById('presImagePreview').classList.remove('hidden');
        document.getElementById('presProcessBtn').classList.remove('hidden');
        document.getElementById('presUploadArea').classList.add('hidden');
    };
    reader.readAsDataURL(file);
}

function removePrescriptionImage() {
    currentPrescriptionImage = null;
    document.getElementById('presImagePreview').classList.add('hidden');
    document.getElementById('presProcessBtn').classList.add('hidden');
    document.getElementById('presUploadArea').classList.remove('hidden');
    document.getElementById('presFileInput').value = '';
    resetPrescription();
}

function resetPrescription() {
    document.getElementById('presResults').classList.add('hidden');
    extractedPrescriptionText = '';
    currentPrescriptionImage = null;
    document.getElementById('presFileInput').value = '';
    document.getElementById('presImagePreview').classList.add('hidden');
    document.getElementById('presUploadArea').classList.remove('hidden');
    document.getElementById('presProcessBtn').classList.add('hidden');
}

function showPrescriptionError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    errorDiv.style.cssText = 'background:#fee2e2; color:#991b1b; border:1px solid #ef4444; padding:12px 16px; border-radius:8px; margin-bottom:16px;';
    
    const container = document.getElementById('prescription');
    container.insertBefore(errorDiv, container.firstChild);
    
    setTimeout(() => errorDiv.remove(), 5000);
}

function showPrescriptionNotification(message) {
    const notification = document.createElement('div');
    notification.className = 'pres-notification';
    notification.textContent = message;
    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 3000);
}

async function processPrescriptionImage() {
    if (!currentPrescriptionImage) return;

    const loadingState = document.getElementById('presLoadingState');
    const processBtn = document.getElementById('presProcessBtn');
    
    loadingState.classList.remove('hidden');
    processBtn.classList.add('hidden');

    try {
        // Use Tesseract.js for OCR
        const result = await Tesseract.recognize(
            currentPrescriptionImage,
            'eng',
            {
                logger: (m) => {
                    console.log(m);
                }
            }
        );

        extractedPrescriptionText = formatPrescriptionText(result.data.text);
        displayPrescriptionResults();
        
    } catch (error) {
        console.error('OCR Error:', error);
        showPrescriptionError('Failed to process image. Please try again.');
        loadingState.classList.add('hidden');
        processBtn.classList.remove('hidden');
    }
}

function formatPrescriptionText(text) {
    if (!text) return 'No text could be extracted from the image.';
    
    let formatted = text.trim();
    formatted = formatted.replace(/\s+/g, ' ');
    formatted = formatted.replace(/([.!?])\s*/g, '$1\n');
    formatted = identifyMedicationPatterns(formatted);
    
    return formatted;
}

function identifyMedicationPatterns(text) {
    const patterns = {
        dosage: /(\d+\s*(?:mg|ml|g|mcg|tablet|capsule|syrup|drop|drops))/gi,
        frequency: /(\d+\s*times?\s*(?:daily|day|week|month)|once|twice|thrice|bid|tid|qid|od|bd|tds|qds)/gi,
        duration: /(\d+\s*(?:days?|weeks?|months?|hours?))/gi,
        instructions: /(before\s+food|after\s+food|with\s+food|empty\s+stomach|morning|evening|night|bedtime)/gi
    };

    let formatted = text;
    
    formatted = formatted.replace(patterns.dosage, '💊 **$1**');
    formatted = formatted.replace(patterns.frequency, '⏰ **$1**');
    formatted = formatted.replace(patterns.duration, '📅 **$1**');
    formatted = formatted.replace(patterns.instructions, '🍽️ **$1**');
    
    const lines = formatted.split('\n').filter(line => line.trim());
    const structuredLines = lines.map(line => {
        if (patterns.dosage.test(line)) {
            return `📋 ${line}`;
        } else if (patterns.frequency.test(line)) {
            return `🕐 ${line}`;
        } else if (patterns.duration.test(line)) {
            return `📆 ${line}`;
        } else if (patterns.instructions.test(line)) {
            return `🍽️ ${line}`;
        }
        return line;
    });

    return structuredLines.join('\n\n');
}

function displayPrescriptionResults() {
    document.getElementById('presLoadingState').classList.add('hidden');
    document.getElementById('presExtractedText').textContent = extractedPrescriptionText;
    document.getElementById('presResults').classList.remove('hidden');
}

function copyPrescriptionText() {
    const textToCopy = document.getElementById('presExtractedText').textContent;
    
    navigator.clipboard.writeText(textToCopy).then(() => {
        showPrescriptionNotification('✓ Prescription text copied to clipboard!');
    }).catch(err => {
        console.error('Failed to copy text:', err);
        showPrescriptionError('Failed to copy text');
    });
}

function exportPrescriptionToPDF() {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();
    
    doc.setFontSize(20);
    doc.text('Prescription Analysis Report', 20, 20);
    
    doc.setFontSize(12);
    doc.text(`Generated: ${new Date().toLocaleString()}`, 20, 30);
    
    doc.setFontSize(14);
    doc.text('Extracted Prescription Details:', 20, 45);
    
    const textLines = doc.splitTextToSize(document.getElementById('presExtractedText').textContent, 170);
    doc.text(textLines, 20, 55);
    
    doc.setFontSize(10);
    doc.text('⚠️ This is an AI-generated analysis. Always consult with a healthcare professional.', 20, doc.internal.pageSize.height - 20);
    
    doc.save('prescription-analysis.pdf');
    
    showPrescriptionNotification('✓ PDF exported successfully!');
}

// Setup drag and drop for prescription upload
function setupPrescriptionDragDrop() {
    const uploadArea = document.getElementById('presUploadArea');
    
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    
    uploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            validateAndProcessPrescriptionFile(files[0]);
        }
    });
}

// ================== CHAT ==================
function openChat(){
    document.getElementById("chatModal").style.display="flex";
}

function closeChat(){
    document.getElementById("chatModal").style.display="none";
}

function handleKey(e){
    if(e.key==="Enter") sendMessage();
}

function formatText(text){
    return text
        ?.replace(/\.\s+/g,". ")
        ?.replace(/\?\s+/g,"? ")
        ?.replace(/\!\s+/g,"! ");
}

function addMessage(text,sender){
    const chat=document.getElementById("chat-content");

    const msg=document.createElement("div");
    msg.classList.add("message",sender);
    msg.innerText = sender==="bot" ? formatText(text) : text;

    chat.appendChild(msg);
    chat.scrollTop = chat.scrollHeight;

    return msg;
}

function sendMessage(){
    const input=document.getElementById("user-input");
    const text=input.value.trim();

    if(!text) return;

    addMessage(text,"user");
    input.value="";

    const botMsg=addMessage("Typing...","bot");

    fetch(`${API_URL}/chat`,{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({query:text})
    })
    .then(res=>res.json())
    .then(data=>{
        console.log("Chat:", data);
        botMsg.innerText = formatText(data.answer || "⚠️ No response");
    })
    .catch(()=>{
        botMsg.innerText="❌ Server Error";
    });
}

// ================== VOICE ==================
function startVoice(){
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if(!SpeechRecognition){
        alert("Voice not supported");
        return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang="en-IN";
    recognition.start();

    recognition.onresult=(e)=>{
        document.getElementById("user-input").value =
            e.results[0][0].transcript;
        sendMessage();
    };
}

// ================== SECTIONS ==================
function showSection(id){
    // Add rainbow glow effect to clicked card
    addRainbowGlow(event.target);
    
    document.querySelectorAll(".section").forEach(sec=>{
        sec.classList.remove("active");
    });
    const section=document.getElementById(id);
    if(section){
        section.classList.add("active");
    }
}

// Add rainbow glow effect to clicked element
function addRainbowGlow(element) {
    // Remove existing glow effects from all cards
    const allCards = document.querySelectorAll('.card');
    allCards.forEach(card => {
        card.classList.remove('rainbow-glow', 'active');
    });
    
    // Add glow effect to clicked card
    if (element && element.classList.contains('card')) {
        element.classList.add('rainbow-glow', 'active');
        
        // Remove effect after animation completes
        setTimeout(() => {
            element.classList.remove('rainbow-glow', 'active');
        }, 2000);
    }
}

// ================== HEALTH TIPS ==================
//     {text:"🥗 Eat more vegetables",category:"diet"},
//     {text:"🍎 Avoid junk food",category:"diet"},
//     {text:"🧘 Practice meditation",category:"mental"},
//     {text:"😌 Reduce stress",category:"mental"},
//     {text:"❤️ Regular heart checkups",category:"heart"},
//     {text:"🚭 Avoid smoking",category:"heart"},
//     {text:"🏃 Exercise daily",category:"fitness"},
//     {text:"🚶 Walk regularly",category:"fitness"}
// ];

// window.onload = ()=>{
//     displayTips(tips);
//     setupPrescriptionDragDrop();
// };

// function displayTips(data){
//     const container=document.getElementById("tips-container");
//     container.innerHTML="";

//     data.forEach(t=>{
//         const div=document.createElement("div");
//         div.classList.add("tip-item");
//         div.innerText=t.text;
//         container.appendChild(div);
//     });
// }

// function filterCategory(cat){
//     currentCategory=cat;
//     applyFilters();
// }

// function filterTips(){
//     applyFilters();
// }

// function applyFilters(){
//     const search=document.getElementById("searchTips").value.toLowerCase();

//     const filtered=tips.filter(t=>
//         (currentCategory==="all" || t.category===currentCategory) &&
//         t.text.toLowerCase().includes(search)
//     );

//     displayTips(filtered);
// }


let currentCategory = "all";

const tips = [
    {text:"💧 Drink 2-3 liters of water daily",category:"diet"},
    {text:"🥗 Eat more vegetables",category:"diet"},
    {text:"🍎 Avoid junk food",category:"diet"},
    {text:"🧘 Practice meditation",category:"mental"},
    {text:"😌 Reduce stress",category:"mental"},
    {text:"❤️ Regular heart checkups",category:"heart"},
    {text:"🚭 Avoid smoking",category:"heart"},
    {text:"🏃 Exercise daily",category:"fitness"},
    {text:"🚶 Walk regularly",category:"fitness"}
];

window.onload = () => {
    displayTips(tips);
    setupSearch(); // setup search listener
    setupCategoryButtons(); // setup category active states
};

// Display tips
function displayTips(data){
    const container = document.getElementById("tips-container");
    container.innerHTML = "";

    if(data.length === 0){
        const noResult = document.createElement("div");
        noResult.classList.add("tip-item");
        noResult.innerText = "No tips found!";
        container.appendChild(noResult);
        return;
    }

    data.forEach(t => {
        const div = document.createElement("div");
        div.classList.add("tip-item");
        div.innerText = t.text;
        container.appendChild(div);
    });
}

// Filter by category
function filterCategory(cat){
    currentCategory = cat;
    applyFilters();
}

// Setup active button highlight
function setupCategoryButtons(){
    const buttons = document.querySelectorAll('.filter-buttons button');
    buttons.forEach(btn => {
        btn.addEventListener('click', () => {
            buttons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });
}

// Search input listener
function setupSearch(){
    const searchInput = document.getElementById("searchTips");
    searchInput.addEventListener("keyup", applyFilters);
}

// Apply both search and category filters
function applyFilters(){
    const search = document.getElementById("searchTips").value.toLowerCase();

    const filtered = tips.filter(t =>
        (currentCategory === "all" || t.category === currentCategory) &&
        t.text.toLowerCase().includes(search)
    );

    displayTips(filtered);
}



// ================== DISEASE PREDICTOR ==================
function predictDisease(){
    const symptoms=document.getElementById("symptoms").value.trim();
    const resultDiv=document.getElementById("prediction-result");

    if(!symptoms){
        resultDiv.innerText="⚠️ Enter symptoms.";
        return;
    }

    resultDiv.innerText="⏳ Predicting...";

    fetch(`${API_URL}/predict`,{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({symptoms})
    })
    .then(res=>res.json())
    .then(data=>{
        console.log("Prediction:", data);

        if(data.predictions){
            let html="<h3>🩺 Possible Diseases:</h3>";

            data.predictions.forEach(p=>{
                html += `
                <b>${p.disease}</b> (${p.match_percent}% match)<br>
                Risk: ${p.risk}<br>
                Advice: ${p.advice}<br><br>
                `;
            });

            resultDiv.innerHTML = html;
        } else {
            resultDiv.innerText = data.message || "No predictions found.";
        }
    })
    .catch(()=>{
        resultDiv.innerText="❌ Server Error";
    });
}

// ================== DAILY ROUTINE ==================
function generateRoutine() {
    const wakeTime = document.getElementById("wakeTime").value.trim();
    const sleepTime = document.getElementById("sleepTime").value.trim();
    const goal = document.getElementById("goal").value.trim();
    const resultDiv = document.getElementById("routineResult");

    if (!wakeTime || !sleepTime || !goal) {
        resultDiv.innerText = "⚠️ Please fill in all fields.";
        return;
    }

    resultDiv.innerText = "⏳ Generating your routine...";

    const routine = `
<b>🌅 Morning:</b><br>
- Wake up at ${wakeTime}<br>
- Drink water and freshen up<br>
- Light exercise or stretching (15-30 mins)<br>
- Healthy breakfast<br><br>

<b>💼 Daytime:</b><br>
- Focus on your main goal: ${goal}<br>
- Take short breaks every 1-2 hours<br>
- Healthy lunch around noon<br><br>

<b>🌇 Evening:</b><br>
- Light exercise or walk<br>
- Relaxation / meditation<br>
- Hobby or leisure time<br><br>

<b>🌙 Night:</b><br>
- Dinner at least 2 hours before sleep<br>
- Plan for tomorrow<br>
- Sleep at ${sleepTime}<br>
    `;

    resultDiv.innerHTML = routine;
}

// ================== DIET PLAN ==================
function generateDietPlan() {
    const goal = document.getElementById("dietGoal").value.trim();
    const allergies = document.getElementById("dietAllergies").value.trim();
    const calories = document.getElementById("dietCalories").value.trim();
    const resultDiv = document.getElementById("dietResult");

    if (!goal) {
        resultDiv.innerText = "⚠️ Please enter your goal.";
        return;
    }

    resultDiv.innerText = "⏳ Generating AI Diet Plan...";

    let breakfast = "";
    let lunch = "";
    let dinner = "";
    
    if (goal.toLowerCase().includes("weight loss")) {
        breakfast = "Oatmeal with fruits and a cup of green tea";
        lunch = "Grilled chicken salad with veggies";
        dinner = "Steamed fish and vegetables";
    } else if (goal.toLowerCase().includes("muscle gain")) {
        breakfast = "Egg omelette with whole grain toast";
        lunch = "Chicken breast with brown rice and broccoli";
        dinner = "Salmon with quinoa and veggies";
    } else {
        breakfast = "Yogurt with nuts and berries";
        lunch = "Vegetable stir fry with tofu";
        dinner = "Grilled vegetables with lentil soup";
    }

    if (allergies) {
        breakfast += ` (avoid ${allergies})`;
        lunch += ` (avoid ${allergies})`;
        dinner += ` (avoid ${allergies})`;
    }

    if (calories) {
        breakfast += ` - approx ${Math.floor(calories*0.3)} kcal`;
        lunch += ` - approx ${Math.floor(calories*0.4)} kcal`;
        dinner += ` - approx ${Math.floor(calories*0.3)} kcal`;
    }

    const plan = `
<b>🥣 Breakfast:</b> ${breakfast}<br>
<b>🍱 Lunch:</b> ${lunch}<br>
<b>🍲 Dinner:</b> ${dinner}<br>
    `;

    resultDiv.innerHTML = plan;
}

// ================== MULTI AGENT ==================
function queryAgent(){
    const agent=document.getElementById("agentSelect").value;
    const userQuery=document.getElementById("agentQuery").value.trim();
    const resultDiv=document.getElementById("agentResponse");

    if(!userQuery){
        resultDiv.innerText="⚠️ Type something.";
        return;
    }

    resultDiv.innerText="⏳ Processing...";

    let finalQuery="";

    if(agent==="doctor"){
        finalQuery = `You are a professional medical doctor. 
        Analyze symptoms and suggest possible diseases with precautions. ${userQuery}`;
    }

    else if(agent==="lab"){
        finalQuery = `You are a medical lab analyst.
        Analyze medical reports and explain results in simple terms. ${userQuery}`;
    }

    fetch(`${API_URL}/chat`,{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({query:finalQuery})
    })
    .then(res=>res.json())
    .then(data=>{
        console.log("Agent:", data);

        if(data.answer){
            resultDiv.innerText=data.answer;
        } else {
            resultDiv.innerText="⚠️ No response.";
        }
    })
    .catch(()=>{
        resultDiv.innerText="❌ Server Error";
    });
}

// ================== FILE UPLOAD ==================
function uploadFile(input){
    const file=input.files[0];
    const resultDiv=document.getElementById("reports");

    if(!file) return;

    resultDiv.innerText="⏳ Uploading...";

    const formData=new FormData();
    formData.append("file",file);

    fetch(`${API_URL}/upload`,{
        method:"POST",
        body:formData
    })
    .then(res=>res.json())
    .then(data=>{
        console.log("Upload:", data);
        resultDiv.innerText = data.analysis || "✅ Uploaded & analyzed!";
    })
    .catch(()=>{
        resultDiv.innerText="❌ Upload failed.";
    });
}

// ================== Yoga Planner ==================
function generateYoga(){
    const goal=document.getElementById("yogaGoal").value.trim();
    const result=document.getElementById("yogaResult");

    if(!goal){
        result.innerText="⚠️ Enter goal";
        return;
    }

    result.innerHTML=`
    🧘 Morning Yoga:
    - Sun Salutation (5 rounds)
    - Pranayama (breathing)

    🌿 Meditation:
    - 10 – 15 min mindfulness

    🌙 Evening:
    - Light stretching

    🎯 Goal: ${goal}
    `;
}

// ================== Workout Generator ==================
function generateWorkout(){
    const type=document.getElementById("workoutType").value;
    const goal=document.getElementById("fitnessGoal").value.trim();
    const result=document.getElementById("workoutResult");

    if(!goal){
        result.innerText="⚠️ Enter goal";
        return;
    }

    let workout="";

    if(type==="home"){
        workout=`
        🏠 Home Workout:
        - Push-ups (3x15)
        - Squats (3x20)
        - Plank (60 sec)
        - Jump rope (5 min)
        `;
    } else {
        workout=`
        🏋️ Gym Workout:
        - Bench Press
        - Deadlift
        - Squats
        - Treadmill (10 min)
        `;
    }

    result.innerHTML = workout + `<br><br>🎯 Goal: ${goal}`;
}

// ================== Stress Relief ==================
function showStressRelief(){
    const result = document.getElementById("stressResult");
    let level = document.getElementById("stressLevel").value;

    if(!level){
        result.innerText="⚠️ Please select stress level";
        return;
    }

    let plan = "";

    if(level==="low"){
        plan = `
        😌 Low Stress Plan:<br>
        - 5 min deep breathing<br>
        - Light music 🎵<br>
        - Short walk 🚶<br>
        - Drink water 💧
        `;
    }

    else if(level==="medium"){
        plan = `
        😌 Medium Stress Plan:<br>
        - 10 min meditation 🧘<br>
        - Journaling 📓<br>
        - Reduce screen time 📵<br>
        - Talk to a friend 📞
        `;
    }

    else if(level==="high"){
        plan = `
        🚨 High Stress Plan:<br>
        - 15–20 min guided meditation 🧘<br>
        - Deep breathing (4-7-8)<br>
        - Lie down & relax 🛌<br>
        - Take a break from work
        `;
    }

    result.innerHTML = `
    ${plan}

    <br><br>⏰ Suggested Routine:<br>
    - 🌅 Morning: Breathing<br>
    - ☀️ Afternoon: Walk + break<br>
    - 🌙 Night: Meditation
    `;
}


// ================== Relax Audio ==================
function suggestAudio(){
    const result = document.getElementById("audioResult");
    let mood = document.getElementById("audioMood").value;

    if(!mood){
        result.innerText="⚠️ Please select mood";
        return;
    }

    let audio = "";

    if(mood==="stress"){
        audio = `
        🎧 Stress Relief Audio:<br>
        - Rain sounds 🌧<br>
        - Soft piano 🎹<br>
        - Forest ambience 🌳
        `;
    }

    else if(mood==="sleep"){
        audio = `
        🌙 Sleep Audio:<br>
        - Ocean waves 🌊<br>
        - White noise<br>
        - Slow ambient music
        `;
    }

    else if(mood==="focus"){
        audio = `
        🧠 Focus Audio:<br>
        - Lo-fi beats 🎧<br>
        - Alpha waves<br>
        - Instrumental music
        `;
    }

    else if(mood==="relax"){
        audio = `
        😌 Relax Audio:<br>
        - Meditation music<br>
        - Tibetan bowls<br>
        - Calm flute music
        `;
    }

    result.innerHTML = `
    ${audio}

    <br><br>🔍 Try on YouTube:<br>
    <b>${mood} meditation music</b>
    `;
}

// ================== Focus Planner ==================
function generateFocusPlan(){
    const goal = document.getElementById("focusGoal").value.trim();
    const hours = document.getElementById("focusHours").value;
    const result = document.getElementById("focusResult");

    if(!goal || !hours){
        result.innerText="⚠️ Enter goal and hours";
        return;
    }

    if(isNaN(hours) || hours <= 0){
        result.innerText="⚠️ Enter valid hours";
        return;
    }

    const totalHours = parseInt(hours);
    const sessions = Math.floor(totalHours * 2);

    let plan = `
    🎯 Goal: ${goal}<br><br>
    🧠 Total Sessions: ${sessions}<br><br>
    `;

    for(let i=1; i<=sessions; i++){
        plan += `🔹 Session ${i}: 25 min focus + 5 min break<br>`;
    }

    plan += `
    <br>🔥 Rules:<br>
    - No phone 📵<br>
    - Deep work only<br>
    - Clear tasks before starting<br>

    <br>⚡ Pro Tip:<br>
    Start with hardest task first
    `;

    result.innerHTML = plan;
}

// ================== 🏥 Hospitals ==================
function searchHospitals(){
    const location = document.getElementById("locationInput").value;
    const result = document.getElementById("hospitalResult");

    if(!location){
        result.innerText = "⚠️ Please enter location";
        return;
    }

    result.innerText = "⏳ Finding location...";

    fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${location}`)
    .then(res => res.json())
    .then(data => {
        if(data.length === 0){
            result.innerText = "❌ Location not found";
            return;
        }

        const lat = data[0].lat;
        const lng = data[0].lon;

        result.innerText = "⏳ Fetching hospitals...";

        fetch(`${API_URL}/hospitals?lat=${lat}&lng=${lng}`)
        .then(res => res.json())
        .then(data => {
            if(!data.hospitals || data.hospitals.length === 0){
                result.innerText = "❌ No hospitals found";
                return;
            }

            let html = `<h3>🏥 Hospitals in ${location}</h3>`;
            data.hospitals.forEach(h=>{
                html += `<div>🏥 ${h.name}</div>`;
            });
            result.innerHTML = html;
        });
    })
    .catch(()=>{
        result.innerText = "❌ Error fetching data";
    });
}

// ================== 👨‍⚕️ Doctor Finder ==================
function findDoctor(){
    const spec=document.getElementById("doctorSpecialty").value;
    const result=document.getElementById("doctorResult");

    if(!spec){
        result.innerText="⚠️ Enter specialty";
        return;
    }

    fetch(`${API_URL}/doctors?specialty=${spec}`)
    .then(res=>res.json())
    .then(data=>{
        let html="";
        data.forEach(d=>{
            html += `<div>👨‍⚕️ ${d.name} - ${d.specialty}</div>`;
        });
        result.innerHTML = html || "No doctors found";
    });
}

// ================== 📅 Appointment ==================
function bookAppointment(){
    const name=document.getElementById("patientName").value;
    const doctor=document.getElementById("doctorName").value;
    const date=document.getElementById("date").value;
    const result=document.getElementById("appointmentResult");

    fetch(`${API_URL}/appointment`,{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({name,doctor,date})
    })
    .then(res=>res.json())
    .then(data=>{
        result.innerText = "✅ Appointment booked!";
    });
}

// ================== 💊 Medicine ==================
function checkMedicine(){
    const name=document.getElementById("medicineName").value;
    const result=document.getElementById("medicineResult");

    if(!name){
        result.innerText="⚠️ Enter medicine";
        return;
    }

    fetch(`${API_URL}/medicine?name=${name}`)
    .then(res=>res.json())
    .then(data=>{
        if(data.available){
            result.innerHTML = `✅ Available<br>${data.info}`;
        } else {
            result.innerText = "❌ Not found";
        }
    });
}

// ================== 🚑 Ambulance ==================
function trackAmbulance(){
    const result=document.getElementById("ambulanceResult");

    fetch(`${API_URL}/ambulance`)
    .then(res=>res.json())
    .then(data=>{
        result.innerHTML = `
        ${data.status}<br>
        Distance: ${data.distance}<br>
        ETA: ${data.eta}
        `;
    });
}

// ================== ⭐ Reviews ==================
function submitReview(){
    const name=document.getElementById("hospitalName").value;
    const text=document.getElementById("reviewText").value;
    const rating=document.getElementById("rating").value;

    fetch(`${API_URL}/reviews`,{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({hospital:name,review:text,rating})
    })
    .then(()=>loadReviews());
}

function loadReviews(){
    fetch(`${API_URL}/reviews`)
    .then(res=>res.json())
    .then(data=>{
        const list=document.getElementById("reviewList");
        let html="";
        data.forEach(r=>{
            html += `<div>⭐ ${r.rating} - ${r.review}</div>`;
        });
        list.innerHTML = html;
    });
}

// ================== HEALTH TRACKER ==================
let healthChart = null;

function calculateBMI(weight, height) {
    if (!weight || !height) return null;
    const bmi = weight / ((height / 100) ** 2);
    let status = "";
    if (bmi < 18.5) status = "Underweight ⚠️";
    else if (bmi < 24.9) status = "Normal ✅";
    else if (bmi < 29.9) status = "Overweight ⚠️";
    else status = "Obese 🚨";
    return { value: bmi.toFixed(1), status };
}

function updateHealthData() {
    const heartRate = parseInt(document.getElementById("heartRate").value) || 0;
    const bloodPressure = parseInt(document.getElementById("bloodPressure").value) || 0;
    const sugarLevel = parseInt(document.getElementById("sugarLevel").value) || 0;
    const weight = parseFloat(document.getElementById("weight").value) || 0;
    const height = parseFloat(document.getElementById("height").value) || 0;
    const calories = parseInt(document.getElementById("calories").value) || 0;
    const sleepHours = parseFloat(document.getElementById("sleepHours").value) || 0;
    const steps = parseInt(document.getElementById("steps").value) || 0;

    const bmiData = calculateBMI(weight, height);

    if (bmiData) {
        document.getElementById("bmiResult").innerHTML =
            `⚖️ BMI: ${bmiData.value} (${bmiData.status})`;
    }

    const ctx = document.getElementById("healthChart").getContext("2d");

    if (healthChart) {
        healthChart.destroy();
    }

    healthChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: ["Heart Rate", "Blood Pressure", "Sugar", "Calories", "Sleep", "Steps", "BMI"],
            datasets: [{
                label: "Health Data",
                data: [heartRate, bloodPressure, sugarLevel, calories, sleepHours, steps, bmiData ? bmiData.value : 0],
                backgroundColor: ["#ef4444", "#3b82f6", "#10b981", "#f59e0b", "#6366f1", "#ec4899", "#14b8a6"],
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { y: { beginAtZero: true } },
            plugins: { legend: { display: false } }
        }
    });
}

function clearDashboard() {
    document.querySelectorAll("#health input").forEach(input => { input.value = ""; });
    document.getElementById("bmiResult").innerHTML = "";
    if (typeof healthChart !== "undefined" && healthChart) {
        healthChart.destroy();
        healthChart = null;
    }
    const canvas = document.getElementById("healthChart");
    const parent = canvas.parentNode;
    const newCanvas = document.createElement("canvas");
    newCanvas.id = "healthChart";
    parent.replaceChild(newCanvas, canvas);
}


// ================== 🔥 TOOL SWITCHER ==================
function showTool(){
    const tool = document.getElementById("toolSelect").value;
    const area = document.getElementById("toolArea");

    if(tool === "bp"){
        area.innerHTML = `
        <h3>🩸 Blood Pressure Checker</h3>
        <input id="sys" placeholder="Systolic (e.g. 120)">
        <input id="dia" placeholder="Diastolic (e.g. 80)">
        <button onclick="checkBP()">Check</button>
        <div id="bpResult"></div>`;
    }
    else if(tool === "sugar"){
        area.innerHTML = `
        <h3>🍬 Blood Sugar Checker</h3>
        <input id="sugarVal" placeholder="mg/dL">
        <button onclick="checkSugar()">Check</button>
        <div id="sugarResult"></div>`;
    }
    else if(tool === "bmi"){
        area.innerHTML = `
        <h3>⚖️ BMI Calculator</h3>
        <input id="bmiWeight" placeholder="Weight (kg)">
        <input id="bmiHeight" placeholder="Height (cm)">
        <button onclick="calcBMI()">Calculate</button>
        <div id="bmiCalcResult"></div>`;
    }
    else if(tool === "pediatric"){
        area.innerHTML = `
        <h3>👶 Pediatric Dosage</h3>
        <input id="childWeight" placeholder="Weight (kg)">
        <input id="dosePerKg" placeholder="Dose per kg (mg)">
        <button onclick="calcDose()">Calculate</button>
        <div id="doseResult"></div>`;
    }
    else if(tool === "ovulation"){
        area.innerHTML = `
        <h3>🌸 Ovulation Calculator</h3>
        <input id="cycleLength" placeholder="Cycle Length (days)">
        <input id="lastPeriod" type="date">
        <button onclick="calcOvulation()">Calculate</button>
        <div id="ovulationResult"></div>`;
    }
    else if(tool === "drug"){
        area.innerHTML = `
        <h3>💊 Drug Interaction Checker</h3>
        <input id="drug1" placeholder="Drug 1">
        <input id="drug2" placeholder="Drug 2">
        <button onclick="checkDrug()">Check</button>
        <div id="drugResult"></div>`;
    }
}

function checkBP(){
    const sys = parseInt(document.getElementById("sys").value);
    const dia = parseInt(document.getElementById("dia").value);
    const result = document.getElementById("bpResult");
    if(!sys || !dia){
        result.innerText="⚠️ Enter values";
        return;
    }
    let status="";
    if(sys < 120 && dia < 80) status="Normal ✅";
    else if(sys < 130) status="Elevated ⚠️";
    else if(sys < 140) status="High BP Stage 1 ⚠️";
    else status="High BP Stage 2 🚨";
    result.innerText = `Result: ${status}`;
}

function checkSugar(){
    const val = parseInt(document.getElementById("sugarVal").value);
    const result = document.getElementById("sugarResult");
    if(!val){
        result.innerText="⚠️ Enter value";
        return;
    }
    let status="";
    if(val < 70) status="Low ⚠️";
    else if(val <= 140) status="Normal ✅";
    else if(val <= 199) status="Prediabetes ⚠️";
    else status="Diabetes 🚨";
    result.innerText = `Status: ${status}`;
}

function calcBMI(){
    const w = parseFloat(document.getElementById("bmiWeight").value);
    const h = parseFloat(document.getElementById("bmiHeight").value);
    const result = document.getElementById("bmiCalcResult");
    if(!w || !h){
        result.innerText="⚠️ Enter values";
        return;
    }
    const bmi = w / ((h/100)**2);
    let status="";
    if(bmi<18.5) status="Underweight";
    else if(bmi<24.9) status="Normal";
    else if(bmi<29.9) status="Overweight";
    else status="Obese";
    result.innerText = `BMI: ${bmi.toFixed(1)} (${status})`;
}

function calcDose(){
    const weight = parseFloat(document.getElementById("childWeight").value);
    const dose = parseFloat(document.getElementById("dosePerKg").value);
    const result = document.getElementById("doseResult");
    if(!weight || !dose){
        result.innerText="⚠️ Enter values";
        return;
    }
    const total = weight * dose;
    result.innerText = `Recommended Dose: ${total} mg`;
}

function calcOvulation(){
    const cycle = parseInt(document.getElementById("cycleLength").value);
    const last = document.getElementById("lastPeriod").value;
    const result = document.getElementById("ovulationResult");
    if(!cycle || !last){
        result.innerText="⚠️ Enter values";
        return;
    }
    const date = new Date(last);
    date.setDate(date.getDate() + (cycle - 14));
    result.innerText = `Ovulation Date: ${date.toDateString()}`;
}

function checkDrug(){
    const d1 = document.getElementById("drug1").value.toLowerCase();
    const d2 = document.getElementById("drug2").value.toLowerCase();
    const result = document.getElementById("drugResult");
    if(!d1 || !d2){
        result.innerText="⚠️ Enter both drugs";
        return;
    }
    if(d1 === d2){
        result.innerText="⚠️ Same medicine entered";
        return;
    }
    if((d1.includes("aspirin") && d2.includes("ibuprofen"))){
        result.innerText="⚠️ Risk: Increased bleeding risk";
    } else {
        result.innerText="✅ No major interaction found (basic check)";
    }
}





// ================== MEDICINE ENCYCLOPEDIA FUNCTIONS ==================

let currentMedicineData = null;

function setMedicineAndSearch(medicineName) {
    document.getElementById('medicineSearchInput').value = medicineName;
    searchMedicineInfo();
}

async function searchMedicineInfo() {
    const medicineName = document.getElementById('medicineSearchInput').value.trim();
    
    if (!medicineName) {
        showNotification('⚠️ Please enter a medicine name to search', 'warning');
        return;
    }
    
    // Show loading, hide results and no results
    document.getElementById('medicineLoadingState').classList.remove('hidden');
    document.getElementById('medicineInfoResults').classList.add('hidden');
    document.getElementById('medicineNoResults').classList.add('hidden');
    
    try {
        const response = await fetch(`${API_URL}/medicine-info?name=${encodeURIComponent(medicineName)}`);
        
        if (!response.ok) {
            throw new Error('Medicine not found');
        }
        
        const data = await response.json();
        
        if (data.error || !data.uses || data.uses === "No information available") {
            showNoResults(medicineName);
        } else {
            displayMedicineInfo(data);
        }
        
    } catch (error) {
        console.error('Medicine search error:', error);
        showNoResults(medicineName);
    } finally {
        document.getElementById('medicineLoadingState').classList.add('hidden');
    }
}

function displayMedicineInfo(data) {
    currentMedicineData = data;
    
    // Update header
    document.getElementById('medicineNameDisplay').textContent = data.name || 'Unknown Medicine';
    const badge = document.getElementById('medicineTypeBadge');
    badge.textContent = data.type || 'Prescription Medicine';
    
    // Set badge color based on type
    if (data.type === 'OTC' || data.type === 'OTC (Over The Counter)') {
        badge.style.background = '#d1fae5';
        badge.style.color = '#065f46';
    } else if (data.type === 'Prescription' || data.type === 'Prescription Antibiotic' || data.type === 'Prescription Medication') {
        badge.style.background = '#dbeafe';
        badge.style.color = '#1e40af';
    } else if (data.type === 'Controlled Substance' || data.type.includes('Schedule')) {
        badge.style.background = '#fee2e2';
        badge.style.color = '#991b1b';
    } else {
        badge.style.background = '#fef3c7';
        badge.style.color = '#92400e';
    }
    
    // Update all fields with formatted text
    document.getElementById('medUses').innerHTML = formatMedicineText(data.uses);
    document.getElementById('medDosage').innerHTML = formatMedicineText(data.dosage);
    document.getElementById('medSideEffects').innerHTML = formatMedicineText(data.side_effects);
    document.getElementById('medWarnings').innerHTML = formatMedicineText(data.warnings);
    document.getElementById('medPregnancy').innerHTML = formatMedicineText(data.pregnancy_safety);
    document.getElementById('medFoodRestrictions').innerHTML = formatMedicineText(data.food_restrictions);
    document.getElementById('medAlternatives').innerHTML = formatMedicineText(data.alternatives);
    document.getElementById('medAdditional').innerHTML = formatMedicineText(data.additional_info);
    
    // Show results
    document.getElementById('medicineInfoResults').classList.remove('hidden');
    
    // Smooth scroll to results
    document.getElementById('medicineInfoResults').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function formatMedicineText(text) {
    if (!text || text === '-' || text === 'No information available') {
        return '<span style="color: #9ca3af;">No information available</span>';
    }
    
    // Convert bullet points to HTML list
    if (text.includes('•') || text.includes('-')) {
        let lines = text.split('\n');
        let formatted = '';
        let inList = false;
        
        for (let line of lines) {
            line = line.trim();
            if (!line) continue;
            
            if (line.startsWith('•') || line.startsWith('-')) {
                if (!inList) {
                    formatted += '<ul style="margin: 5px 0 5px 20px; padding: 0;">';
                    inList = true;
                }
                formatted += `<li>${line.substring(1).trim()}</li>`;
            } else {
                if (inList) {
                    formatted += '</ul>';
                    inList = false;
                }
                if (line.includes('⚠️')) {
                    formatted += `<div style="margin-top: 8px; color: #dc2626;">${line}</div>`;
                } else {
                    formatted += `<div style="margin-top: 8px;">${line}</div>`;
                }
            }
        }
        
        if (inList) {
            formatted += '</ul>';
        }
        
        return formatted || text;
    }
    
    // Handle line breaks
    if (text.includes('\n')) {
        return text.split('\n').map(line => line.trim()).filter(line => line).join('<br>');
    }
    
    return text;
}

function showNoResults(medicineName) {
    document.getElementById('searchedMedicine').textContent = medicineName;
    document.getElementById('medicineNoResults').classList.remove('hidden');
    document.getElementById('medicineInfoResults').classList.add('hidden');
}

function clearMedicineSearch() {
    document.getElementById('medicineSearchInput').value = '';
    document.getElementById('medicineNoResults').classList.add('hidden');
    document.getElementById('medicineInfoResults').classList.add('hidden');
    document.getElementById('medicineSearchInput').focus();
}

function copyMedicineInfo() {
    if (!currentMedicineData) return;
    
    let copyText = `🏥 MEDICINE INFORMATION - ${currentMedicineData.name}\n`;
    copyText += `${'='.repeat(60)}\n\n`;
    copyText += `📋 TYPE: ${currentMedicineData.type || 'N/A'}\n\n`;
    copyText += `💊 USES:\n${formatPlainText(currentMedicineData.uses)}\n\n`;
    copyText += `⚕️ DOSAGE:\n${formatPlainText(currentMedicineData.dosage)}\n\n`;
    copyText += `⚠️ SIDE EFFECTS:\n${formatPlainText(currentMedicineData.side_effects)}\n\n`;
    copyText += `🚨 WARNINGS:\n${formatPlainText(currentMedicineData.warnings)}\n\n`;
    copyText += `🤰 PREGNANCY:\n${formatPlainText(currentMedicineData.pregnancy_safety)}\n\n`;
    copyText += `🍽️ FOOD RESTRICTIONS:\n${formatPlainText(currentMedicineData.food_restrictions)}\n\n`;
    copyText += `🔄 ALTERNATIVES:\n${formatPlainText(currentMedicineData.alternatives)}\n\n`;
    copyText += `📋 ADDITIONAL INFO:\n${formatPlainText(currentMedicineData.additional_info)}\n\n`;
    copyText += `${'='.repeat(60)}\n`;
    copyText += `⚠️ This information is for educational purposes only. Always consult a healthcare professional.`;
    
    navigator.clipboard.writeText(copyText).then(() => {
        showNotification('✓ Medicine information copied to clipboard!', 'success');
    }).catch(() => {
        showNotification('Failed to copy text', 'error');
    });
}

function formatPlainText(text) {
    if (!text || text === '-') return 'No information available';
    return text.replace(/[•-]/g, '•').replace(/<br>/g, '\n').replace(/<[^>]*>/g, '');
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `pres-notification ${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: ${type === 'success' ? '#10b981' : type === 'warning' ? '#f59e0b' : '#3b82f6'};
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 1000;
        animation: slideInRight 0.3s ease;
    `;
    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 3000);
}

// Update medicine count on page load
window.addEventListener('DOMContentLoaded', function() {
    fetch(`${API_URL}/medicine-count`)
        .then(res => res.json())
        .then(data => {
            if (data.count) {
                document.getElementById('medicineCount').textContent = data.count;
            }
        })
        .catch(() => {
            document.getElementById('medicineCount').textContent = '50';
        });
});



// ================== GENERIC MEDICINE FINDER FUNCTIONS ==================

let currentGenericData = null;

function setGenericAndSearch(medicineName) {
    document.getElementById('genericSearchInput').value = medicineName;
    searchGenericMedicine();
}

async function searchGenericMedicine() {
    const medicineName = document.getElementById('genericSearchInput').value.trim();
    
    if (!medicineName) {
        showNotification('⚠️ Please enter a medicine name to search', 'warning');
        return;
    }
    
    // Show loading, hide results and no results
    document.getElementById('genericLoadingState').classList.remove('hidden');
    document.getElementById('genericResults').classList.add('hidden');
    document.getElementById('genericNoResults').classList.add('hidden');
    
    try {
        const response = await fetch(`${API_URL}/generic-finder?name=${encodeURIComponent(medicineName)}`);
        
        if (!response.ok) {
            throw new Error('Medicine not found');
        }
        
        const data = await response.json();
        
        if (data.error || !data.generic_name) {
            showGenericNoResults(medicineName);
        } else {
            displayGenericInfo(data);
        }
        
    } catch (error) {
        console.error('Generic search error:', error);
        showGenericNoResults(medicineName);
    } finally {
        document.getElementById('genericLoadingState').classList.add('hidden');
    }
}

function displayGenericInfo(data) {
    currentGenericData = data;
    
    // Update header
    document.getElementById('brandNameDisplay').textContent = data.brand_name || 'Unknown Brand';
    document.getElementById('compositionDisplay').textContent = data.composition || 'Active Ingredient';
    
    // Update prices
    document.getElementById('brandPrice').innerHTML = `₹ ${data.brand_price.toFixed(2)}`;
    document.getElementById('brandDetail').textContent = data.brand_detail || 'per strip';
    document.getElementById('genericPrice').innerHTML = `₹ ${data.generic_price.toFixed(2)}`;
    document.getElementById('genericDetail').textContent = data.generic_detail || 'per strip';
    
    // Calculate savings
    const savings = (data.brand_price - data.generic_price);
    const savingsPercent = ((savings / data.brand_price) * 100).toFixed(1);
    document.getElementById('savingsAmount').innerHTML = `₹ ${savings.toFixed(2)}`;
    document.getElementById('savingsPercent').innerHTML = `${savingsPercent}%`;
    
    // Update savings badge text
    document.getElementById('savingsBadge').innerHTML = `<i class="fas fa-tag"></i> Save ${savingsPercent}%`;
    
    // Update generic info
    document.getElementById('genericName').textContent = data.generic_name;
    document.getElementById('genericComposition').innerHTML = data.composition_detail || data.composition;
    document.getElementById('genericManufacturers').innerHTML = data.manufacturers || 'Multiple generic manufacturers available';
    document.getElementById('genericAvailability').innerHTML = data.availability || 'Available at Jan Aushadhi Kendras, generic pharmacies, and online stores';
    document.getElementById('genericWhy').innerHTML = data.why_generic || 'Same active ingredient, same quality, same effectiveness, but much lower price because no brand marketing costs.';
    document.getElementById('genericQuality').innerHTML = data.quality_assurance || 'All generic medicines are approved by CDSCO (Indian drug regulator) and meet the same quality standards as brand-name medicines.';
    
    // Show results
    document.getElementById('genericResults').classList.remove('hidden');
    
    // Smooth scroll to results
    document.getElementById('genericResults').scrollIntoView({ behavior: 'smooth', block: 'start' });
    
    // Update statistics
    updateGenericStats();
}

async function updateGenericStats() {
    try {
        const response = await fetch(`${API_URL}/generic-statistics`);
        const data = await response.json();
        if (data.total_generics_available) {
            document.getElementById('genericCount').textContent = data.total_generics_available;
            document.getElementById('avgSavings').textContent = data.average_savings_percent + '%';
        }
    } catch (error) {
        console.error('Error fetching stats:', error);
    }
}

function showGenericNoResults(medicineName) {
    document.getElementById('searchedGeneric').textContent = medicineName;
    document.getElementById('genericNoResults').classList.remove('hidden');
    document.getElementById('genericResults').classList.add('hidden');
}

function clearGenericSearch() {
    document.getElementById('genericSearchInput').value = '';
    document.getElementById('genericNoResults').classList.add('hidden');
    document.getElementById('genericResults').classList.add('hidden');
    document.getElementById('genericSearchInput').focus();
}

function shareGenericInfo() {
    if (!currentGenericData) return;
    
    const savings = (currentGenericData.brand_price - currentGenericData.generic_price);
    const savingsPercent = ((savings / currentGenericData.brand_price) * 100).toFixed(1);
    
    const shareText = `💰 Medicine Savings Alert! 💰\n\n` +
        `Brand: ${currentGenericData.brand_name} - ₹${currentGenericData.brand_price.toFixed(2)}\n` +
        `Generic: ${currentGenericData.generic_name} - ₹${currentGenericData.generic_price.toFixed(2)}\n` +
        `You Save: ₹${savings.toFixed(2)} (${savingsPercent}%)\n\n` +
        `Same quality, much lower price! Ask your doctor or pharmacist for generics.\n` +
        `#GenericMedicine #SaveMoney #JanAushadhi #PradhanMantriJanAushadhi`;
    
    if (navigator.share) {
        navigator.share({
            title: 'Generic Medicine Savings',
            text: shareText
        }).catch(() => {
            copyToClipboard(shareText);
            showNotification('✓ Information copied to clipboard!', 'success');
        });
    } else {
        copyToClipboard(shareText);
        showNotification('✓ Information copied to clipboard! Share with friends and family!', 'success');
    }
}

function generatePrescriptionNote() {
    if (!currentGenericData) return;
    
    const savings = (currentGenericData.brand_price - currentGenericData.generic_price);
    const savingsPercent = ((savings / currentGenericData.brand_price) * 100).toFixed(1);
    
    const note = `PRESCRIPTION NOTE FOR DOCTOR\n` +
        `=================================\n\n` +
        `Patient Request: Please consider prescribing generic ${currentGenericData.generic_name} instead of brand ${currentGenericData.brand_name}\n\n` +
        `Reason: Generic version costs ₹${currentGenericData.generic_price.toFixed(2)} vs ₹${currentGenericData.brand_price.toFixed(2)} (Save ${savingsPercent}%)\n\n` +
        `Same active ingredient: ${currentGenericData.composition}\n\n` +
        `Quality: CDSCO approved, same quality standards\n\n` +
        `Annual savings potential: ₹${(savings * 12).toFixed(2)} per year if taken monthly\n\n` +
        `Request: Please prescribe generic version to help reduce medicine costs.`;
    
    copyToClipboard(note);
    showNotification('✓ Prescription note copied! Share with your doctor.', 'success');
}

function copyGenericInfo() {
    if (!currentGenericData) return;
    
    const savings = (currentGenericData.brand_price - currentGenericData.generic_price);
    const savingsPercent = ((savings / currentGenericData.brand_price) * 100).toFixed(1);
    
    const copyText = `🏥 GENERIC MEDICINE INFORMATION\n` +
        `${'='.repeat(50)}\n\n` +
        `Brand Name: ${currentGenericData.brand_name}\n` +
        `Generic Name: ${currentGenericData.generic_name}\n` +
        `Composition: ${currentGenericData.composition}\n\n` +
        `💰 PRICE COMPARISON:\n` +
        `• Brand Price: ₹${currentGenericData.brand_price.toFixed(2)} ${currentGenericData.brand_detail}\n` +
        `• Generic Price: ₹${currentGenericData.generic_price.toFixed(2)} ${currentGenericData.generic_detail}\n` +
        `• You Save: ₹${savings.toFixed(2)} (${savingsPercent}%)\n\n` +
        `🏭 Manufacturers: ${currentGenericData.manufacturers}\n` +
        `📍 Available at: ${currentGenericData.availability}\n\n` +
        `ℹ️ Why Generic: ${currentGenericData.why_generic}\n\n` +
        `✅ Quality Assurance: ${currentGenericData.quality_assurance}\n\n` +
        `${'='.repeat(50)}\n` +
        `Always consult your doctor before switching medications.`;
    
    copyToClipboard(copyText);
    showNotification('✓ Generic medicine information copied!', 'success');
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        console.log('Copied to clipboard');
    }).catch(err => {
        console.error('Failed to copy:', err);
    });
}

// Load generic statistics on page load
document.addEventListener('DOMContentLoaded', function() {
    updateGenericStats();
});



// ================== FOOD & MEDICINE INTERACTION FUNCTIONS ==================

let currentInteractionData = null;

function setInteractionAndSearch(medicineName) {
    document.getElementById('medicineInteractionInput').value = medicineName;
    searchFoodInteraction();
}

async function searchFoodInteraction() {
    const medicineName = document.getElementById('medicineInteractionInput').value.trim();
    
    if (!medicineName) {
        showNotification('⚠️ Please enter a medicine name to check interactions', 'warning');
        return;
    }
    
    // Show loading, hide results and no results
    document.getElementById('interactionLoadingState').classList.remove('hidden');
    document.getElementById('interactionResults').classList.add('hidden');
    document.getElementById('interactionNoResults').classList.add('hidden');
    
    try {
        const response = await fetch(`${API_URL}/food-interaction?name=${encodeURIComponent(medicineName)}`);
        
        if (!response.ok) {
            throw new Error('Medicine not found');
        }
        
        const data = await response.json();
        
        if (data.error || !data.medicine_name) {
            showInteractionNoResults(medicineName);
        } else {
            displayInteractionInfo(data);
        }
        
    } catch (error) {
        console.error('Interaction search error:', error);
        showInteractionNoResults(medicineName);
    } finally {
        document.getElementById('interactionLoadingState').classList.add('hidden');
    }
}

function displayInteractionInfo(data) {
    currentInteractionData = data;
    
    // Update header
    document.getElementById('interactionMedicineName').textContent = data.medicine_name;
    document.getElementById('interactionCategory').textContent = data.category || 'Medication';
    
    // Update severity badge based on overall risk
    const severityBadge = document.getElementById('severityBadge');
    if (data.overall_risk === 'HIGH') {
        severityBadge.style.background = '#dc2626';
        severityBadge.innerHTML = '<i class="fas fa-exclamation-triangle"></i> HIGH RISK - Multiple Interactions';
    } else if (data.overall_risk === 'MODERATE') {
        severityBadge.style.background = '#f59e0b';
        severityBadge.innerHTML = '<i class="fas fa-shield-alt"></i> MODERATE RISK - Caution Advised';
    } else {
        severityBadge.style.background = '#10b981';
        severityBadge.innerHTML = '<i class="fas fa-check-circle"></i> LOW RISK - Standard Precautions';
    }
    
    // Update critical warnings
    const criticalList = document.getElementById('criticalList');
    if (data.critical_warnings && data.critical_warnings.length > 0) {
        criticalList.innerHTML = data.critical_warnings.map(warning => `
            <div class="interaction-item">
                <i class="fas ${warning.icon || 'fa-exclamation-circle'}"></i>
                <span>${warning.text}</span>
            </div>
        `).join('');
        document.getElementById('criticalWarnings').classList.remove('hidden');
    } else {
        document.getElementById('criticalWarnings').classList.add('hidden');
    }
    
    // Update interaction cards
    document.getElementById('alcoholInteraction').innerHTML = data.alcohol || 'No specific interaction reported';
    document.getElementById('grapefruitInteraction').innerHTML = data.grapefruit || 'No specific interaction reported';
    document.getElementById('dairyInteraction').innerHTML = data.dairy || 'No specific interaction reported';
    document.getElementById('caffeineInteraction').innerHTML = data.caffeine || 'No specific interaction reported';
    document.getElementById('potassiumInteraction').innerHTML = data.potassium_foods || 'No specific restriction';
    document.getElementById('vitaminKInteraction').innerHTML = data.vitamin_k_foods || 'No specific restriction';
    
    // Update timing advice
    document.getElementById('timingAdvice').innerHTML = data.timing_advice || 'Take as prescribed by your doctor. Follow specific instructions on your prescription.';
    
    // Update additional advice
    document.getElementById('additionalAdvice').innerHTML = data.additional_advice || 'Always consult your healthcare provider for personalized advice about food and drug interactions.';
    
    // Show results
    document.getElementById('interactionResults').classList.remove('hidden');
    
    // Smooth scroll to results
    document.getElementById('interactionResults').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function showInteractionNoResults(medicineName) {
    document.getElementById('searchedInteractionMedicine').textContent = medicineName;
    document.getElementById('interactionNoResults').classList.remove('hidden');
    document.getElementById('interactionResults').classList.add('hidden');
}

function clearInteractionSearch() {
    document.getElementById('medicineInteractionInput').value = '';
    document.getElementById('interactionNoResults').classList.add('hidden');
    document.getElementById('interactionResults').classList.add('hidden');
    document.getElementById('medicineInteractionInput').focus();
}

function shareInteractionInfo() {
    if (!currentInteractionData) return;
    
    let shareText = `🍊 FOOD & MEDICINE INTERACTION ALERT 🍊\n\n`;
    shareText += `Medicine: ${currentInteractionData.medicine_name}\n`;
    shareText += `Category: ${currentInteractionData.category}\n\n`;
    shareText += `⚠️ CRITICAL AVOID:\n`;
    
    if (currentInteractionData.alcohol && currentInteractionData.alcohol !== 'No specific interaction reported') {
        shareText += `• Alcohol: ${currentInteractionData.alcohol}\n`;
    }
    if (currentInteractionData.grapefruit && currentInteractionData.grapefruit !== 'No specific interaction reported') {
        shareText += `• Grapefruit: ${currentInteractionData.grapefruit}\n`;
    }
    if (currentInteractionData.dairy && currentInteractionData.dairy !== 'No specific interaction reported') {
        shareText += `• Dairy: ${currentInteractionData.dairy}\n`;
    }
    if (currentInteractionData.caffeine && currentInteractionData.caffeine !== 'No specific interaction reported') {
        shareText += `• Caffeine: ${currentInteractionData.caffeine}\n`;
    }
    
    shareText += `\n⏰ When to take: ${currentInteractionData.timing_advice}\n\n`;
    shareText += `Always consult your doctor about food-drug interactions! #MedicineSafety #FoodInteraction`;
    
    if (navigator.share) {
        navigator.share({
            title: `Food Interactions for ${currentInteractionData.medicine_name}`,
            text: shareText
        }).catch(() => {
            copyToClipboard(shareText);
            showNotification('✓ Information copied to clipboard!', 'success');
        });
    } else {
        copyToClipboard(shareText);
        showNotification('✓ Information copied to clipboard! Share with others!', 'success');
    }
}

function printInteractionInfo() {
    if (!currentInteractionData) return;
    
    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>Food & Medicine Interaction - ${currentInteractionData.medicine_name}</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 40px; max-width: 800px; margin: 0 auto; }
                h1 { color: #1e293b; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }
                h2 { color: #334155; margin-top: 20px; }
                .warning { background: #fef2f2; border-left: 4px solid #dc2626; padding: 15px; margin: 15px 0; }
                .info { background: #f0fdf4; border-left: 4px solid #22c55e; padding: 15px; margin: 15px 0; }
                .interaction { margin: 10px 0; padding: 10px; background: #f8fafc; border-radius: 8px; }
                .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #64748b; text-align: center; }
                @media print {
                    body { padding: 20px; }
                    .no-print { display: none; }
                }
            </style>
        </head>
        <body>
            <h1>🍊 Food & Medicine Interaction Report</h1>
            <h2>${currentInteractionData.medicine_name}</h2>
            <p><strong>Category:</strong> ${currentInteractionData.category}</p>
            
            <div class="warning">
                <h3>⚠️ Critical Interactions - AVOID</h3>
                ${currentInteractionData.alcohol && currentInteractionData.alcohol !== 'No specific interaction reported' ? `<div class="interaction"><strong>🍷 Alcohol:</strong> ${currentInteractionData.alcohol}</div>` : ''}
                ${currentInteractionData.grapefruit && currentInteractionData.grapefruit !== 'No specific interaction reported' ? `<div class="interaction"><strong>🍊 Grapefruit:</strong> ${currentInteractionData.grapefruit}</div>` : ''}
                ${currentInteractionData.dairy && currentInteractionData.dairy !== 'No specific interaction reported' ? `<div class="interaction"><strong>🥛 Dairy:</strong> ${currentInteractionData.dairy}</div>` : ''}
                ${currentInteractionData.caffeine && currentInteractionData.caffeine !== 'No specific interaction reported' ? `<div class="interaction"><strong>☕ Caffeine:</strong> ${currentInteractionData.caffeine}</div>` : ''}
            </div>
            
            <div class="info">
                <h3>⏰ When to Take</h3>
                <p>${currentInteractionData.timing_advice}</p>
            </div>
            
            <div class="info">
                <h3>📋 Additional Information</h3>
                <p>${currentInteractionData.additional_advice}</p>
            </div>
            
            <div class="footer">
                <p>This information is for educational purposes only. Always consult your healthcare provider.</p>
                <p>Generated on: ${new Date().toLocaleString()}</p>
            </div>
        </body>
        </html>
    `);
    printWindow.document.close();
    printWindow.print();
}

function copyInteractionInfo() {
    if (!currentInteractionData) return;
    
    let copyText = `🍊 FOOD & MEDICINE INTERACTION REPORT\n`;
    copyText += `${'='.repeat(60)}\n\n`;
    copyText += `Medicine: ${currentInteractionData.medicine_name}\n`;
    copyText += `Category: ${currentInteractionData.category}\n\n`;
    
    copyText += `⚠️ CRITICAL INTERACTIONS - AVOID:\n`;
    copyText += `• Alcohol: ${currentInteractionData.alcohol}\n`;
    copyText += `• Grapefruit: ${currentInteractionData.grapefruit}\n`;
    copyText += `• Dairy: ${currentInteractionData.dairy}\n`;
    copyText += `• Caffeine: ${currentInteractionData.caffeine}\n`;
    copyText += `• High Potassium Foods: ${currentInteractionData.potassium_foods}\n`;
    copyText += `• Vitamin K Rich Foods: ${currentInteractionData.vitamin_k_foods}\n\n`;
    
    copyText += `⏰ WHEN TO TAKE:\n${currentInteractionData.timing_advice}\n\n`;
    copyText += `📋 ADDITIONAL ADVICE:\n${currentInteractionData.additional_advice}\n\n`;
    copyText += `${'='.repeat(60)}\n`;
    copyText += `Always consult your doctor or pharmacist about food-drug interactions.`;
    
    copyToClipboard(copyText);
    showNotification('✓ Interaction information copied to clipboard!', 'success');
}


// ================== PHARMACY FINDER FUNCTIONS ==================

// ================== PHARMACY FINDER FUNCTIONS ==================

let userLat = null;
let userLng = null;
let allPharmacies = [];
let currentLocationName = "";
let isClearing = false;

// OpenStreetMap Nominatim API for geocoding
const NOMINATIM_URL = "https://nominatim.openstreetmap.org/search";

// Overpass API for pharmacy search
const OVERPASS_URL = "https://overpass-api.de/api/interpreter";

function getUserLocation() {
    if (navigator.geolocation) {
        document.getElementById('pharmacyLoadingState').classList.remove('hidden');
        document.getElementById('locationPermissionCard').classList.add('hidden');
        document.getElementById('citySearchCard').classList.add('hidden');
        
        navigator.geolocation.getCurrentPosition(
            (position) => {
                userLat = position.coords.latitude;
                userLng = position.coords.longitude;
                getLocationName(userLat, userLng);
                searchNearbyPharmacies();
            },
            (error) => {
                document.getElementById('pharmacyLoadingState').classList.add('hidden');
                let errorMsg = "Unable to get your location. ";
                if (error.code === 1) errorMsg += "Please enable location services.";
                else if (error.code === 2) errorMsg += "Location unavailable. Try again.";
                else errorMsg += "Please search by city instead.";
                alert(errorMsg);
                document.getElementById('locationPermissionCard').classList.remove('hidden');
            }
        );
    } else {
        alert("Geolocation is not supported by your browser. Please search by city.");
        document.getElementById('locationPermissionCard').classList.add('hidden');
        document.getElementById('citySearchCard').classList.remove('hidden');
    }
}

function getLocationName(lat, lng) {
    fetch(`${NOMINATIM_URL}?format=json&lat=${lat}&lon=${lng}&zoom=10`)
        .then(res => res.json())
        .then(data => {
            if (data && data[0]) {
                currentLocationName = data[0].display_name.split(',')[0];
                document.getElementById('currentLocationDisplay').innerHTML = `<i class="fas fa-map-marker-alt"></i> ${currentLocationName}`;
            }
        })
        .catch(err => console.error("Error getting location name:", err));
}

function clearAndStartFresh() {
    if (isClearing) return;
    isClearing = true;
    
    // Show confirmation toast
    showClearToast();
    
    // Clear all data
    allPharmacies = [];
    userLat = null;
    userLng = null;
    currentLocationName = "";
    
    // Reset filters to default
    document.getElementById('filterOpenNow').value = 'all';
    document.getElementById('distanceSlider').value = '5';
    document.getElementById('distanceValue').innerText = '5';
    
    // Hide all result sections
    document.getElementById('pharmacyResults').classList.add('hidden');
    document.getElementById('pharmacyFilters').classList.add('hidden');
    document.getElementById('locationInfoBar').classList.add('hidden');
    document.getElementById('pharmacyNoResults').classList.add('hidden');
    
    // Clear the grid
    document.getElementById('pharmacyGrid').innerHTML = '';
    
    // Reset location permission card
    document.getElementById('locationPermissionCard').classList.remove('hidden');
    document.getElementById('citySearchCard').classList.add('hidden');
    document.getElementById('pharmacyLoadingState').classList.add('hidden');
    
    // Clear search input if any
    document.getElementById('citySearchInput').value = '';
    document.getElementById('medicineInteractionInput').value = '';
    
    isClearing = false;
}

function showClearToast() {
    const toast = document.createElement('div');
    toast.className = 'clear-toast';
    toast.innerHTML = '<i class="fas fa-check-circle"></i> All data cleared! Start fresh by sharing your location.';
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

function updateDistanceValue() {
    const slider = document.getElementById('distanceSlider');
    const value = parseFloat(slider.value);
    document.getElementById('distanceValue').innerText = value;
    filterPharmacies();
}

async function searchNearbyPharmacies() {
    if (!userLat || !userLng) return;
    
    try {
        // Overpass API query for pharmacies within 20km
        const query = `
            [out:json];
            (
                node["amenity"="pharmacy"](around:20000,${userLat},${userLng});
                way["amenity"="pharmacy"](around:20000,${userLat},${userLng});
                relation["amenity"="pharmacy"](around:20000,${userLat},${userLng});
            );
            out body;
            >;
            out skel qt;
        `;
        
        const response = await fetch(OVERPASS_URL, {
            method: 'POST',
            body: query
        });
        
        const data = await response.json();
        
        if (data.elements && data.elements.length > 0) {
            allPharmacies = processPharmacies(data.elements);
            // Sort by distance (nearest first)
            allPharmacies.sort((a, b) => a.distance - b.distance);
            displayPharmacies(allPharmacies);
        } else {
            // Fallback to mock data if Overpass returns nothing
            allPharmacies = getMockPharmacies();
            allPharmacies.sort((a, b) => a.distance - b.distance);
            displayPharmacies(allPharmacies);
        }
        
        // Show location info bar
        document.getElementById('locationInfoBar').classList.remove('hidden');
        
    } catch (error) {
        console.error("Error fetching pharmacies:", error);
        // Fallback to mock data
        allPharmacies = getMockPharmacies();
        allPharmacies.sort((a, b) => a.distance - b.distance);
        displayPharmacies(allPharmacies);
        document.getElementById('locationInfoBar').classList.remove('hidden');
    }
}

function processPharmacies(elements) {
    const pharmacies = [];
    const processedIds = new Set();
    
    for (const element of elements) {
        if (processedIds.has(element.id)) continue;
        processedIds.add(element.id);
        
        const tags = element.tags || {};
        
        // Calculate distance
        const distance = calculateDistance(
            userLat, userLng,
            element.lat || element.center?.lat,
            element.lon || element.center?.lon
        );
        
        // Determine status
        let status = "unknown";
        let statusText = "Unknown";
        let statusClass = "";
        
        if (tags['opening_hours']) {
            if (tags['opening_hours'] === '24/7' || tags['opening_hours'].includes('24/7')) {
                status = "24h";
                statusText = "Open 24/7";
                statusClass = "status-24h";
            } else {
                status = checkIfOpen(tags['opening_hours']);
                statusText = status === "open" ? "Open Now" : "Closed Now";
                statusClass = status === "open" ? "status-open" : "status-closed";
            }
        } else {
            status = "unknown";
            statusText = "Hours Unknown";
            statusClass = "status-closed";
        }
        
        pharmacies.push({
            id: element.id,
            name: tags.name || "Pharmacy",
            lat: element.lat || element.center?.lat,
            lng: element.lon || element.center?.lon,
            address: tags['addr:full'] || tags['addr:street'] || "Address not available",
            phone: tags.phone || tags['contact:phone'] || "Not available",
            opening_hours: tags.opening_hours || "Not specified",
            status: status,
            statusText: statusText,
            statusClass: statusClass,
            distance: distance,
            distanceText: formatDistance(distance),
            wheelchair: tags.wheelchair === 'yes' ? "Yes" : "Not specified"
        });
    }
    
    // Sort by distance
    pharmacies.sort((a, b) => a.distance - b.distance);
    
    return pharmacies;
}

function calculateDistance(lat1, lon1, lat2, lon2) {
    if (!lat2 || !lon2) return 9999;
    const R = 6371; // Earth's radius in km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

function formatDistance(distance) {
    if (distance < 1) {
        return `${Math.round(distance * 1000)} m`;
    }
    return `${distance.toFixed(1)} km`;
}

function checkIfOpen(openingHours) {
    // Simplified check - in real app, parse actual hours
    const now = new Date();
    const hour = now.getHours();
    if (hour >= 9 && hour <= 21) {
        return "open";
    }
    return "closed";
}

function displayPharmacies(pharmacies) {
    document.getElementById('pharmacyLoadingState').classList.add('hidden');
    document.getElementById('pharmacyFilters').classList.remove('hidden');
    document.getElementById('pharmacyResults').classList.remove('hidden');
    document.getElementById('pharmacyNoResults').classList.add('hidden');
    
    const grid = document.getElementById('pharmacyGrid');
    const filterOpen = document.getElementById('filterOpenNow').value;
    const maxDistance = parseFloat(document.getElementById('distanceSlider').value);
    
    let filtered = [...pharmacies];
    
    // Filter by open status
    if (filterOpen === 'open') {
        filtered = filtered.filter(p => p.status === 'open');
    } else if (filterOpen === '24h') {
        filtered = filtered.filter(p => p.status === '24h');
    }
    
    // Filter by distance (0.5km to 20km)
    filtered = filtered.filter(p => p.distance <= maxDistance);
    
    // Update results count
    document.getElementById('resultsCount').innerHTML = `${filtered.length} pharmacies found within ${maxDistance} km`;
    
    if (filtered.length === 0) {
        document.getElementById('noResultDistance').innerText = maxDistance;
        document.getElementById('pharmacyNoResults').classList.remove('hidden');
        document.getElementById('pharmacyResults').classList.add('hidden');
        return;
    }
    
    grid.innerHTML = filtered.map((pharmacy, index) => `
        <div class="pharmacy-card ${pharmacy.status === 'open' ? 'open' : pharmacy.status === '24h' ? 'twentyfour' : 'closed'}" onclick="showPharmacyDetails(${JSON.stringify(pharmacy).replace(/"/g, '&quot;')})">
            <div class="pharmacy-rank">${index + 1}</div>
            <div class="pharmacy-name">
                <span>${pharmacy.name}</span>
                <span class="pharmacy-status ${pharmacy.statusClass}">${pharmacy.statusText}</span>
            </div>
            <div class="pharmacy-address">
                <i class="fas fa-map-marker-alt"></i> ${pharmacy.address.substring(0, 80)}${pharmacy.address.length > 80 ? '...' : ''}
            </div>
            <div class="pharmacy-details">
                <div class="pharmacy-distance">
                    <i class="fas fa-road"></i> ${pharmacy.distanceText} • ${index === 0 ? '🥇 Nearest' : index === 1 ? '🥈' : index === 2 ? '🥉' : ''}
                </div>
                <div class="pharmacy-hours">
                    <i class="fas fa-clock"></i> ${pharmacy.opening_hours.substring(0, 30)}${pharmacy.opening_hours.length > 30 ? '...' : ''}
                </div>
                <div class="pharmacy-phone">
                    <i class="fas fa-phone"></i> ${pharmacy.phone}
                </div>
            </div>
        </div>
    `).join('');
}

function filterPharmacies() {
    displayPharmacies(allPharmacies);
}

function increaseDistanceAndRetry() {
    const slider = document.getElementById('distanceSlider');
    let currentValue = parseFloat(slider.value);
    let newValue = currentValue + 5;
    if (newValue > 20) newValue = 20;
    slider.value = newValue;
    document.getElementById('distanceValue').innerText = newValue;
    filterPharmacies();
}

function showPharmacyDetails(pharmacy) {
    const modal = document.getElementById('pharmacyModal');
    document.getElementById('modalPharmacyName').textContent = pharmacy.name;
    document.getElementById('modalAddress').textContent = pharmacy.address;
    document.getElementById('modalPhone').textContent = pharmacy.phone;
    document.getElementById('modalHours').textContent = pharmacy.opening_hours;
    document.getElementById('modalStatus').innerHTML = `<span class="pharmacy-status ${pharmacy.statusClass}">${pharmacy.statusText}</span>`;
    document.getElementById('modalDistance').textContent = pharmacy.distanceText;
    
    // Set directions link
    const directionsLink = document.getElementById('directionsLink');
    directionsLink.href = `https://www.google.com/maps/dir/${userLat},${userLng}/${pharmacy.lat},${pharmacy.lng}`;
    
    // Set call link
    const callLink = document.getElementById('callLink');
    callLink.href = `tel:${pharmacy.phone.replace(/\D/g, '')}`;
    
    modal.classList.remove('hidden');
}

function closePharmacyModal() {
    document.getElementById('pharmacyModal').classList.add('hidden');
}

function searchByCity() {
    document.getElementById('locationPermissionCard').classList.add('hidden');
    document.getElementById('citySearchCard').classList.remove('hidden');
}

function backToLocation() {
    document.getElementById('citySearchCard').classList.add('hidden');
    document.getElementById('locationPermissionCard').classList.remove('hidden');
}

async function searchPharmaciesByCity() {
    const city = document.getElementById('citySearchInput').value.trim();
    
    if (!city) {
        alert("Please enter a city name");
        return;
    }
    
    document.getElementById('pharmacyLoadingState').classList.remove('hidden');
    document.getElementById('pharmacyFilters').classList.add('hidden');
    document.getElementById('pharmacyResults').classList.add('hidden');
    document.getElementById('citySearchCard').classList.add('hidden');
    
    try {
        const geoResponse = await fetch(`${NOMINATIM_URL}?format=json&q=${city}, India&limit=1`);
        const geoData = await geoResponse.json();
        
        if (geoData && geoData[0]) {
            userLat = parseFloat(geoData[0].lat);
            userLng = parseFloat(geoData[0].lon);
            currentLocationName = city;
            document.getElementById('currentLocationDisplay').innerHTML = `<i class="fas fa-map-marker-alt"></i> ${city}`;
            await searchNearbyPharmacies();
            document.getElementById('locationInfoBar').classList.remove('hidden');
        } else {
            throw new Error("City not found");
        }
        
    } catch (error) {
        console.error("Error searching city:", error);
        document.getElementById('pharmacyLoadingState').classList.add('hidden');
        alert("Could not find that city. Please try again.");
        document.getElementById('citySearchCard').classList.remove('hidden');
    }
}

function retryLocation() {
    document.getElementById('pharmacyNoResults').classList.add('hidden');
    getUserLocation();
}

// Mock pharmacy data for fallback when API fails
function getMockPharmacies() {
    const distances = [0.5, 0.8, 1.2, 1.8, 2.5, 3.2, 4.0, 5.5, 7.0, 8.5, 10.0, 12.5, 15.0, 18.0, 20.0];
    const pharmacyNames = [
        "Apollo Pharmacy", "MedPlus Pharmacy", "Jan Aushadhi Kendra", "Wellness Forever", "Guardian Pharmacy",
        "Netmeds Pharmacy", "PharmEasy Store", "Medlife Pharmacy", "1mg Pharmacy", "Healthkart Pharmacy",
        "Care Pharmacy", "Lifeline Medicals", "City Drug Store", "Family Pharmacy", "24x7 Medicos"
    ];
    const addresses = [
        "Main Road, Near City Hospital", "Sector 12, Near Metro Station", "Government Hospital Complex",
        "Mall Road, Near Shopping Complex", "City Center, First Floor", "Bus Stand Area", "Railway Station Road",
        "Market Complex", "Residential Colony", "Commercial Street"
    ];
    
    const pharmacies = [];
    const now = new Date();
    const hour = now.getHours();
    
    for (let i = 0; i < 15; i++) {
        let status, statusText, statusClass;
        if (i % 3 === 0) {
            status = "24h";
            statusText = "Open 24/7";
            statusClass = "status-24h";
        } else if ((hour >= 9 && hour <= 21) || i % 2 === 0) {
            status = "open";
            statusText = "Open Now";
            statusClass = "status-open";
        } else {
            status = "closed";
            statusText = "Closed Now";
            statusClass = "status-closed";
        }
        
        pharmacies.push({
            id: i + 1,
            name: pharmacyNames[i % pharmacyNames.length] + (i < 5 ? " (Nearest)" : ""),
            lat: (userLat || 28.6139) + (Math.random() - 0.5) * 0.2,
            lng: (userLng || 77.2090) + (Math.random() - 0.5) * 0.2,
            address: addresses[i % addresses.length] + ", " + (currentLocationName || "Your City"),
            phone: `+91-${Math.floor(Math.random() * 9000000000) + 1000000000}`,
            opening_hours: status === "24h" ? "24/7" : "9:00 AM - 9:00 PM",
            status: status,
            statusText: statusText,
            statusClass: statusClass,
            distance: distances[i % distances.length],
            distanceText: formatDistance(distances[i % distances.length]),
            wheelchair: "Yes"
        });
    }
    
    pharmacies.sort((a, b) => a.distance - b.distance);
    return pharmacies;
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('pharmacyModal');
    if (event.target === modal) {
        closePharmacyModal();
    }
}

// ================== AI HEALTH RISK PREDICTOR FUNCTIONS ==================

async function predictHealthRisk() {
    // Get required fields
    const age = parseInt(document.getElementById('riskAge').value);
    let weight = parseFloat(document.getElementById('riskWeight').value);
    const weightUnit = document.getElementById('weightUnit').value;
    
    // Validate required fields
    if (!age || age < 18 || age > 120) {
        showRiskError('Please enter a valid age (18-120 years)');
        return;
    }
    
    if (!weight || weight <= 0) {
        showRiskError('Please enter your weight');
        return;
    }
    
    // Convert weight to kg if needed
    if (weightUnit === 'lbs') {
        weight = weight * 0.453592;
    }
    
    // Get height and calculate BMI
    let height = parseFloat(document.getElementById('riskHeight').value);
    const heightUnit = document.getElementById('heightUnit').value;
    if (height && heightUnit === 'ft') {
        height = height * 30.48;
    }
    
    let bmi = null;
    if (height && height > 0) {
        bmi = weight / ((height / 100) ** 2);
        bmi = Math.round(bmi * 10) / 10;
    }
    
    // Get all form data
    const formData = {
        age: age,
        weight: weight,
        bmi: bmi,
        gender: document.getElementById('riskGender').value,
        systolic_bp: parseInt(document.getElementById('riskSystolic').value) || null,
        diastolic_bp: parseInt(document.getElementById('riskDiastolic').value) || null,
        blood_sugar: parseInt(document.getElementById('riskBloodSugar').value) || null,
        smoking: document.getElementById('riskSmoking').value,
        alcohol: document.getElementById('riskAlcohol').value,
        activity: document.getElementById('riskActivity').value,
        diet: document.getElementById('riskDiet').value,
        family_history: document.getElementById('riskFamilyHistory').value,
        sleep_quality: document.getElementById('riskSleepQuality').value,
        stress_level: document.getElementById('riskStressLevel').value
    };
    
    // Show loading
    document.getElementById('riskLoadingState').classList.remove('hidden');
    document.getElementById('riskResults').classList.add('hidden');
    document.getElementById('riskErrorState').classList.add('hidden');
    
    try {
        const response = await fetch(`${API_URL}/predict-health-risk`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const results = await response.json();
        
        if (results.error) {
            showRiskError(results.error);
            document.getElementById('riskLoadingState').classList.add('hidden');
            return;
        }
        
        displayRiskResults(results);
        document.getElementById('riskLoadingState').classList.add('hidden');
        document.getElementById('riskResults').classList.remove('hidden');
        
    } catch (error) {
        console.error('Prediction error:', error);
        showRiskError('Server error. Please try again.');
        document.getElementById('riskLoadingState').classList.add('hidden');
    }
}

function displayRiskResults(results) {
    // Update overall score
    document.getElementById('overallScore').innerHTML = `${results.overall_score}<span style="font-size: 18px;">/100</span>`;
    document.getElementById('scoreFill').style.width = `${results.overall_score}%`;
    
    let scoreMessage = '';
    if (results.overall_score >= 80) {
        scoreMessage = '🎉 Excellent! Your health profile looks great. Keep up the healthy habits!';
    } else if (results.overall_score >= 60) {
        scoreMessage = '👍 Good! Some areas need attention. Follow the recommendations to improve.';
    } else if (results.overall_score >= 40) {
        scoreMessage = '⚠️ Fair. Significant room for improvement. Consider lifestyle changes.';
    } else {
        scoreMessage = '🚨 Needs Attention. High risk factors detected. Consult a doctor soon.';
    }
    document.getElementById('scoreMessage').innerHTML = scoreMessage;
    
    // Update Hypertension Risk
    const hypertensionPercent = results.hypertension_risk;
    document.getElementById('hypertensionPercent').innerHTML = `${hypertensionPercent}%`;
    document.getElementById('hypertensionFill').style.width = `${hypertensionPercent}%`;
    
    let hypertensionLevel = '';
    let hypertensionDetails = '';
    if (hypertensionPercent < 20) {
        hypertensionLevel = 'Low Risk';
        hypertensionDetails = 'Your risk of developing hypertension is low. Maintain healthy habits.';
    } else if (hypertensionPercent < 40) {
        hypertensionLevel = 'Mild Risk';
        hypertensionDetails = 'Slightly elevated risk. Monitor blood pressure regularly.';
    } else if (hypertensionPercent < 60) {
        hypertensionLevel = 'Moderate Risk';
        hypertensionDetails = 'Moderate risk detected. Lifestyle changes recommended.';
    } else if (hypertensionPercent < 80) {
        hypertensionLevel = 'High Risk';
        hypertensionDetails = 'High risk! Consult doctor and make immediate lifestyle changes.';
    } else {
        hypertensionLevel = 'Very High Risk';
        hypertensionDetails = 'Critical risk! Seek medical attention immediately.';
    }
    
    document.getElementById('hypertensionLevel').innerHTML = hypertensionLevel;
    document.getElementById('hypertensionLevel').className = `risk-level ${hypertensionPercent < 40 ? 'low' : hypertensionPercent < 60 ? 'moderate' : 'high'}`;
    document.getElementById('hypertensionDetails').innerHTML = hypertensionDetails;
    document.getElementById('hypertensionFactors').innerHTML = `<strong>Key factors:</strong> ${results.hypertension_factors.join(' • ')}`;
    
    // Update Heart Disease Risk
    const heartPercent = results.heart_disease_risk;
    document.getElementById('heartPercent').innerHTML = `${heartPercent}%`;
    document.getElementById('heartFill').style.width = `${heartPercent}%`;
    
    let heartLevel = '';
    let heartDetails = '';
    if (heartPercent < 20) {
        heartLevel = 'Low Risk';
        heartDetails = 'Your heart disease risk is low. Continue healthy habits.';
    } else if (heartPercent < 40) {
        heartLevel = 'Mild Risk';
        heartDetails = 'Slightly elevated risk. Focus on heart-healthy lifestyle.';
    } else if (heartPercent < 60) {
        heartLevel = 'Moderate Risk';
        heartDetails = 'Moderate risk detected. Diet and exercise crucial.';
    } else if (heartPercent < 80) {
        heartLevel = 'High Risk';
        heartDetails = 'High risk! Consult cardiologist immediately.';
    } else {
        heartLevel = 'Very High Risk';
        heartDetails = 'Critical risk! Urgent medical consultation needed.';
    }
    
    document.getElementById('heartLevel').innerHTML = heartLevel;
    document.getElementById('heartLevel').className = `risk-level ${heartPercent < 40 ? 'low' : heartPercent < 60 ? 'moderate' : 'high'}`;
    document.getElementById('heartDetails').innerHTML = heartDetails;
    document.getElementById('heartFactors').innerHTML = `<strong>Key factors:</strong> ${results.heart_factors.join(' • ')}`;
    
    // Display recommendations
    const recommendationsList = document.getElementById('recommendationsList');
    recommendationsList.innerHTML = `<ul>${results.recommendations.map(r => `<li>${r}</li>`).join('')}</ul>`;
}

function shareRiskReport() {
    const overall = document.getElementById('overallScore').innerHTML;
    const hypertension = document.getElementById('hypertensionPercent').innerHTML;
    const heart = document.getElementById('heartPercent').innerHTML;
    
    const shareText = `🏥 AI Health Risk Assessment Report\n\n` +
        `Overall Health Score: ${overall}\n` +
        `Hypertension Risk: ${hypertension}\n` +
        `Heart Disease Risk: ${heart}\n\n` +
        `Generated by Medical AI Dashboard\n` +
        `⚠️ This is an AI prediction. Consult a doctor for medical advice.`;
    
    if (navigator.share) {
        navigator.share({
            title: 'My Health Risk Report',
            text: shareText
        }).catch(() => {
            copyToClipboard(shareText);
            showNotification('Report copied to clipboard!', 'success');
        });
    } else {
        copyToClipboard(shareText);
        showNotification('Report copied to clipboard!', 'success');
    }
}

function showRiskError(message) {
    document.getElementById('riskErrorMessage').innerHTML = message;
    document.getElementById('riskErrorState').classList.remove('hidden');
}

function hideRiskError() {
    document.getElementById('riskErrorState').classList.add('hidden');
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text);
}




// ================== HOSPITAL COST ESTIMATOR FUNCTIONS ==================

let currentCostData = null;

function selectDisease() {
    const disease = document.getElementById('diseaseSelect').value;
    if (disease) {
        document.getElementById('costNoSelection').classList.add('hidden');
    }
}

async function estimateCost() {
    const disease = document.getElementById('diseaseSelect').value;
    const cityTier = document.getElementById('citySelect').value;
    const insurance = document.getElementById('insuranceSelect').value;
    
    if (!disease) {
        document.getElementById('costNoSelection').classList.remove('hidden');
        document.getElementById('costResults').classList.add('hidden');
        return;
    }
    
    // Show loading
    document.getElementById('costLoadingState').classList.remove('hidden');
    document.getElementById('costResults').classList.add('hidden');
    document.getElementById('costNoSelection').classList.add('hidden');
    
    try {
        const response = await fetch(`${API_URL}/estimate-treatment-cost`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                disease: disease,
                city_tier: cityTier,
                insurance: insurance
            })
        });
        
        const data = await response.json();
        currentCostData = data;
        displayCostResults(data);
        
        document.getElementById('costLoadingState').classList.add('hidden');
        document.getElementById('costResults').classList.remove('hidden');
        
    } catch (error) {
        console.error('Cost estimation error:', error);
        document.getElementById('costLoadingState').classList.add('hidden');
        alert('Error calculating costs. Please try again.');
    }
}

function displayCostResults(data) {
    // Update header
    document.getElementById('treatmentName').innerHTML = data.treatment_name;
    document.getElementById('locationBadge').innerHTML = `<i class="fas fa-map-marker-alt"></i> ${data.city_display}`;
    
    // Update government hospital
    document.getElementById('govtCost').innerHTML = `₹ ${formatNumber(data.government.min)} - ${formatNumber(data.government.max)}`;
    document.getElementById('govtWait').innerHTML = data.government.wait_time;
    
    // Update private budget hospital
    document.getElementById('privateBudgetCost').innerHTML = `₹ ${formatNumber(data.private_budget.min)} - ${formatNumber(data.private_budget.max)}`;
    document.getElementById('privateBudgetWait').innerHTML = data.private_budget.wait_time;
    
    // Update premium hospital
    document.getElementById('premiumCost').innerHTML = `₹ ${formatNumber(data.premium.min)} - ${formatNumber(data.premium.max)}`;
    document.getElementById('premiumWait').innerHTML = data.premium.wait_time;
    
    // Update cost breakdown
    const breakdownItems = document.getElementById('breakdownItems');
    breakdownItems.innerHTML = data.cost_breakdown.map(item => `
        <div class="breakdown-item">
            <span class="item-name">${item.name}</span>
            <span class="item-cost">₹ ${formatNumber(item.cost)}</span>
        </div>
    `).join('');
    
    // Update insurance impact
    const insuranceInfo = document.getElementById('insuranceInfo');
    if (data.insurance_impact) {
        insuranceInfo.innerHTML = `
            <div class="insurance-info">
                <div>
                    <strong>Total Estimated Cost:</strong> ₹ ${formatNumber(data.insurance_impact.total_cost)}
                </div>
                <div class="insurance-amount">
                    Insurance Coverage: ₹ ${formatNumber(data.insurance_impact.insurance_cover)}
                </div>
                <div class="out-of-pocket">
                    Your Out-of-Pocket: ₹ ${formatNumber(data.insurance_impact.out_of_pocket)}
                </div>
            </div>
        `;
    } else {
        insuranceInfo.innerHTML = '<p>No insurance information available for this selection.</p>';
    }
    
    // Update savings tips
    const savingsTips = document.getElementById('savingsTipsList');
    savingsTips.innerHTML = data.savings_tips.map(tip => `<li>${tip}</li>`).join('');
}

function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function shareCostEstimate() {
    if (!currentCostData) return;
    
    const shareText = `💰 Hospital Cost Estimate 💰\n\n` +
        `Treatment: ${currentCostData.treatment_name}\n` +
        `Location: ${currentCostData.city_display}\n\n` +
        `🏥 Government Hospital: ₹ ${formatNumber(currentCostData.government.min)} - ${formatNumber(currentCostData.government.max)}\n` +
        `🏥 Private Hospital (Budget): ₹ ${formatNumber(currentCostData.private_budget.min)} - ${formatNumber(currentCostData.private_budget.max)}\n` +
        `🏥 Premium Hospital: ₹ ${formatNumber(currentCostData.premium.min)} - ${formatNumber(currentCostData.premium.max)}\n\n` +
        `Use this estimate to plan your medical expenses!\n` +
        `Generated by Medical AI Dashboard`;
    
    if (navigator.share) {
        navigator.share({
            title: 'Hospital Cost Estimate',
            text: shareText
        }).catch(() => {
            copyToClipboard(shareText);
            showNotification('Estimate copied to clipboard!', 'success');
        });
    } else {
        copyToClipboard(shareText);
        showNotification('Estimate copied to clipboard!', 'success');
    }
}

function compareHospitals() {
    if (!currentCostData) return;
    
    const compareText = `🏥 HOSPITAL COMPARISON\n\n` +
        `Treatment: ${currentCostData.treatment_name}\n` +
        `Location: ${currentCostData.city_display}\n\n` +
        `1️⃣ Government Hospital:\n   Cost: ₹ ${formatNumber(currentCostData.government.min)} - ${formatNumber(currentCostData.government.max)}\n   Wait Time: ${currentCostData.government.wait_time}\n\n` +
        `2️⃣ Private Hospital (Budget):\n   Cost: ₹ ${formatNumber(currentCostData.private_budget.min)} - ${formatNumber(currentCostData.private_budget.max)}\n   Wait Time: ${currentCostData.private_budget.wait_time}\n\n` +
        `3️⃣ Premium Hospital:\n   Cost: ₹ ${formatNumber(currentCostData.premium.min)} - ${formatNumber(currentCostData.premium.max)}\n   Wait Time: ${currentCostData.premium.wait_time}\n\n` +
        `💰 Savings Tip: ${currentCostData.savings_tips[0]}`;
    
    copyToClipboard(compareText);
    showNotification('Hospital comparison copied!', 'success');
}




// ================== HEALTH GAMIFICATION SYSTEM ==================

// Game State
let gameState = {
    totalPoints: 0,
    currentStreak: 0,
    lastPlayedDate: null,
    completedMissions: [],
    unlockedRewards: [],
    unlockedAchievements: [],
    level: 1,
    missionsCompleted: 0
};

// Daily Missions
const dailyMissions = [
    { id: "water", title: "💧 Drink 2 Liters of Water", points: 10, icon: "💧", category: "hydration" },
    { id: "steps", title: "🚶 Take 5000 Steps", points: 15, icon: "🚶", category: "activity" },
    { id: "meditate", title: "🧘 Meditate for 10 Minutes", points: 20, icon: "🧘", category: "mental" },
    { id: "sleep", title: "😴 Get 7-8 Hours of Sleep", points: 15, icon: "😴", category: "sleep" },
    { id: "fruit", title: "🍎 Eat 5 Servings of Fruits/Vegetables", points: 10, icon: "🍎", category: "nutrition" },
    { id: "exercise", title: "🏋️ Exercise for 30 Minutes", points: 25, icon: "🏋️", category: "activity" },
    { id: "vitamins", title: "💊 Take Daily Vitamins", points: 10, icon: "💊", category: "health" },
    { id: "blood_pressure", title: "❤️ Check Blood Pressure", points: 15, icon: "❤️", category: "monitoring" },
    { id: "blood_sugar", title: "🩸 Check Blood Sugar", points: 15, icon: "🩸", category: "monitoring" },
    { id: "no_junk", title: "🍔 Avoid Junk Food", points: 20, icon: "🍔", category: "nutrition" }
];

// Streak Rewards
const streakRewards = [
    { days: 3, reward: "50 points", icon: "🎁" },
    { days: 7, reward: "100 points + Badge", icon: "🏅" },
    { days: 14, reward: "200 points + Rare Badge", icon: "🌟" },
    { days: 30, reward: "500 points + Legendary Badge", icon: "👑" },
    { days: 100, reward: "1000 points + Master Badge", icon: "🏆" }
];

// Rewards Shop
const rewardsShop = [
    { id: "badge_warrior", title: "🏅 Health Warrior Badge", cost: 100, icon: "🏅", type: "badge" },
    { id: "badge_master", title: "🌟 Wellness Master Badge", cost: 250, icon: "🌟", type: "badge" },
    { id: "badge_legend", title: "👑 Health Legend Badge", cost: 500, icon: "👑", type: "badge" },
    { id: "coupon_health", title: "🏥 Health Checkup Discount (10%)", cost: 200, icon: "🏥", type: "coupon" },
    { id: "coupon_medicine", title: "💊 Medicine Discount (₹100 off)", cost: 150, icon: "💊", type: "coupon" },
    { id: "consultation", title: "👨‍⚕️ Free Doctor Consultation", cost: 300, icon: "👨‍⚕️", type: "service" }
];

// Achievements
const achievements = [
    { id: "first_mission", title: "First Steps", description: "Complete your first mission", points: 50, icon: "🎯", requirement: 1 },
    { id: "week_streak", title: "Weekly Warrior", description: "Maintain a 7-day streak", points: 100, icon: "🔥", requirement: 7 },
    { id: "month_streak", title: "Monthly Master", description: "Maintain a 30-day streak", points: 500, icon: "🏆", requirement: 30 },
    { id: "points_500", title: "Point Collector", description: "Earn 500 total points", points: 100, icon: "⭐", requirement: 500 },
    { id: "points_1000", title: "Point Champion", description: "Earn 1000 total points", points: 250, icon: "🌟", requirement: 1000 },
    { id: "missions_10", title: "Mission Accomplished", description: "Complete 10 missions", points: 100, icon: "📋", requirement: 10 },
    { id: "missions_50", title: "Mission Master", description: "Complete 50 missions", points: 500, icon: "👑", requirement: 50 },
    { id: "all_missions", title: "Perfectionist", description: "Complete all missions in one day", points: 100, icon: "💯", requirement: "all" }
];

// Load saved game data
function loadGameData() {
    const saved = localStorage.getItem('healthGameData');
    if (saved) {
        gameState = JSON.parse(saved);
        
        // Check streak
        if (gameState.lastPlayedDate) {
            const lastDate = new Date(gameState.lastPlayedDate);
            const today = new Date();
            const diffDays = Math.floor((today - lastDate) / (1000 * 60 * 60 * 24));
            
            if (diffDays > 1) {
                // Streak broken
                gameState.currentStreak = 0;
                saveGameData();
            }
        }
    }
    updateDisplay();
}

// Save game data
function saveGameData() {
    localStorage.setItem('healthGameData', JSON.stringify(gameState));
}

// Update all displays
function updateDisplay() {
    document.getElementById('totalPoints').textContent = gameState.totalPoints;
    document.getElementById('currentStreak').textContent = gameState.currentStreak;
    document.getElementById('level').textContent = gameState.level;
    document.getElementById('missionsCompleted').textContent = gameState.missionsCompleted;
    
    // Update level and progress
    const pointsForNextLevel = gameState.level * 100;
    const currentLevelPoints = gameState.totalPoints - ((gameState.level - 1) * 100);
    const progressPercent = (currentLevelPoints / 100) * 100;
    
    document.getElementById('levelProgressFill').style.width = `${Math.min(100, progressPercent)}%`;
    document.getElementById('nextLevelInfo').innerHTML = `Next Level: ${pointsForNextLevel - gameState.totalPoints} points needed`;
    
    // Update missions
    updateMissions();
    
    // Update streak rewards
    updateStreakRewards();
    
    // Update rewards shop
    updateRewardsShop();
    
    // Update achievements
    updateAchievements();
    
    // Update leaderboard
    updateLeaderboard();
}

// Update daily missions
function updateMissions() {
    const missionsGrid = document.getElementById('missionsGrid');
    const today = new Date().toDateString();
    
    missionsGrid.innerHTML = dailyMissions.map(mission => {
        const isCompleted = gameState.completedMissions.includes(`${mission.id}_${today}`);
        return `
            <div class="mission-card ${isCompleted ? 'completed' : ''}">
                <div class="mission-icon">${mission.icon}</div>
                <div class="mission-info">
                    <div class="mission-title">${mission.title}</div>
                    <div class="mission-points">+${mission.points} points</div>
                    ${isCompleted ? '<div class="mission-status">✅ Completed!</div>' : ''}
                </div>
                <button class="complete-btn" onclick="completeMission('${mission.id}', ${mission.points})" ${isCompleted ? 'disabled' : ''}>
                    ${isCompleted ? 'Done' : 'Complete'}
                </button>
            </div>
        `;
    }).join('');
}

// Complete a mission
function completeMission(missionId, points) {
    const today = new Date().toDateString();
    const missionKey = `${missionId}_${today}`;
    
    if (gameState.completedMissions.includes(missionKey)) {
        showNotification('Mission already completed today!', 'warning');
        return;
    }
    
    // Add points
    gameState.totalPoints += points;
    gameState.completedMissions.push(missionKey);
    gameState.missionsCompleted++;
    
    // Update streak
    const lastDate = gameState.lastPlayedDate ? new Date(gameState.lastPlayedDate) : null;
    const todayDate = new Date();
    
    if (lastDate) {
        const diffDays = Math.floor((todayDate - lastDate) / (1000 * 60 * 60 * 24));
        if (diffDays === 1) {
            gameState.currentStreak++;
        } else if (diffDays === 0) {
            // Already played today
        } else {
            gameState.currentStreak = 1;
        }
    } else {
        gameState.currentStreak = 1;
    }
    
    gameState.lastPlayedDate = todayDate.toISOString();
    
    // Update level
    const newLevel = Math.floor(gameState.totalPoints / 100) + 1;
    if (newLevel > gameState.level) {
        gameState.level = newLevel;
        showCelebration('Level Up!', `Congratulations! You reached Level ${gameState.level}!`, '🎉');
    }
    
    // Check achievements
    checkAchievements();
    
    saveGameData();
    updateDisplay();
    
    showNotification(`+${points} points earned! Keep it up!`, 'success');
}

// Check and unlock achievements
function checkAchievements() {
    achievements.forEach(achievement => {
        if (!gameState.unlockedAchievements.includes(achievement.id)) {
            let unlocked = false;
            
            if (achievement.id === 'first_mission' && gameState.missionsCompleted >= 1) {
                unlocked = true;
            } else if (achievement.id === 'week_streak' && gameState.currentStreak >= 7) {
                unlocked = true;
            } else if (achievement.id === 'month_streak' && gameState.currentStreak >= 30) {
                unlocked = true;
            } else if (achievement.id === 'points_500' && gameState.totalPoints >= 500) {
                unlocked = true;
            } else if (achievement.id === 'points_1000' && gameState.totalPoints >= 1000) {
                unlocked = true;
            } else if (achievement.id === 'missions_10' && gameState.missionsCompleted >= 10) {
                unlocked = true;
            } else if (achievement.id === 'missions_50' && gameState.missionsCompleted >= 50) {
                unlocked = true;
            } else if (achievement.id === 'all_missions') {
                const today = new Date().toDateString();
                const todayMissions = dailyMissions.filter(m => 
                    gameState.completedMissions.includes(`${m.id}_${today}`)
                );
                if (todayMissions.length === dailyMissions.length) {
                    unlocked = true;
                }
            }
            
            if (unlocked) {
                gameState.unlockedAchievements.push(achievement.id);
                gameState.totalPoints += achievement.points;
                showCelebration('Achievement Unlocked!', achievement.title, achievement.icon);
                showNotification(`Achievement: ${achievement.title} +${achievement.points} points!`, 'success');
            }
        }
    });
}

// Update streak rewards display
function updateStreakRewards() {
    const streakContainer = document.getElementById('streakRewards');
    streakContainer.innerHTML = streakRewards.map(reward => {
        const isUnlocked = gameState.currentStreak >= reward.days;
        return `
            <div class="streak-badge ${isUnlocked ? 'unlocked' : 'locked'}">
                <div class="streak-icon">${reward.icon}</div>
                <div class="streak-days">${reward.days} Days</div>
                <div class="streak-reward">${reward.reward}</div>
                ${isUnlocked ? '<div class="streak-status">✅ Unlocked!</div>' : '<div class="streak-status">🔒 Locked</div>'}
            </div>
        `;
    }).join('');
}

// Update rewards shop
function updateRewardsShop() {
    const rewardsGrid = document.getElementById('rewardsGrid');
    rewardsGrid.innerHTML = rewardsShop.map(reward => {
        const isUnlocked = gameState.unlockedRewards.includes(reward.id);
        const canAfford = gameState.totalPoints >= reward.cost && !isUnlocked;
        
        return `
            <div class="reward-card ${isUnlocked ? 'unlocked' : ''}" onclick="purchaseReward('${reward.id}', ${reward.cost})">
                <div class="reward-icon">${reward.icon}</div>
                <div class="reward-info">
                    <div class="reward-title">${reward.title}</div>
                    <div class="reward-cost">💰 ${reward.cost} points</div>
                    ${isUnlocked ? '<div class="reward-status">✅ Unlocked!</div>' : ''}
                </div>
                ${!isUnlocked ? `<button class="complete-btn" style="background: ${canAfford ? '#f59e0b' : '#9ca3af'}">${canAfford ? 'Buy' : 'Locked'}</button>` : ''}
            </div>
        `;
    }).join('');
}

// Purchase a reward
function purchaseReward(rewardId, cost) {
    if (gameState.unlockedRewards.includes(rewardId)) {
        showNotification('You already unlocked this reward!', 'warning');
        return;
    }
    
    if (gameState.totalPoints >= cost) {
        gameState.totalPoints -= cost;
        gameState.unlockedRewards.push(rewardId);
        saveGameData();
        updateDisplay();
        showCelebration('Reward Unlocked!', `You unlocked a new reward!`, '🎁');
        showNotification('Reward unlocked successfully!', 'success');
    } else {
        showNotification(`Need ${cost - gameState.totalPoints} more points!`, 'warning');
    }
}

// Update achievements display
function updateAchievements() {
    const achievementsGrid = document.getElementById('achievementsGrid');
    achievementsGrid.innerHTML = achievements.map(achievement => {
        const isUnlocked = gameState.unlockedAchievements.includes(achievement.id);
        return `
            <div class="achievement-card ${isUnlocked ? 'unlocked' : 'locked'}">
                <div class="achievement-icon">${achievement.icon}</div>
                <div class="achievement-title">${achievement.title}</div>
                <div class="achievement-desc">${achievement.description}</div>
                ${isUnlocked ? '<div class="reward-status">✅ Unlocked!</div>' : '<div class="reward-status">🔒 In Progress</div>'}
            </div>
        `;
    }).join('');
}

// Update leaderboard
function updateLeaderboard() {
    // Get all users from localStorage (simulated)
    let leaderboard = [];
    
    // Add current user
    leaderboard.push({
        name: "You",
        points: gameState.totalPoints,
        level: gameState.level,
        streak: gameState.currentStreak
    });
    
    // Add some mock users for demonstration
    const mockUsers = [
        { name: "Health Champion 🏆", points: 1250, level: 13, streak: 45 },
        { name: "Wellness Warrior 💪", points: 980, level: 10, streak: 28 },
        { name: "Fitness Guru 🏃", points: 750, level: 8, streak: 21 },
        { name: "Hydration Hero 💧", points: 520, level: 6, streak: 14 },
        { name: "Sleep Master 😴", points: 340, level: 4, streak: 9 }
    ];
    
    leaderboard.push(...mockUsers);
    leaderboard.sort((a, b) => b.points - a.points);
    
    const leaderboardElement = document.getElementById('leaderboard');
    leaderboardElement.innerHTML = leaderboard.slice(0, 10).map((user, index) => {
        let rankClass = '';
        if (index === 0) rankClass = 'gold';
        else if (index === 1) rankClass = 'silver';
        else if (index === 2) rankClass = 'bronze';
        
        return `
            <div class="leaderboard-item">
                <div class="leaderboard-rank ${rankClass}">${index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : `#${index + 1}`}</div>
                <div class="leaderboard-name">${user.name}</div>
                <div class="leaderboard-points">${user.points} pts</div>
                <div class="leaderboard-level">Lvl ${user.level}</div>
                <div class="leaderboard-streak">🔥 ${user.streak}</div>
            </div>
        `;
    }).join('');
}

// Reset game data
function resetGameData() {
    if (confirm('Are you sure you want to reset all your game progress? This cannot be undone!')) {
        gameState = {
            totalPoints: 0,
            currentStreak: 0,
            lastPlayedDate: null,
            completedMissions: [],
            unlockedRewards: [],
            unlockedAchievements: [],
            level: 1,
            missionsCompleted: 0
        };
        saveGameData();
        updateDisplay();
        showNotification('Game data has been reset! Start fresh!', 'info');
    }
}

// Show celebration modal
function showCelebration(title, message, icon) {
    const modal = document.getElementById('celebrationModal');
    document.getElementById('celebrationTitle').textContent = title;
    document.getElementById('celebrationMessage').innerHTML = message;
    document.getElementById('celebrationIcon').textContent = icon;
    modal.classList.remove('hidden');
    
    // Auto close after 3 seconds
    setTimeout(() => {
        closeCelebrationModal();
    }, 3000);
}

function closeCelebrationModal() {
    document.getElementById('celebrationModal').classList.add('hidden');
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadGameData();
});



// ================== ENVIRONMENT IMPACT ALERTS ==================

let currentEnvData = null;
let envLat = null;
let envLng = null;

// OpenWeatherMap API (free tier - you need to sign up for API key)
// For demo, we'll use mock data with real API fallback
const WEATHER_API_KEY = "YOUR_API_KEY"; // Replace with actual API key
const WEATHER_API_URL = "https://api.openweathermap.org/data/2.5";
const AQI_API_URL = "https://api.openweathermap.org/data/2.5/air_pollution";

function getEnvironmentLocation() {
    if (navigator.geolocation) {
        document.getElementById('envLoadingState').classList.remove('hidden');
        document.getElementById('envLocationCard').classList.add('hidden');
        document.getElementById('envCitySearch').classList.add('hidden');
        document.getElementById('envDashboard').classList.add('hidden');
        document.getElementById('envErrorState').classList.add('hidden');
        
        navigator.geolocation.getCurrentPosition(
            (position) => {
                envLat = position.coords.latitude;
                envLng = position.coords.longitude;
                fetchEnvironmentData(envLat, envLng);
            },
            (error) => {
                document.getElementById('envLoadingState').classList.add('hidden');
                let errorMsg = "Unable to get your location. ";
                if (error.code === 1) errorMsg += "Please enable location services or search by city.";
                else if (error.code === 2) errorMsg += "Location unavailable. Try again.";
                else errorMsg += "Please search by city instead.";
                showEnvError(errorMsg);
            }
        );
    } else {
        alert("Geolocation not supported. Please search by city.");
        document.getElementById('envLocationCard').classList.add('hidden');
        document.getElementById('envCitySearch').classList.remove('hidden');
    }
}

async function fetchEnvironmentData(lat, lng) {
    try {
        // For demo purposes, using mock data since API key required
        // In production, replace with actual API calls
        
        // Simulate API call delay
        await new Promise(resolve => setTimeout(resolve, 1500));
        
        // Generate realistic mock data based on coordinates
        const mockData = generateMockEnvironmentData(lat, lng);
        currentEnvData = mockData;
        displayEnvironmentData(mockData);
        
        document.getElementById('envLoadingState').classList.add('hidden');
        document.getElementById('envDashboard').classList.remove('hidden');
        
    } catch (error) {
        console.error('Environment fetch error:', error);
        document.getElementById('envLoadingState').classList.add('hidden');
        showEnvError('Failed to fetch environmental data. Please try again.');
    }
}

function clearEnvironmentData() {
    // Reset all variables
    currentEnvData = null;
    envLat = null;
    envLng = null;
    
    // Hide dashboard and show location card
    document.getElementById('envDashboard').classList.add('hidden');
    document.getElementById('envErrorState').classList.add('hidden');
    document.getElementById('envLocationCard').classList.remove('hidden');
    document.getElementById('envCitySearch').classList.add('hidden');
    document.getElementById('envLoadingState').classList.add('hidden');
    
    // Clear city input
    document.getElementById('envCityInput').value = '';
    
    // Show success toast
    showClearToast();
}

function showClearToast() {
    const toast = document.getElementById('clearToast');
    toast.classList.remove('hidden');
    
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3000);
}

function generateMockEnvironmentData(lat, lng) {
    // Generate realistic mock data based on coordinates
    const randomSeed = Math.abs(Math.sin(lat * lng) * 10000);
    
    const weatherConditions = ['Clear Sky', 'Partly Cloudy', 'Cloudy', 'Light Rain', 'Sunny', 'Haze', 'Mist'];
    const weatherIcons = ['☀️', '⛅', '☁️', '🌧️', '☀️', '🌫️', '🌫️'];
    
    const conditionIndex = Math.floor(randomSeed % weatherConditions.length);
    
    // Temperature based on latitude (simpler logic)
    let baseTemp = 25 + Math.sin(lat * Math.PI / 180) * 10;
    const temp = Math.round(baseTemp + (randomSeed % 15) - 5);
    
    const humidity = 40 + Math.floor(randomSeed % 50);
    const windSpeed = 5 + Math.floor(randomSeed % 25);
    const uvIndex = 3 + Math.floor(randomSeed % 9);
    
    // Air Quality Index (0-500)
    const aqi = 50 + Math.floor(randomSeed % 200);
    let aqiStatus, aqiColor, aqiAdvice;
    
    if (aqi <= 50) {
        aqiStatus = "Good";
        aqiColor = "aqi-good";
        aqiAdvice = "Air quality is good. Enjoy outdoor activities!";
    } else if (aqi <= 100) {
        aqiStatus = "Moderate";
        aqiColor = "aqi-moderate";
        aqiAdvice = "Air quality is acceptable. Sensitive groups should limit prolonged outdoor exertion.";
    } else if (aqi <= 150) {
        aqiStatus = "Unhealthy for Sensitive Groups";
        aqiColor = "aqi-unhealthy";
        aqiAdvice = "Children, elderly, and those with respiratory conditions should limit outdoor activities.";
    } else if (aqi <= 200) {
        aqiStatus = "Unhealthy";
        aqiColor = "aqi-unhealthy";
        aqiAdvice = "Everyone may experience health effects. Limit outdoor activities.";
    } else if (aqi <= 300) {
        aqiStatus = "Very Unhealthy";
        aqiColor = "aqi-very-unhealthy";
        aqiAdvice = "Health alert. Avoid outdoor activities. Wear N95 mask if going out.";
    } else {
        aqiStatus = "Hazardous";
        aqiColor = "aqi-hazardous";
        aqiAdvice = "Emergency conditions. Stay indoors with air purifier. Avoid all outdoor activity.";
    }
    
    // Pollutants
    const pm25 = 20 + Math.floor(randomSeed % 150);
    const pm10 = 30 + Math.floor(randomSeed % 200);
    const no2 = 10 + Math.floor(randomSeed % 100);
    const o3 = 20 + Math.floor(randomSeed % 80);
    
    // Generate alerts based on conditions
    const alerts = [];
    
    if (temp > 35) {
        alerts.push({
            icon: "🌡️",
            title: "Extreme Heat Alert",
            message: `Temperature is ${temp}°C. High risk of heat exhaustion. Stay hydrated and avoid direct sunlight.`
        });
    } else if (temp < 10) {
        alerts.push({
            icon: "❄️",
            title: "Cold Wave Alert",
            message: `Temperature is ${temp}°C. Risk of hypothermia. Dress warmly and limit outdoor exposure.`
        });
    }
    
    if (aqi > 150) {
        alerts.push({
            icon: "😷",
            title: "Poor Air Quality Alert",
            message: `AQI is ${aqi} (${aqiStatus}). Wear N95 mask when outdoors. Use air purifier indoors.`
        });
    }
    
    if (humidity > 80) {
        alerts.push({
            icon: "💧",
            title: "High Humidity Alert",
            message: `Humidity is ${humidity}%. Risk of dehydration and heat stress. Drink extra water.`
        });
    } else if (humidity < 30) {
        alerts.push({
            icon: "🏜️",
            title: "Low Humidity Alert",
            message: `Humidity is ${humidity}%. Risk of dry skin and respiratory issues. Use humidifier.`
        });
    }
    
    if (uvIndex > 8) {
        alerts.push({
            icon: "🧴",
            title: "High UV Alert",
            message: `UV Index is ${uvIndex}. Wear sunscreen (SPF 50+), hat, and sunglasses. Avoid peak sun hours.`
        });
    }
    
    // Generate health recommendations
    const recommendations = [];
    
    if (temp > 35) {
        recommendations.push({ icon: "💧", text: "Drink 3-4 liters of water today to prevent dehydration" });
        recommendations.push({ icon: "🌳", text: "Stay indoors between 11 AM - 4 PM when heat is highest" });
        recommendations.push({ icon: "👕", text: "Wear light-colored, loose-fitting cotton clothes" });
    } else if (temp < 15) {
        recommendations.push({ icon: "🧥", text: "Wear layered warm clothing to maintain body temperature" });
        recommendations.push({ icon: "☕", text: "Drink warm fluids like tea or soup" });
    }
    
    if (aqi > 100) {
        recommendations.push({ icon: "😷", text: "Wear N95 mask when going outdoors" });
        recommendations.push({ icon: "🏠", text: "Use air purifier and keep windows closed" });
        recommendations.push({ icon: "🌿", text: "Add indoor plants that purify air (Areca palm, Snake plant)" });
    }
    
    if (humidity > 75) {
        recommendations.push({ icon: "💧", text: "Use dehumidifier to prevent mold growth" });
        recommendations.push({ icon: "🚿", text: "Take cool showers to regulate body temperature" });
    }
    
    if (humidity < 35) {
        recommendations.push({ icon: "💦", text: "Use humidifier to prevent dry skin and respiratory issues" });
        recommendations.push({ icon: "🧴", text: "Apply moisturizer to prevent dry skin" });
    }
    
    recommendations.push({ icon: "🍎", text: "Eat seasonal fruits rich in vitamin C for immunity" });
    recommendations.push({ icon: "🏃", text: "Exercise during cooler hours (early morning or evening)" });
    
    // Generate activity suggestions
    const activities = [];
    
    if (aqi <= 100 && temp >= 15 && temp <= 32) {
        activities.push({ icon: "🏃", text: "Great day for outdoor running or walking" });
        activities.push({ icon: "🚴", text: "Perfect weather for cycling" });
        activities.push({ icon: "🧘", text: "Ideal for outdoor yoga in the park" });
    } else if (aqi > 150 || temp > 35 || temp < 10) {
        activities.push({ icon: "🏠", text: "Stay indoors - best day for home workout" });
        activities.push({ icon: "🧘", text: "Indoor yoga or meditation recommended" });
        activities.push({ icon: "📚", text: "Good day for indoor activities and rest" });
    } else {
        activities.push({ icon: "🚶", text: "Moderate outdoor activity recommended" });
        activities.push({ icon: "🧘", text: "Indoor yoga or light stretching" });
    }
    
    // Weekly forecast
    const weekDays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const weeklyForecast = [];
    for (let i = 0; i < 7; i++) {
        const dayTemp = temp + (Math.random() * 6 - 3);
        weeklyForecast.push({
            day: weekDays[i],
            temp: Math.round(dayTemp),
            icon: ['☀️', '⛅', '☁️', '🌧️', '☀️'][Math.floor(Math.random() * 5)]
        });
    }
    
    return {
        location: getLocationNameFromCoords(lat, lng),
        temp: temp,
        condition: weatherConditions[conditionIndex],
        weatherIcon: weatherIcons[conditionIndex],
        humidity: humidity,
        windSpeed: windSpeed,
        uvIndex: uvIndex,
        aqi: aqi,
        aqiStatus: aqiStatus,
        aqiColor: aqiColor,
        aqiAdvice: aqiAdvice,
        pollutants: { pm25, pm10, no2, o3 },
        alerts: alerts,
        recommendations: recommendations,
        activities: activities,
        weeklyForecast: weeklyForecast,
        timestamp: new Date().toLocaleString()
    };
}

function getLocationNameFromCoords(lat, lng) {
    // Mock location names based on coordinates
    const cities = [
        { lat: 28.6139, lng: 77.2090, name: "Delhi" },
        { lat: 19.0760, lng: 72.8777, name: "Mumbai" },
        { lat: 12.9716, lng: 77.5946, name: "Bangalore" },
        { lat: 22.5726, lng: 88.3639, name: "Kolkata" },
        { lat: 13.0827, lng: 80.2707, name: "Chennai" }
    ];
    
    let closest = cities[0];
    let minDist = Infinity;
    
    for (const city of cities) {
        const dist = Math.hypot(lat - city.lat, lng - city.lng);
        if (dist < minDist) {
            minDist = dist;
            closest = city;
        }
    }
    
    return closest.name;
}

function displayEnvironmentData(data) {
    // Update location and time
    document.getElementById('envLocation').innerHTML = `${data.location}`;
    const now = new Date();
    document.getElementById('envTime').innerHTML = now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
    
    // Update weather card
    document.getElementById('weatherIcon').textContent = data.weatherIcon;
    document.getElementById('weatherTemp').innerHTML = `${data.temp}°C`;
    document.getElementById('weatherCondition').innerHTML = data.condition;
    document.getElementById('humidity').innerHTML = `${data.humidity}%`;
    document.getElementById('windSpeed').innerHTML = `${data.windSpeed} km/h`;
    document.getElementById('uvIndex').innerHTML = data.uvIndex;
    
    // Update AQI card
    const aqiCard = document.getElementById('airQualityCard');
    aqiCard.className = `air-quality-card ${data.aqiColor}`;
    document.getElementById('aqiValue').innerHTML = data.aqi;
    document.getElementById('aqiStatus').innerHTML = data.aqiStatus;
    document.getElementById('aqiAdvice').innerHTML = data.aqiAdvice;
    document.getElementById('pm25').innerHTML = `${data.pollutants.pm25} µg/m³`;
    document.getElementById('pm10').innerHTML = `${data.pollutants.pm10} µg/m³`;
    document.getElementById('no2').innerHTML = `${data.pollutants.no2} µg/m³`;
    document.getElementById('o3').innerHTML = `${data.pollutants.o3} µg/m³`;
    
    // Update critical alerts
    const alertsContainer = document.getElementById('criticalAlerts');
    if (data.alerts.length > 0) {
        alertsContainer.classList.remove('hidden');
        alertsContainer.innerHTML = `
            <h4><i class="fas fa-exclamation-triangle"></i> Critical Alerts</h4>
            ${data.alerts.map(alert => `
                <div class="alert-item">
                    <div class="alert-icon">${alert.icon}</div>
                    <div class="alert-content">
                        <div class="alert-title">${alert.title}</div>
                        <div class="alert-message">${alert.message}</div>
                    </div>
                </div>
            `).join('')}
        `;
    } else {
        alertsContainer.classList.add('hidden');
    }
    
    // Update health recommendations
    const recommendationsDiv = document.getElementById('healthRecommendations');
    recommendationsDiv.innerHTML = data.recommendations.map(rec => `
        <div class="recommendation-item">
            <div class="recommendation-icon">${rec.icon}</div>
            <div class="recommendation-text">${rec.text}</div>
        </div>
    `).join('');
    
    // Update activity suggestions
    const activitiesDiv = document.getElementById('activitySuggestions');
    activitiesDiv.innerHTML = data.activities.map(act => `
        <div class="activity-item">
            <div class="activity-icon">${act.icon}</div>
            <div class="activity-text">${act.text}</div>
        </div>
    `).join('');
    
    // Update weekly forecast
    const forecastDiv = document.getElementById('weeklyForecast');
    forecastDiv.innerHTML = data.weeklyForecast.map(day => `
        <div class="forecast-day">
            <div class="forecast-day-name">${day.day}</div>
            <div class="forecast-icon">${day.icon}</div>
            <div class="forecast-temp">${day.temp}°C</div>
        </div>
    `).join('');
}

function searchByCityEnv() {
    document.getElementById('envLocationCard').classList.add('hidden');
    document.getElementById('envCitySearch').classList.remove('hidden');
}

function backToEnvLocation() {
    document.getElementById('envCitySearch').classList.add('hidden');
    document.getElementById('envLocationCard').classList.remove('hidden');
}

async function searchEnvironmentByCity() {
    const city = document.getElementById('envCityInput').value.trim();
    
    if (!city) {
        alert("Please enter a city name");
        return;
    }
    
    document.getElementById('envLoadingState').classList.remove('hidden');
    document.getElementById('envCitySearch').classList.add('hidden');
    document.getElementById('envLocationCard').classList.add('hidden');
    document.getElementById('envDashboard').classList.add('hidden');
    
    // Simulate city search with mock data
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Generate mock data for city
    const mockData = generateMockEnvironmentDataForCity(city);
    currentEnvData = mockData;
    displayEnvironmentData(mockData);
    
    document.getElementById('envLoadingState').classList.add('hidden');
    document.getElementById('envDashboard').classList.remove('hidden');
}

function generateMockEnvironmentDataForCity(city) {
    // Generate city-specific mock data
    const cityTemps = {
        'delhi': 28, 'mumbai': 30, 'bangalore': 24, 'kolkata': 29, 'chennai': 31,
        'hyderabad': 27, 'pune': 26, 'ahmedabad': 32, 'jaipur': 29, 'lucknow': 27
    };
    
    const cityLower = city.toLowerCase();
    let baseTemp = cityTemps[cityLower] || 27;
    const temp = baseTemp + Math.floor(Math.random() * 6) - 3;
    const humidity = 40 + Math.floor(Math.random() * 40);
    const windSpeed = 5 + Math.floor(Math.random() * 20);
    const uvIndex = 4 + Math.floor(Math.random() * 8);
    const aqi = 60 + Math.floor(Math.random() * 150);
    
    let aqiStatus, aqiAdvice;
    if (aqi <= 50) {
        aqiStatus = "Good";
        aqiAdvice = "Air quality is good. Enjoy outdoor activities!";
    } else if (aqi <= 100) {
        aqiStatus = "Moderate";
        aqiAdvice = "Air quality is acceptable. Sensitive groups should limit prolonged outdoor exertion.";
    } else if (aqi <= 150) {
        aqiStatus = "Unhealthy for Sensitive Groups";
        aqiAdvice = "Children, elderly, and those with respiratory conditions should limit outdoor activities.";
    } else if (aqi <= 200) {
        aqiStatus = "Unhealthy";
        aqiAdvice = "Everyone may experience health effects. Limit outdoor activities.";
    } else {
        aqiStatus = "Very Unhealthy";
        aqiAdvice = "Health alert. Avoid outdoor activities. Wear N95 mask if going out.";
    }
    
    const alerts = [];
    if (temp > 35) {
        alerts.push({ icon: "🌡️", title: "Extreme Heat Alert", message: `Temperature is ${temp}°C. Stay hydrated and avoid direct sunlight.` });
    }
    if (aqi > 150) {
        alerts.push({ icon: "😷", title: "Poor Air Quality Alert", message: `AQI is ${aqi} (${aqiStatus}). Wear N95 mask when outdoors.` });
    }
    
    const recommendations = [
        { icon: "💧", text: "Drink 2-3 liters of water daily" },
        { icon: "🍎", text: "Eat seasonal fruits for immunity" }
    ];
    
    if (temp > 32) {
        recommendations.push({ icon: "🌳", text: "Avoid outdoor activities between 12 PM - 3 PM" });
    }
    if (aqi > 100) {
        recommendations.push({ icon: "😷", text: "Wear mask when going outdoors" });
    }
    
    const activities = [
        { icon: "🏃", text: "Exercise in early morning or evening" },
        { icon: "🧘", text: "Indoor yoga recommended" }
    ];
    
    return {
        location: city.charAt(0).toUpperCase() + city.slice(1),
        temp: temp,
        condition: "Partly Cloudy",
        weatherIcon: "⛅",
        humidity: humidity,
        windSpeed: windSpeed,
        uvIndex: uvIndex,
        aqi: aqi,
        aqiStatus: aqiStatus,
        aqiColor: aqi <= 100 ? "aqi-good" : aqi <= 150 ? "aqi-moderate" : "aqi-unhealthy",
        aqiAdvice: aqiAdvice,
        pollutants: { pm25: 30, pm10: 50, no2: 25, o3: 35 },
        alerts: alerts,
        recommendations: recommendations,
        activities: activities,
        weeklyForecast: [
            { day: 'Mon', temp: temp - 1, icon: '⛅' },
            { day: 'Tue', temp: temp, icon: '☀️' },
            { day: 'Wed', temp: temp + 1, icon: '☀️' },
            { day: 'Thu', temp: temp - 1, icon: '⛅' },
            { day: 'Fri', temp: temp - 2, icon: '☁️' },
            { day: 'Sat', temp: temp, icon: '☀️' },
            { day: 'Sun', temp: temp + 1, icon: '☀️' }
        ],
        timestamp: new Date().toLocaleString()
    };
}

function shareEnvironmentAlert() {
    if (!currentEnvData) return;
    
    const shareText = `🌍 ENVIRONMENT HEALTH ALERT 🌍\n\n` +
        `📍 Location: ${currentEnvData.location}\n` +
        `🌡️ Temperature: ${currentEnvData.temp}°C\n` +
        `💧 Humidity: ${currentEnvData.humidity}%\n` +
        `😷 Air Quality: ${currentEnvData.aqi} (${currentEnvData.aqiStatus})\n\n` +
        `💡 Health Tips:\n${currentEnvData.recommendations.slice(0, 3).map(r => `• ${r.text}`).join('\n')}\n\n` +
        `Stay safe and healthy! 🌿\n` +
        `Generated by Medical AI Dashboard`;
    
    if (navigator.share) {
        navigator.share({
            title: 'Environment Health Alert',
            text: shareText
        }).catch(() => {
            copyToClipboard(shareText);
            showNotification('Alert copied to clipboard!', 'success');
        });
    } else {
        copyToClipboard(shareText);
        showNotification('Alert copied to clipboard!', 'success');
    }
}

function showEnvError(message) {
    document.getElementById('envErrorMessage').innerHTML = message;
    document.getElementById('envErrorState').classList.remove('hidden');
    document.getElementById('envLoadingState').classList.add('hidden');
}

function retryEnvironment() {
    document.getElementById('envErrorState').classList.add('hidden');
    document.getElementById('envLocationCard').classList.remove('hidden');
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text);
}



// ================== RECOVERY MODE FUNCTIONS ==================

let recoveryActive = false;
let sickStartTime = null;
let waterIntake = 0;
let symptomsList = [];
let medicinesList = [];
let restLogsList = [];
let sickInterval = null;

// Default medicines for common illnesses
const defaultMedicinesData = {
    fever: [
        { name: "Paracetamol", dose: "500mg", time: "Every 6 hours" },
        { name: "Ibuprofen", dose: "400mg", time: "Every 8 hours (if fever > 101°F)" }
    ],
    cold: [
        { name: "Cetirizine", dose: "10mg", time: "Once daily at night" },
        { name: "Cough Syrup", dose: "10ml", time: "Every 8 hours" }
    ],
    headache: [
        { name: "Paracetamol", dose: "500mg", time: "Every 6 hours as needed" }
    ],
    stomach: [
        { name: "Ondansetron", dose: "4mg", time: "For nausea (as needed)" },
        { name: "ORS", dose: "1 packet", time: "After each loose motion" }
    ],
    fatigue: [
        { name: "Multivitamin", dose: "1 tablet", time: "Once daily" }
    ],
    bodypain: [
        { name: "Paracetamol", dose: "500mg", time: "Every 6 hours" },
        { name: "Diclofenac Gel", dose: "Apply", time: "Every 8 hours on affected area" }
    ]
};

// Recovery tips based on symptoms
const recoveryTipsData = {
    fever: [
        "🌡️ Monitor temperature every 4 hours",
        "💧 Drink plenty of fluids to prevent dehydration",
        "🧊 Use cold compress on forehead",
        "🛌 Rest in a cool, well-ventilated room",
        "📝 Record temperature to track patterns"
    ],
    cold: [
        "🤧 Use saline nasal spray for congestion",
        "🍵 Drink warm ginger tea with honey",
        "💤 Elevate head while sleeping",
        "🧴 Use humidifier to ease breathing",
        "🧣 Keep throat warm with scarf"
    ],
    headache: [
        "😴 Rest in a dark, quiet room",
        "💧 Stay hydrated - dehydration causes headaches",
        "🧊 Apply cold compress to forehead",
        "☕ Avoid caffeine if migraine",
        "📱 Reduce screen time"
    ],
    stomach: [
        "🍚 Eat bland foods (BRAT diet - Banana, Rice, Applesauce, Toast)",
        "💧 Sip ORS solution slowly",
        "🛌 Rest your digestive system",
        "🚫 Avoid dairy, spicy, and fatty foods",
        "🍵 Drink peppermint or ginger tea"
    ],
    fatigue: [
        "😴 Take short naps (20-30 minutes)",
        "💧 Stay hydrated - fatigue increases with dehydration",
        "🍎 Eat small, frequent meals",
        "🚶 Light stretching when energy permits",
        "🌿 Try deep breathing exercises"
    ],
    bodypain: [
        "🛌 Rest affected muscles",
        "🧊 Apply ice for first 48 hours",
        "🔥 Use heat pack after 48 hours",
        "💆 Gentle massage if tolerable",
        "🛏️ Use supportive pillows"
    ]
};

// Low energy daily routine
const lowEnergyRoutineData = [
    { time: "Morning (8-9 AM)", activity: "Wake up slowly, drink warm water", icon: "🌅" },
    { time: "Morning (9-10 AM)", activity: "Light breakfast - easy to digest (porridge, fruits)", icon: "🍳" },
    { time: "Morning (10 AM)", activity: "Take morning medications", icon: "💊" },
    { time: "Morning (10:30 AM)", activity: "Rest period - read or listen to calming music", icon: "📖" },
    { time: "Afternoon (12-1 PM)", activity: "Light lunch - soup or khichdi", icon: "🍲" },
    { time: "Afternoon (1-3 PM)", activity: "Nap time - body needs rest to heal", icon: "😴" },
    { time: "Afternoon (3 PM)", activity: "Take afternoon medications", icon: "💊" },
    { time: "Afternoon (3:30 PM)", activity: "Gentle stretching if energy permits", icon: "🧘" },
    { time: "Evening (6-7 PM)", activity: "Light dinner - early meal", icon: "🍽️" },
    { time: "Evening (8 PM)", activity: "Take evening medications", icon: "💊" },
    { time: "Night (9-10 PM)", activity: "Wind down - avoid screens", icon: "📵" },
    { time: "Night (10 PM)", activity: "Bedtime - aim for 8-10 hours sleep", icon: "🌙" }
];

// Rest reminders data
const restRemindersData = [
    { time: "Every 2 hours", duration: "Take 15-20 minutes rest" },
    { time: "After meals", duration: "Rest for 30 minutes after eating" },
    { time: "When feeling tired", duration: "Listen to your body and rest immediately" }
];

function toggleRecoveryMode() {
    const toggle = document.getElementById('recoveryToggle');
    
    if (toggle.checked) {
        activateRecoveryMode();
    } else {
        deactivateRecoveryMode();
    }
}

function activateRecoveryMode() {
    recoveryActive = true;
    sickStartTime = new Date();
    waterIntake = 0;
    symptomsList = [];
    medicinesList = [];
    restLogsList = [];
    
    // Update UI
    const statusCard = document.getElementById('statusToggleCard');
    document.getElementById('statusIcon').textContent = '🤒';
    document.getElementById('statusTitle').textContent = "You're in Recovery Mode";
    document.getElementById('statusMessage').textContent = "Take care of yourself. Follow the recovery plan below.";
    statusCard.style.background = "linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%)";
    statusCard.style.borderColor = "#fecaca";
    
    // Show dashboard
    document.getElementById('recoveryDashboard').classList.remove('hidden');
    
    // Update sick duration
    updateSickDuration();
    
    // Start timer for sick duration
    if (sickInterval) clearInterval(sickInterval);
    sickInterval = setInterval(updateSickDuration, 60000);
    
    // Initialize all components
    initializeMedicineReminders();
    initializeRestReminders();
    displayLowEnergyRoutine();
    updateHydrationDisplay();
    updateSymptomsDisplay();
    updateRecoveryTips();
    updateDoctorAdvice();
    
    // Save to localStorage
    saveRecoveryState();
    
    showNotification('🛏️ Recovery Mode Activated. Take care and follow your recovery plan!', 'success');
}

function deactivateRecoveryMode() {
    if (confirm('Are you sure you want to end Recovery Mode? Make sure you\'re feeling better.')) {
        recoveryActive = false;
        
        // Update UI
        const statusCard = document.getElementById('statusToggleCard');
        document.getElementById('statusIcon').textContent = '😊';
        document.getElementById('statusTitle').textContent = "You're Feeling Well";
        document.getElementById('statusMessage').textContent = "Toggle the switch below if you're feeling unwell and need recovery mode";
        statusCard.style.background = "linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)";
        statusCard.style.borderColor = "#bbf7d0";
        
        // Hide dashboard
        document.getElementById('recoveryDashboard').classList.add('hidden');
        
        // Clear intervals
        if (sickInterval) clearInterval(sickInterval);
        
        // Show celebration
        showRecoveryCelebration();
        
        // Clear localStorage
        localStorage.removeItem('recoveryState');
        
        showNotification('🎉 Great to see you recover! Take care of yourself!', 'success');
    } else {
        // Uncheck the toggle
        document.getElementById('recoveryToggle').checked = false;
    }
}

function endRecoveryMode() {
    document.getElementById('recoveryToggle').checked = false;
    deactivateRecoveryMode();
}

function selectSymptom(symptom) {
    if (!symptomsList.includes(symptom)) {
        symptomsList.push(symptom);
        updateSymptomsDisplay();
        updateRecoveryTips();
        updateDoctorAdvice();
        initializeMedicineReminders();
        saveRecoveryState();
        showNotification(`${getSymptomIcon(symptom)} ${getSymptomName(symptom)} added to symptoms`, 'info');
    } else {
        showNotification(`${getSymptomName(symptom)} already in symptoms list`, 'info');
    }
}

function getSymptomIcon(symptom) {
    const icons = {
        fever: '🌡️', cold: '🤧', headache: '🤕', 
        stomach: '🤢', fatigue: '😴', bodypain: '💪'
    };
    return icons[symptom] || '📝';
}

function getSymptomName(symptom) {
    const names = {
        fever: 'Fever', cold: 'Cold/Cough', headache: 'Headache',
        stomach: 'Stomach Issue', fatigue: 'Fatigue', bodypain: 'Body Pain'
    };
    return names[symptom] || symptom;
}

function updateSymptomsDisplay() {
    const container = document.getElementById('symptomsList');
    if (symptomsList.length === 0) {
        container.innerHTML = '<p style="color: #9ca3af; text-align: center;">No symptoms added. Click on symptoms above to track them.</p>';
    } else {
        container.innerHTML = symptomsList.map(s => `
            <div class="symptom-tag">
                ${getSymptomIcon(s)} ${getSymptomName(s)}
                <span class="remove-symptom" onclick="removeSymptom('${s}')">×</span>
            </div>
        `).join('');
    }
}

function removeSymptom(symptom) {
    symptomsList = symptomsList.filter(s => s !== symptom);
    updateSymptomsDisplay();
    updateRecoveryTips();
    updateDoctorAdvice();
    initializeMedicineReminders();
    saveRecoveryState();
}

function addCustomSymptom() {
    const input = document.getElementById('newSymptom');
    const symptom = input.value.trim();
    if (symptom) {
        if (!symptomsList.includes(symptom)) {
            symptomsList.push(symptom);
            updateSymptomsDisplay();
            updateRecoveryTips();
            updateDoctorAdvice();
            input.value = '';
            saveRecoveryState();
            showNotification(`Added "${symptom}" to symptoms`, 'info');
        } else {
            showNotification('Symptom already exists!', 'warning');
        }
    }
}

function initializeMedicineReminders() {
    let allMedicines = [];
    
    if (symptomsList.length > 0) {
        symptomsList.forEach(symptom => {
            if (defaultMedicinesData[symptom]) {
                allMedicines.push(...defaultMedicinesData[symptom]);
            }
        });
    } else {
        // Default medicines for general illness
        allMedicines = [
            { name: "Paracetamol", dose: "500mg", time: "Every 6 hours as needed", taken: false },
            { name: "Multivitamin", dose: "1 tablet", time: "Once daily", taken: false }
        ];
    }
    
    // Remove duplicates
    const uniqueMedicines = [];
    const medicineKeys = new Set();
    for (const med of allMedicines) {
        const key = `${med.name}_${med.dose}`;
        if (!medicineKeys.has(key)) {
            medicineKeys.add(key);
            uniqueMedicines.push({ ...med, taken: false });
        }
    }
    
    medicinesList = uniqueMedicines;
    displayMedicineReminders();
    saveRecoveryState();
}

function displayMedicineReminders() {
    const container = document.getElementById('medicineReminders');
    if (medicinesList.length === 0) {
        container.innerHTML = '<p style="color: #9ca3af; text-align: center;">No medicines added. Add custom medicine below.</p>';
    } else {
        container.innerHTML = medicinesList.map((med, index) => `
            <div class="medicine-item">
                <div class="medicine-time">${med.time}</div>
                <div class="medicine-name">${med.name}</div>
                <div class="medicine-dose">${med.dose}</div>
                ${!med.taken ? 
                    `<button class="take-btn" onclick="takeMedicine(${index})">Take</button>` :
                    `<span class="taken-badge">✓ Taken</span>`
                }
            </div>
        `).join('');
    }
}

function takeMedicine(index) {
    medicinesList[index].taken = true;
    displayMedicineReminders();
    saveRecoveryState();
    showNotification(`✓ ${medicinesList[index].name} taken as scheduled`, 'success');
    
    // Reset after 6 hours (simulate next dose)
    setTimeout(() => {
        if (recoveryActive && medicinesList[index]) {
            medicinesList[index].taken = false;
            displayMedicineReminders();
            saveRecoveryState();
            showNotification(`⏰ Time for next dose of ${medicinesList[index].name}`, 'warning');
        }
    }, 6 * 60 * 60 * 1000);
}

function addCustomMedicine() {
    const name = prompt("Enter medicine name:");
    if (!name) return;
    const dose = prompt("Enter dose (e.g., 500mg):");
    const time = prompt("Enter frequency (e.g., Every 6 hours):");
    
    medicinesList.push({
        name: name,
        dose: dose || "As prescribed",
        time: time || "As needed",
        taken: false
    });
    
    displayMedicineReminders();
    saveRecoveryState();
    showNotification(`Added ${name} to medicine reminders`, 'success');
}

function initializeRestReminders() {
    const container = document.getElementById('restReminders');
    container.innerHTML = restRemindersData.map(rest => `
        <div class="rest-item">
            <div class="rest-time">${rest.time}</div>
            <div class="rest-duration">${rest.duration}</div>
        </div>
    `).join('');
}

function logRest() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString();
    document.getElementById('lastRestTime').innerHTML = timeStr;
    restLogsList.push({ time: timeStr, duration: "30 minutes" });
    saveRecoveryState();
    showNotification('🛌 Rest logged! Your body needs this rest to recover.', 'success');
}

function displayLowEnergyRoutine() {
    const container = document.getElementById('lowEnergyRoutine');
    container.innerHTML = lowEnergyRoutineData.map(item => `
        <div class="routine-item">
            <div class="routine-icon">${item.icon}</div>
            <div class="routine-time">${item.time}</div>
            <div class="routine-activity">${item.activity}</div>
        </div>
    `).join('');
}

function addWater(ml) {
    waterIntake += ml;
    if (waterIntake > 3000) waterIntake = 3000;
    updateHydrationDisplay();
    saveRecoveryState();
    
    if (waterIntake >= 2000) {
        showNotification('🎉 Great! You\'ve reached your daily hydration goal!', 'success');
    }
}

function resetWater() {
    waterIntake = 0;
    updateHydrationDisplay();
    saveRecoveryState();
}

function updateHydrationDisplay() {
    const percentage = (waterIntake / 2000) * 100;
    document.getElementById('waterFill').style.width = `${Math.min(100, percentage)}%`;
    document.getElementById('waterTotal').innerHTML = waterIntake;
}

function updateRecoveryTips() {
    const container = document.getElementById('recoveryTips');
    let allTips = [];
    
    if (symptomsList.length > 0) {
        symptomsList.forEach(symptom => {
            if (recoveryTipsData[symptom]) {
                allTips.push(...recoveryTipsData[symptom]);
            }
        });
    } else {
        allTips = [
            "🛌 Get plenty of rest - sleep helps your immune system",
            "💧 Stay hydrated with water, herbal tea, or soup",
            "🍎 Eat nutritious foods even if you have little appetite",
            "🧼 Practice good hygiene to prevent spreading illness",
            "📱 Limit screen time to reduce eye strain",
            "🌿 Try deep breathing exercises to reduce stress"
        ];
    }
    
    // Remove duplicates
    allTips = [...new Set(allTips)];
    
    container.innerHTML = allTips.map(tip => `
        <div class="tip-item">
            <span>${tip}</span>
        </div>
    `).join('');
}

function updateDoctorAdvice() {
    const container = document.getElementById('doctorAdvice');
    let advice = [];
    
    if (symptomsList.includes('fever') && symptomsList.includes('bodypain')) {
        advice.push("⚠️ If fever exceeds 103°F (39.4°C) or lasts more than 3 days, consult a doctor immediately.");
    }
    if (symptomsList.includes('stomach')) {
        advice.push("⚠️ Seek medical help if you have blood in stool, severe abdominal pain, or can't keep fluids down for more than 24 hours.");
    }
    if (symptomsList.includes('cold') && symptomsList.includes('fever')) {
        advice.push("⚠️ Consult doctor if symptoms worsen after 5-7 days, you have difficulty breathing, or chest pain develops.");
    }
    if (symptomsList.includes('headache') && symptomsList.includes('fever')) {
        advice.push("⚠️ Seek immediate medical attention if headache is severe, sudden onset, or accompanied by neck stiffness.");
    }
    
    if (advice.length === 0) {
        advice = [
            "🩺 Most viral illnesses resolve within 7-10 days with rest and hydration.",
            "🏥 Seek medical attention if symptoms worsen or you develop new concerning symptoms.",
            "💊 Always complete prescribed antibiotic courses if given by your doctor.",
            "📞 Trust your body - if you feel something is wrong, consult a doctor."
        ];
    }
    
    container.innerHTML = advice.join('<br><br>');
}

function updateSickDuration() {
    if (!sickStartTime) return;
    const now = new Date();
    const diffMs = now - sickStartTime;
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);
    
    let durationText = "";
    if (diffDays > 0) {
        durationText = `Sick since: ${diffDays} day${diffDays > 1 ? 's' : ''} and ${diffHours % 24} hour${(diffHours % 24) !== 1 ? 's' : ''} ago`;
    } else if (diffHours > 0) {
        durationText = `Sick since: ${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    } else {
        durationText = `Sick since: Just now`;
    }
    
    const sickDurationElem = document.getElementById('sickDuration');
    if (sickDurationElem) {
        sickDurationElem.innerHTML = durationText;
    }
}

function showRecoveryCelebration() {
    const modal = document.getElementById('recoveryCelebration');
    if (modal) {
        modal.classList.remove('hidden');
        setTimeout(() => {
            closeRecoveryCelebration();
        }, 3000);
    }
}

function closeRecoveryCelebration() {
    const modal = document.getElementById('recoveryCelebration');
    if (modal) {
        modal.classList.add('hidden');
    }
}

function showTelemedicine() {
    showNotification('📞 Telemedicine consultation coming soon! For now, please contact your local doctor or call 911 for emergencies.', 'info');
}

function saveRecoveryState() {
    const state = {
        recoveryActive: recoveryActive,
        sickStartTime: sickStartTime ? sickStartTime.toISOString() : null,
        waterIntake: waterIntake,
        symptomsList: symptomsList,
        medicinesList: medicinesList,
        restLogsList: restLogsList
    };
    localStorage.setItem('recoveryState', JSON.stringify(state));
}

function loadRecoveryState() {
    const saved = localStorage.getItem('recoveryState');
    if (saved) {
        try {
            const state = JSON.parse(saved);
            if (state.recoveryActive) {
                recoveryActive = true;
                sickStartTime = state.sickStartTime ? new Date(state.sickStartTime) : new Date();
                waterIntake = state.waterIntake || 0;
                symptomsList = state.symptomsList || [];
                medicinesList = state.medicinesList || [];
                restLogsList = state.restLogsList || [];
                
                // Activate UI
                document.getElementById('recoveryToggle').checked = true;
                activateRecoveryMode();
            }
        } catch (e) {
            console.error('Error loading recovery state:', e);
        }
    }
}

// Load saved state on page load
document.addEventListener('DOMContentLoaded', function() {
    loadRecoveryState();
});

// Helper function for notifications (if not already defined)
function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = `pres-notification ${type}`;
    notification.innerHTML = message;
    notification.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: ${type === 'success' ? '#10b981' : type === 'warning' ? '#f59e0b' : '#3b82f6'};
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        z-index: 1000;
        animation: slideInRight 0.3s ease;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    `;
    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 4000);
}

// ========= CSS =========

const canvas = document.getElementById("particles");
const ctx = canvas.getContext("2d");

canvas.width = window.innerWidth;
canvas.height = window.innerHeight;

let particlesArray = [];

/* Particle class */
class Particle {
    constructor() {
        this.x = Math.random() * canvas.width;
        this.y = Math.random() * canvas.height;

        this.size = Math.random() * 2 + 1;

        this.speedX = (Math.random() - 0.5) * 0.5;
        this.speedY = (Math.random() - 0.5) * 0.5;

        this.angle = Math.random() * 360;
        this.rotationSpeed = (Math.random() - 0.5) * 0.02;

        this.color = `hsl(${Math.random() * 360}, 70%, 70%)`;
    }

    update() {
        this.x += this.speedX;
        this.y += this.speedY;
        this.angle += this.rotationSpeed;

        // Wrap around screen
        if (this.x > canvas.width) this.x = 0;
        if (this.x < 0) this.x = canvas.width;
        if (this.y > canvas.height) this.y = 0;
        if (this.y < 0) this.y = canvas.height;
    }

    draw() {
        ctx.save();
        ctx.translate(this.x, this.y);
        ctx.rotate(this.angle);

        ctx.beginPath();
        ctx.arc(0, 0, this.size, 0, Math.PI * 2);
        ctx.fillStyle = this.color;
        ctx.shadowBlur = 10;
        ctx.shadowColor = this.color;
        ctx.fill();

        ctx.restore();
    }
}

/* Create particles */
function initParticles() {
    particlesArray = [];
    for (let i = 0; i < 120; i++) { // increase for more stars
        particlesArray.push(new Particle());
    }
}

/* Animate */
function animateParticles() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    particlesArray.forEach(p => {
        p.update();
        p.draw();
    });

    requestAnimationFrame(animateParticles);
}

/* Resize fix */
window.addEventListener("resize", () => {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    initParticles();
});

/* Init */
initParticles();
animateParticles();

// ================== HEADER NAVIGATION ==================
function navigateToSection(section) {
    // Hide all main sections
    const mainSections = document.querySelectorAll('.main-section');
    mainSections.forEach(sec => sec.classList.add('hidden'));
    
    // Hide dashboard
    const dashboard = document.querySelector('.dashboard');
    if (dashboard) {
        dashboard.style.display = 'none';
    }
    
    // Show selected section
    const targetSection = document.getElementById(section + '-section');
    if (targetSection) {
        targetSection.classList.remove('hidden');
    }
    
    // Update active nav link
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('data-section') === section) {
            link.classList.add('active');
        }
    });
    
    // Special handling for dashboard
    if (section === 'dashboard') {
        if (dashboard) {
            dashboard.style.display = 'flex';
        }
    }
}

// Profile management functions
function saveProfile() {
    const formData = {
        fullName: document.getElementById('fullName').value,
        email: document.getElementById('email').value,
        phone: document.getElementById('phone').value,
        dob: document.getElementById('dob').value,
        bloodType: document.getElementById('bloodType').value,
        gender: document.getElementById('gender').value,
        allergies: document.getElementById('allergies').value,
        medications: document.getElementById('medications').value,
        conditions: document.getElementById('conditions').value
    };
    
    // Save to localStorage
    localStorage.setItem('userProfile', JSON.stringify(formData));
    
    // Update display
    document.getElementById('profileName').textContent = formData.fullName;
    document.getElementById('profileEmail').textContent = formData.email;
    
    // Show success message
    showNotification('Profile saved successfully!', 'success');
}

function loadProfile() {
    const savedProfile = localStorage.getItem('userProfile');
    if (savedProfile) {
        const data = JSON.parse(savedProfile);
        
        // Fill form fields
        document.getElementById('fullName').value = data.fullName || '';
        document.getElementById('email').value = data.email || '';
        document.getElementById('phone').value = data.phone || '';
        document.getElementById('dob').value = data.dob || '';
        document.getElementById('bloodType').value = data.bloodType || '';
        document.getElementById('gender').value = data.gender || '';
        document.getElementById('allergies').value = data.allergies || '';
        document.getElementById('medications').value = data.medications || '';
        document.getElementById('conditions').value = data.conditions || '';
        
        // Update display
        document.getElementById('profileName').textContent = data.fullName || 'John Doe';
        document.getElementById('profileEmail').textContent = data.email || 'john.doe@example.com';
    }
}

function resetProfile() {
    if (confirm('Are you sure you want to reset all profile data?')) {
        // Clear form
        document.getElementById('fullName').value = 'John Doe';
        document.getElementById('email').value = 'john.doe@example.com';
        document.getElementById('phone').value = '+1 234 567 8900';
        document.getElementById('dob').value = '';
        document.getElementById('bloodType').value = '';
        document.getElementById('gender').value = '';
        document.getElementById('allergies').value = '';
        document.getElementById('medications').value = '';
        document.getElementById('conditions').value = '';
        
        showNotification('Profile reset to defaults', 'info');
    }
}

function deleteProfile() {
    if (confirm('Are you sure you want to delete your profile? This action cannot be undone.')) {
        localStorage.removeItem('userProfile');
        resetProfile();
        showNotification('Profile deleted successfully', 'warning');
    }
}

// Notification system
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    // Style notification
    notification.style.cssText = `
        position: fixed;
        top: 100px;
        right: 20px;
        padding: 15px 20px;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        z-index: 10000;
        animation: slideIn 0.3s ease;
        max-width: 300px;
    `;
    
    // Set background color based on type
    switch(type) {
        case 'success':
            notification.style.background = 'linear-gradient(135deg, #22c55e, #16a34a)';
            break;
        case 'warning':
            notification.style.background = 'linear-gradient(135deg, #f59e0b, #d97706)';
            break;
        case 'error':
            notification.style.background = 'linear-gradient(135deg, #ef4444, #dc2626)';
            break;
        default:
            notification.style.background = 'linear-gradient(135deg, #3b82f6, #2563eb)';
    }
    
    // Add to page
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

// Add CSS animations for notifications
const notificationStyles = document.createElement('style');
notificationStyles.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(notificationStyles);

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Load profile data
    loadProfile();
    
    // Set dashboard as default view
    navigateToSection('dashboard');
});

// ================== LOGOUT FUNCTIONALITY ==================
function logout() {
    if (confirm('Are you sure you want to logout?')) {
        // Clear login data
        localStorage.removeItem('userLogin');
        
        // Clear session data
        sessionStorage.clear();
        
        // Show notification
        showNotification('Logged out successfully! Redirecting to login page...', 'success');
        
        // Redirect to login page after 1 second
        setTimeout(() => {
            window.location.href = 'login.html';
        }, 1000);
    }
}

// ================== LOGIN FUNCTIONALITY ==================
function handleLogin(event) {
    event.preventDefault();
    
    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;
    const rememberMe = document.getElementById('rememberMe').checked;
    
    // Validate email and password
    if (!email || !password) {
        showNotification('Please enter both email and password', 'error');
        return;
    }
    
    // Create user data object
    const userData = {
        email: email,
        password: password,
        loginTime: new Date().toISOString(),
        rememberMe: rememberMe
    };
    
    // Store login data
    localStorage.setItem('userLogin', JSON.stringify(userData));
    
    // Update profile with login data
    updateProfileWithLoginData(email);
    
    // Show success message
    showNotification('Login successful! Redirecting to Dashboard...', 'success');
    
    // Redirect to dashboard after 2 seconds
    setTimeout(() => {
        window.location.href = 'index.html';
    }, 2000);
}

function updateProfileWithLoginData(email) {
    // Get existing profile data or create new
    let profileData = localStorage.getItem('userProfile');
    if (profileData) {
        profileData = JSON.parse(profileData);
    } else {
        profileData = {
            fullName: 'John Doe',
            email: email,
            phone: '+1 234 567 8900',
            dob: '',
            bloodType: '',
            gender: '',
            allergies: '',
            medications: '',
            conditions: ''
        };
    }
    
    // Update email with login email
    profileData.email = email;
    profileData.lastLogin = new Date().toISOString();
    
    // Save updated profile data
    localStorage.setItem('userProfile', JSON.stringify(profileData));
    
    // Update profile display if on profile page
    if (document.getElementById('profileEmail')) {
        document.getElementById('profileEmail').textContent = email;
    }
    if (document.getElementById('email')) {
        document.getElementById('email').value = email;
    }
}

function togglePassword() {
    const passwordInput = document.getElementById('loginPassword');
    const passwordIcon = document.getElementById('passwordIcon');
    
    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        passwordIcon.className = 'fas fa-eye-slash';
    } else {
        passwordInput.type = 'password';
        passwordIcon.className = 'fas fa-eye';
    }
}

function socialLogin(provider) {
    showNotification(`${provider} login coming soon! Please use email login for now.`, 'info');
}

function showRegister() {
    showNotification('Registration page coming soon! Please use default login for now.', 'info');
}

function checkLoginStatus() {
    const loginData = localStorage.getItem('userLogin');
    if (loginData) {
        const data = JSON.parse(loginData);
        const loginTime = new Date(data.loginTime);
        const now = new Date();
        const hoursSinceLogin = (now - loginTime) / (1000 * 60 * 60);
        
        // If logged in within last 24 hours and remember me is checked, keep session
        if (hoursSinceLogin < 24 && data.rememberMe) {
            return true;
        } else if (hoursSinceLogin < 2) {
            // 2-hour session for non-remembered logins
            return true;
        }
    }
    return false;
}

function logout() {
    localStorage.removeItem('userLogin');
    showNotification('Logged out successfully', 'success');
    setTimeout(() => {
        window.location.href = 'login.html';
    }, 1000);
}

// Check login status on page load
document.addEventListener('DOMContentLoaded', function() {
    // Load profile data
    loadProfile();
    
    // Set dashboard as default view
    navigateToSection('dashboard');
    
    // Check if user should be logged in
    if (!checkLoginStatus() && window.location.pathname.includes('index.html')) {
        // Optionally redirect to login if not logged in
        // window.location.href = 'login.html';
    }
});

// Prevent default link behavior for nav links
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('nav-link')) {
        e.preventDefault();
    }
});

// ================== MENTAL HEALTH AI COMPANION FUNCTIONS ================== //

// Mood tracking functionality
function trackMood(mood) {
    // Remove previous selection
    document.querySelectorAll('.mood-option').forEach(option => {
        option.classList.remove('selected');
    });
    
    // Add selection to clicked mood
    event.target.closest('.mood-option').classList.add('selected');
    
    // Save mood entry
    const moodData = {
        mood: mood,
        timestamp: new Date().toISOString(),
        note: document.getElementById('moodNote').value
    };
    
    // Get existing mood data
    let moodHistory = JSON.parse(localStorage.getItem('moodHistory') || '[]');
    moodHistory.push(moodData);
    
    // Keep only last 30 entries
    if (moodHistory.length > 30) {
        moodHistory = moodHistory.slice(-30);
    }
    
    localStorage.setItem('moodHistory', JSON.stringify(moodHistory));
    
    // Update stress level based on mood
    updateStressLevel(mood);
    
    // Show success message
    showNotification('Mood tracked successfully!', 'success');
}

function logMoodEntry() {
    const selectedMood = document.querySelector('.mood-option.selected');
    if (!selectedMood) {
        showNotification('Please select a mood first', 'error');
        return;
    }
    
    const mood = selectedMood.dataset.mood;
    const note = document.getElementById('moodNote').value;
    
    trackMood(mood);
    
    // Clear note
    document.getElementById('moodNote').value = '';
    
    // Update stress pattern chart
    updateStressChart();
}

function updateStressLevel(mood) {
    const stressLevels = {
        'happy': 20,
        'calm': 30,
        'sad': 60,
        'anxious': 75,
        'stressed': 85,
        'angry': 90
    };
    
    const stressLevel = stressLevels[mood] || 50;
    const stressFill = document.getElementById('stressFill');
    const stressLevelText = document.getElementById('currentStressLevel');
    
    stressFill.style.width = stressLevel + '%';
    
    const levelNames = ['Low', 'Moderate', 'High', 'Very High'];
    const levelIndex = Math.floor(stressLevel / 25);
    stressLevelText.textContent = levelNames[Math.min(levelIndex, 3)];
}

function updateStressChart() {
    const canvas = document.getElementById('stressChart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Get mood history
    const moodHistory = JSON.parse(localStorage.getItem('moodHistory') || '[]');
    
    // Prepare data for chart (last 7 days)
    const last7Days = moodHistory.slice(-7);
    const labels = [];
    const data = [];
    
    for (let i = 0; i < 7; i++) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        labels.push(date.toLocaleDateString('en-US', { weekday: 'short' }));
        
        // Calculate average stress for this day
        const dayMoods = last7Days.filter(m => {
            const mDate = new Date(m.timestamp);
            return mDate.getDate() === date.getDate();
        });
        
        if (dayMoods.length > 0) {
            const stressValues = dayMoods.map(m => {
                const stressLevels = {
                    'happy': 20, 'calm': 30, 'sad': 60, 
                    'anxious': 75, 'stressed': 85, 'angry': 90
                };
                return stressLevels[m.mood] || 50;
            });
            const avgStress = stressValues.reduce((a, b) => a + b, 0) / stressValues.length;
            data.push(avgStress);
        } else {
            data.push(0);
        }
    }
    
    // Create chart
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Stress Level',
                data: data,
                borderColor: '#ef4444',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                }
            }
        }
    });
}

// Coping strategies functionality
function applyStrategy(strategy) {
    const strategies = {
        'breathing': {
            title: 'Breathing Exercise',
            description: 'Starting 5-minute breathing exercise to help reduce anxiety...',
            duration: 300000 // 5 minutes in ms
        },
        'meditation': {
            title: 'Mindfulness',
            description: 'Beginning quick meditation session for mental clarity...',
            duration: 600000 // 10 minutes in ms
        },
        'journaling': {
            title: 'Journaling',
            description: 'Open a safe space to express and process your thoughts...',
            duration: 900000 // 15 minutes in ms
        },
        'exercise': {
            title: 'Physical Activity',
            description: 'Suggesting light exercise to release endorphins...',
            duration: 1200000 // 20 minutes in ms
        }
    };
    
    const selectedStrategy = strategies[strategy];
    if (selectedStrategy) {
        showNotification(selectedStrategy.description, 'info');
        
        // Simulate strategy execution
        setTimeout(() => {
            showNotification(`${selectedStrategy.title} completed! Take a moment to notice how you feel.`, 'success');
        }, selectedStrategy.duration);
    }
}

// AI chat functionality
function sendMentalHealthMessage() {
    const input = document.getElementById('mentalHealthInput');
    const message = input.value.trim();
    
    if (!message) {
        showNotification('Please enter a message', 'error');
        return;
    }
    
    // Add user message to chat
    addMentalHealthMessage(message, 'user');
    
    // Clear input
    input.value = '';
    
    // Generate AI response
    setTimeout(() => {
        generateAIResponse(message);
    }, 1000);
}

function addMentalHealthMessage(message, sender) {
    const messagesContainer = document.getElementById('mentalHealthMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = sender === 'user' ? 'user-message' : 'ai-message';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = `<p>${message}</p>`;
    
    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function generateAIResponse(userMessage) {
    const responses = [
        "I understand you're feeling this way. It's completely valid to experience these emotions. Would you like to try a quick breathing exercise?",
        "Thank you for sharing that with me. Based on your pattern, I've noticed work pressure has been a recurring trigger. Let's explore some coping strategies together.",
        "That sounds really challenging. Remember that stress is temporary, but your resilience is permanent. You have the strength to get through this.",
        "I appreciate you opening up about your feelings. Journaling can be really helpful for processing emotions. Would you like some prompts to get started?",
        "Your mental health is just as important as your physical health. Let's work together to find strategies that work for you."
    ];
    
    const response = responses[Math.floor(Math.random() * responses.length)];
    addMentalHealthMessage(response, 'ai');
}

// Initialize mental health section when loaded
document.addEventListener('DOMContentLoaded', function() {
    // Load mood history
    updateStressChart();
    
    // Load stress triggers from recent entries
    updateStressTriggers();
});

function updateStressTriggers() {
    const moodHistory = JSON.parse(localStorage.getItem('moodHistory') || '[]');
    const triggerCounts = {};
    
    // Analyze patterns for common triggers
    moodHistory.forEach(entry => {
        const note = entry.note ? entry.note.toLowerCase() : '';
        if (note.includes('work') || note.includes('job') || note.includes('office')) {
            triggerCounts['Work pressure'] = (triggerCounts['Work pressure'] || 0) + 1;
        }
        if (note.includes('sleep') || note.includes('tired') || note.includes('insomnia')) {
            triggerCounts['Lack of sleep'] = (triggerCounts['Lack of sleep'] || 0) + 1;
        }
        if (note.includes('social') || note.includes('people') || note.includes('anxious')) {
            triggerCounts['Social interactions'] = (triggerCounts['Social interactions'] || 0) + 1;
        }
    });
    
    // Update triggers list
    const triggersList = document.getElementById('stressTriggersList');
    if (triggersList) {
        triggersList.innerHTML = '';
        Object.entries(triggerCounts).forEach(([trigger, count]) => {
            if (count > 0) {
                const li = document.createElement('li');
                li.textContent = trigger;
                triggersList.appendChild(li);
            }
        });
    }
}






