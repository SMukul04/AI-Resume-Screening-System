# AI Resume Screening System

## 🚀 Overview
This project is an AI-powered resume screening system that automatically ranks resumes based on their relevance to a job description using NLP and semantic similarity.

## 🔍 Features
- Upload multiple resumes (PDF/DOC)
- Extract text using PyMuPDF
- AI-based semantic matching (Sentence Transformers)
- Candidate ranking using cosine similarity
- Dashboard with insights & screening history

## 🧠 How It Works
1. Job description and resumes are converted into embeddings
2. Cosine similarity is used to measure relevance
3. Candidates are ranked based on similarity score

## 🛠 Tech Stack
- Python (Flask)
- NLP (Sentence Transformers)
- Scikit-learn
- HTML, CSS, JavaScript

## ▶️ How to Run

pip install -r requirements.txt  
python app.py  

Then open:  
http://127.0.0.1:5000

## 📌 Future Improvements
- Add database (MongoDB/MySQL)
- Improve UI/UX
- Add authentication system
