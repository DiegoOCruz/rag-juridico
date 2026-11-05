import numpy as np
import ollama

MODELO = "bge-m3"
CONEXAO = "postgresql://rag:rag@localhost:5432/juridico"
K = 5
MODELO_RESPOSTA = "qwen3.8:27b"


def embed(textos):
    resp = ollama.embed(model=MODELO, input=textos)
    v = np.array(resp["embeddings"])
    return v / np.linalg.norm(v, axis=1, keepdims=True)

def buscar_lei(conn, pergunta, k=K):
    #print(f'k: {k}')
    q = embed([pergunta])[0]

    return conn.execute(
        """
        SELECT
            1 - (t.embedding <=> %(q)s) AS similaridade,
            a.numero_artigo,
            t.referencia,
            t.texto
        FROM trechos AS t
        JOIN artigos AS a ON a.id = t.artigo_id
        ORDER BY t.embedding <=> %(q)s
        LIMIT %(k)s
        """,
        {"q": q, "k": k},
    ).fetchall()

def buscar_multiplas(conn, perguntas, k=5):
    candidatos = {}

    for pergunta in perguntas:
        resultados = buscar_lei(conn, pergunta, k=k)

        for similaridade, numero_artigo, referencia, texto in resultados:
            chave = (numero_artigo, referencia)

            atual = candidatos.get(chave)

            if atual is None or similaridade > atual[0]:
                candidatos[chave] = (
                    similaridade,
                    numero_artigo,
                    referencia,
                    texto,
                )

    return sorted(
        candidatos.values(),
        key=lambda resultado: resultado[0],
        reverse=True,
    )[:k]


    
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