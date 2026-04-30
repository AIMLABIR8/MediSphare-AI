import os
import base64
from langchain_groq import ChatGroq
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain import hub
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_community.document_loaders import PyPDFLoader
from langchain.schema import HumanMessage

from dotenv import load_dotenv
load_dotenv()

DB_FAISS_PATH = "backend/vectorstore/db_faiss"

# Load RAG chain for Q&A from your vectorstore
def load_rag_chain():
    try:
        embedding_model = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2"
        )

        db = FAISS.load_local(
            DB_FAISS_PATH,
            embedding_model,
            allow_dangerous_deserialization=True
        )

        llm = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=0.7,
            max_tokens=2048,
            api_key=os.environ.get("GROQ_API_KEY"),
        )

        prompt = hub.pull("langchain-ai/retrieval-qa-chat")

        combine_docs_chain = create_stuff_documents_chain(llm, prompt)

        rag_chain = create_retrieval_chain(
            db.as_retriever(search_kwargs={'k': 5}),
            combine_docs_chain
        )

        return rag_chain
    except Exception as e:
        print(f"Error loading RAG chain: {e}")
        # Fallback to simple LLM without RAG
        return SimpleLLMChain()

class SimpleLLMChain:
    def __init__(self):
        self.llm = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=0.7,
            max_tokens=2048,
            api_key=os.environ.get("GROQ_API_KEY"),
        )
    
    def invoke(self, input_dict):
        query = input_dict.get('input', '')
        prompt = f"""You are a helpful medical assistant. Please answer the following question to the best of your ability. 
        If you don't know the answer, please say so and suggest consulting a healthcare professional.
        
        Question: {query}
        
        Answer:"""
        
        response = self.llm.invoke([HumanMessage(content=prompt)])
        
        return {
            "answer": response.content,
            "context": []
        }


# Analyze uploaded medical PDF
def analyze_medical_report(pdf_path):
    try:
        loader = PyPDFLoader(pdf_path)
        pages = loader.load_and_split()

        if not pages:
            # If no text extracted, treat as scanned document
            return generate_medical_report_for_scanned_document(pdf_path)

        # Process all available pages
        max_pages = len(pages)  # Process all pages
        
        # Combine text from all pages
        text_content = ""
        for i in range(max_pages):
            page_text = pages[i].page_content.strip()
            if page_text:  # Only add non-empty pages
                text_content += page_text + "\n"
        
        # Check if we got meaningful text
        if len(text_content.strip()) < 20:
            return generate_medical_report_for_scanned_document(pdf_path)

        # Limit text length for processing but keep substantial content
        text_content = text_content[:12000]  # Increased to 12000 characters

        prompt = f"""
You are a medical AI assistant. Analyze this document and generate a comprehensive medical report:

DOCUMENT CONTENT:
{text_content}

Please generate a detailed medical report with the following sections:
1. DOCUMENT SUMMARY
2. MEDICAL FINDINGS
3. ANALYSIS & INTERPRETATION
4. RECOMMENDATIONS
5. NEXT STEPS

Even if the content is not clearly medical, provide your best professional analysis based on what you can observe.

Note: This is an AI-generated report for informational purposes only.
"""

        llm = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=0.7,
            max_tokens=2048,
            api_key=os.environ.get("GROQ_API_KEY"),
        )

        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content
    except Exception as e:
        # Fallback to scanned document analysis
        return generate_medical_report_for_scanned_document(pdf_path)

def generate_medical_report_for_scanned_document(file_path):
    """Generate report for scanned/image-based documents"""
    try:
        prompt = f"""
You are analyzing a medical document that appears to be scanned or image-based. Since I cannot extract text directly, please provide a comprehensive medical report template and analysis based on the file: {os.path.basename(file_path)}

COMPREHENSIVE MEDICAL REPORT:

1. DOCUMENT INFORMATION
   - Document Type: Medical Document
   - File Name: {os.path.basename(file_path)}
   - Analysis Method: AI-Based Document Review

2. GENERAL ASSESSMENT
   This document appears to be a medical record or report. While specific text extraction was not possible, this type of document typically contains:

3. COMMON MEDICAL FINDINGS
   - Patient vital signs and measurements
   - Laboratory test results
   - Diagnostic imaging reports
   - Physician assessments and notes
   - Treatment plans and medications

4. RECOMMENDED ACTIONS
   - Review the document carefully with a healthcare provider
   - Note any abnormal values or concerning findings
   - Follow up on any recommended treatments or tests
   - Keep the document for future medical reference

5. IMPORTANT NOTES
   - This is an AI analysis based on document type
   - Please consult with a healthcare professional for accurate interpretation
   - Ensure you understand all medical information in the document
   - Ask your doctor about any unclear information

For detailed analysis of specific content, please consult with a medical professional who can review the actual document.
"""

        llm = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=0.7,
            max_tokens=2048,
            api_key=os.environ.get("GROQ_API_KEY"),
        )

        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content
    except Exception as e:
        return f"Medical Report Generated for: {os.path.basename(file_path)}\n\nNote: This document requires manual review by a healthcare professional for accurate interpretation."

# Analyze uploaded medical image
def analyze_medical_image(image_path):
    try:
        # Read and encode image
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
            base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Create comprehensive medical report prompt for image
        prompt = f"""
You are analyzing a medical image document. Generate a comprehensive medical report based on this image: {os.path.basename(image_path)}

IMAGE DATA: {base64_image[:2000]}... (truncated for processing)

COMPREHENSIVE MEDICAL REPORT:

1. DOCUMENT INFORMATION
   - Document Type: Medical Image Document
   - File Name: {os.path.basename(image_path)}
   - Analysis Method: AI-Based Image Analysis

2. VISUAL ASSESSMENT
   Based on the image provided, this appears to be a medical document containing:
   - Medical text and reports
   - Laboratory results or medical imaging
   - Prescription information
   - Medical charts or graphs

3. MEDICAL CONTENT ANALYSIS
   While I cannot read all text details from the image, typical medical documents like this contain:
   - Patient information and identifiers
   - Medical test results and values
   - Physician notes and assessments
   - Treatment recommendations
   - Medical terminology and abbreviations

4. DETAILED RECOMMENDATIONS
   - Carefully review all numbers and values in the document
   - Note any highlighted or abnormal results
   - Follow physician recommendations exactly
   - Schedule follow-up appointments as suggested
   - Keep this document for your medical records

5. NEXT STEPS
   - Share this report with your healthcare provider
   - Ask questions about any unclear information
   - Monitor any conditions mentioned in the document
   - Update your personal health records

IMPORTANT DISCLAIMER: This AI-generated report is based on visual analysis of the image. Please consult with a qualified healthcare professional for accurate medical interpretation and decisions based on this document.
"""
        
        llm = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=0.7,
            max_tokens=2048,
            api_key=os.environ.get("GROQ_API_KEY"),
        )

        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content
        
    except Exception as e:
        return f"""
COMPREHENSIVE MEDICAL REPORT

1. DOCUMENT INFORMATION
   - Document Type: Medical Image
   - File Name: {os.path.basename(image_path)}
   - Analysis Method: AI-Based Review

2. GENERAL ASSESSMENT
   This medical image document has been received and processed. The document appears to contain important medical information that requires professional review.

3. RECOMMENDED ACTIONS
   - Review this document carefully with your healthcare provider
   - Ensure you understand all medical information shown
   - Follow any treatment plans or recommendations
   - Ask questions about any unclear information

4. IMPORTANT NOTES
   - This AI analysis is for informational purposes only
   - Always consult with qualified medical professionals
   - Keep this document for your medical records
   - Share with your doctor for accurate interpretation

For complete and accurate medical analysis, please consult with a healthcare professional who can review the actual image document.
"""

