# 🧠 MyData-Copilot RAG (Node + Python + React)

A full-stack Retrieval-Augmented Generation (RAG) system built with:
- **Node.js + Express + MongoDB** — authentication, file uploads, and API backend  
- **Python FastAPI** — text extraction, vector storage (FAISS), and retrieval logic  
- **React frontend** — user dashboard, file management, and chat interface  
- Supports **dual AI models** (OpenAI + Gemini) and local fallback answers.

---

## 📁 MyData Copilot – Full Project Structure
```bash
mydata-copilot/
│
├── README.md                        # Full project overview & setup guide
├── .gitignore                       # Ignore node_modules, venv, uploads, etc.
│
├── backend/                         # 🧠 Combined backend (Node + Python)
│   │
│   ├── node-backend/                # 🟢 Node.js API server (Express + MongoDB)
│   │   ├── server.js                # Main entry file for Express app
│   │   ├── package.json
│   │   ├── .env                     # Backend environment variables
│   │   │
│   │   ├── routes/
│   │   │   ├── auth.js              # Register / Login routes
│   │   │   ├── files.js             # Upload, get, delete file routes
│   │   │   └── query.js             # Query/chat route (calls Python)
│   │   │
│   │   ├── middleware/
│   │   │   └── auth.js              # JWT verification middleware
│   │   │
│   │   ├── utils/
│   │   │   ├── mongo.js             # MongoDB connection & helpers
│   │   │   └── helpers.js (optional)
│   │   │
│   │   ├── uploads/                 # Uploaded user files (ignored in git)
│   │   │   └── (auto-generated files)
│   │   │
│   │   └── logs/                    # Optional logs
│   │
│   │
│   ├── python-rag/                  # 🐍 Python RAG + FastAPI service
│   │   ├── app.py                   # FastAPI main app (handles /chat, /process-file)
│   │   ├── requirements.txt         # Python dependencies
│   │   ├── .env                     # Python-specific environment variables
│   │   │
│   │   ├── utils/
│   │   │   ├── file_processing.py   # PDF/DOCX/TXT extraction logic
│   │   │   ├── vector_store.py      # FAISS vector store build/search/delete
│   │   │   ├── mongo_client.py      # Connects to MongoDB
│   │   │   ├── openai_client.py     # Handles OpenAI API calls
│   │   │   └── gemini_client.py     # Handles Gemini API calls
│   │   │
│   │   ├── data/
│   │   │   └── vector_stores/       # FAISS index files (auto-generated)
│   │   │
│   │   ├── logs/                    # Optional logs
│   │   └── test_scripts/            # Debug/test utilities
│   │
│   └── docker/ (optional)           # Docker configs for Mongo/Python/Node
│
│
├── frontend/                        # ⚛️ React app (Dashboard + Chat)
│   ├── package.json
│   ├── .env                         # Frontend environment variables
│   │
│   ├── public/
│   │   ├── index.html
│   │   ├── favicon.ico
│   │   └── manifest.json
│   │
│   ├── src/
│   │   ├── api/
│   │   │   └── api.js               # Handles GET/POST/upload requests with JWT
│   │   │
│   │   ├── utils/
│   │   │   └── auth.js              # Token management helpers (localStorage)
│   │   │
│   │   ├── components/
│   │   │   ├── ChatBox.jsx          # Chat interface (dual AI answers)
│   │   │   ├── FileCard.jsx         # Single file display with delete/open
│   │   │   ├── FileList.jsx         # File listing page
│   │   │   ├── Navbar.jsx           # Navigation bar (Dashboard, Files, Chat)
│   │   │   ├── Sidebar.jsx          # (Optional)
│   │   │   └── Loader.jsx           # Loader/spinner
│   │   │
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx        # Shows stats (files, pages, last upload)
│   │   │   ├── FilesPage.jsx        # Manage uploads and files
│   │   │   ├── ChatPage.jsx         # Main chat UI
│   │   │   ├── LoginPage.jsx        # Login screen
│   │   │   └── RegisterPage.jsx     # Registration screen
│   │   │
│   │   ├── styles/
│   │   │   ├── globals.css
│   │   │   ├── dashboard.css
│   │   │   ├── chat.css
│   │   │   └── files.css
│   │   │
│   │   ├── App.jsx
│   │   └── index.js
│   │
│   └── build/                       # Production build (after npm run build)
│
│
├── mongo-data/                      # Local MongoDB data (if using Docker)
└── docker-compose.yml (optional)    # To run Node + Python + Mongo together
```
---
🚀 About the Project

MyData Copilot is an intelligent document assistant that lets users upload, manage, and chat with their own files — powered by Retrieval-Augmented Generation (RAG).

It combines secure file handling, text extraction, and semantic search so you can ask natural-language questions about your documents and get instant, context-aware answers.

---

🔍 What It Does

- Secure user authentication: Each user registers and logs in with JWT-based authentication.

- Smart document uploads: Upload PDFs, DOCX, or text files directly from the web app.

- Automatic text extraction: The Python service extracts and chunks text into meaningful segments.

- Vectorized knowledge storage: Chunks are embedded and stored in FAISS + MongoDB for lightning-fast retrieval.

Conversational Q&A: Ask questions about your data and get summarized answers from:

- 💬 OpenAI (GPT-based models)

- 🤖 Gemini (Google Vertex AI models)

- Local fallback logic: If AI APIs fail or are unavailable, the system generates concise extractive summaries from retrieved chunks.

- The user can choose the answer he wants by selecting a drop down box contains MyData/ MyData + General / General answer depending upon the questions user asks.
  
- Per-user isolation: Each user’s files, chunks, and stats are securely separated in the database.

- Interactive dashboard: Track number of files, extracted pages, and upload history.

---

🧠 Why It’s Useful

Traditional chatbots don’t know your data — MyData Copilot does.
It lets teams or individuals build a private, local “AI brain” over their documents, ideal for:

- Research and note retrieval

- Legal or compliance document queries

- Internal knowledge bases

- Academic paper analysis

- Corporate training data summarization
