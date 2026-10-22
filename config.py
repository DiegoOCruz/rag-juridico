import numpy as np
import ollama

MODELO = "bge-m3"
CONEXAO = "postgresql://rag:rag@localhost:5432/juridico"


def embed(textos):
    resp = ollama.embed(model=MODELO, input=textos)
    v = np.array(resp["embeddings"])
    return v / np.linalg.norm(v, axis=1, keepdims=True)

def buscar_lei(conn, pergunta, k=3):
    q = embed([pergunta])[0]
    params = {"q": q, "k": k}
    where = ""

    return conn.execute(
        f"""SELECT 1 - (embedding <=> %(q)s) AS lei, numero_art, texto
            FROM dispositivos
            {where}
            ORDER BY embedding <=> %(q)s
            LIMIT %(k)s""",
        params,
    ).fetchall()
    
#     CREATE TABLE IF NOT EXISTS dispositivos (
#     id SERIAL PRIMARY KEY,
#     lei TEXT NOT NULL,
#     numero_art TEXT NOT NULL,
#     titulo TEXT,
#     capitulo TEXT,
#     secao TEXT,
#     anotacoes TEXT[],
#     texto TEXT NOT NULL,
#     embedding vector(1024) NOT NULL,
#     UNIQUE (lei, numero_art)
# );