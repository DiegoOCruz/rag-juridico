import numpy as np
import ollama

MODELO = "bge-m3"
CONEXAO = "postgresql://rag:rag@localhost:5432/juridico"


def embed(textos):
    resp = ollama.embed(model=MODELO, input=textos)
    v = np.array(resp["embeddings"])
    return v / np.linalg.norm(v, axis=1, keepdims=True)