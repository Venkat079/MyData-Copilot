# python-rag/utils/embeddings.py
import os
import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model

def embed_texts(texts):
    """
    texts: List[str]
    returns: numpy array shape (len(texts), dim)
    """
    if not texts:
        import numpy as _np
        return _np.zeros((0, get_model().get_sentence_embedding_dimension()))
    model = get_model()
    embs = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return embs
