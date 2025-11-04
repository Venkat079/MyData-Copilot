# 🧠 RAG Chat System (Node + Python + React)

A full-stack Retrieval-Augmented Generation (RAG) system built with:
- **Node.js + Express + MongoDB** — authentication, file uploads, and API backend  
- **Python FastAPI** — text extraction, vector storage (FAISS), and retrieval logic  
- **React frontend** — user dashboard, file management, and chat interface  
- Supports **dual AI models** (OpenAI + Gemini) and local fallback answers.

---

## 🚀 Project Structure

```bash
project-root/
│
├── node-backend/                     # Node.js + Express + MongoDB backend
│   ├── routes/                       # Auth, files, query routes
│   ├── middleware/                   # JWT auth middleware
│   ├── utils/                        # Mongo connection + helpers
│   ├── server.js                     # Express app entry point
│   └── .env.example                  # Example environment variables
│
├── python-rag/                       # Python FastAPI service (RAG processor)
│   ├── app.py
│   ├── utils/
│   │   ├── file_processing.py
│   │   ├── vector_store.py
│   │   └── mongo_client.py
│   └── requirements.txt
│
└── frontend/                         # React app (dashboard + chat)
    ├── src/
    │   ├── api/                      # API helper functions
    │   ├── utils/                    # Auth and token helpers
    │   ├── components/               # UI components (ChatBox, FileList, etc.)
    │   └── pages/
    └── .env
