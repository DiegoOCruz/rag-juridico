import ollama
import psycopg
from pgvector.psycopg import register_vector
import json

from config import CONEXAO, buscar_multiplas, MODELO_RESPOSTA




# PERGUNTA = (
#     # "Fui fazer o financiamento de um carro e a loja quer "
#     # "que eu faça um seguro com eles, mas não quero. Isso é legal?"
#     "Qual é o prazo para contestar uma multa de trânsito?"
# )

# CONSULTAS_BUSCA = [
#     PERGUNTA,
#     (
#         "É abusivo condicionar o fornecimento de um produto ou serviço "
#         "ao fornecimento de outro produto ou serviço."
#     ),
# ]
#PERGUNTA = input("Digite sua pergunta: ").strip().lower()
PERGUNTA = "É abusivo condicionar o fornecimento de um produto ou serviço ao fornecimento de outro?"

CONSULTAS_BUSCA = [PERGUNTA]

# consulta_auxiliar = input(
#     "Digite uma formulação jurídica auxiliar (opcional): "
# ).strip()
# consulta_auxiliar = input(
#     "Digite uma formulação jurídica auxiliar (opcional): "
# ).strip()
consulta_auxiliar = ""

if consulta_auxiliar:
    CONSULTAS_BUSCA.append(consulta_auxiliar)


with psycopg.connect(CONEXAO) as conn:
    register_vector(conn)

    resultados = buscar_multiplas(
        conn,
        CONSULTAS_BUSCA,
        k=1,
    )


contexto = "\n\n---\n\n".join(
    f"Artigo {numero_artigo}-{referencia}:\n{texto}"
    for similaridade, numero_artigo, referencia, texto in resultados
)
referencias_disponiveis = ", ".join(
    f"{numero_artigo}-{referencia}"
    for similaridade, numero_artigo, referencia, texto in resultados
)
artigo_principal = resultados[0][1]

fontes = [
    resultado
    for resultado in resultados
    if resultado[1] == artigo_principal
]

prompt = f"""
Responda à pergunta usando somente o contexto jurídico fornecido.

Pergunta:
{PERGUNTA}

Contexto:
{contexto}

Referências disponíveis no contexto:
{referencias_disponiveis}

Regras adicionais:
- Não cite números de artigos ou incisos na resposta;
- A aplicação adicionará as fontes separadamente;
- não reproduza texto que não esteja nos trechos fornecidos;
- se uma informação não estiver nos trechos, diga que ela não foi fornecida;
"""

formato_resposta = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["answer", "abstain"],
        },
        "text": {
            "type": "string",
        },
    },
    "required": ["status", "text"],
}

resposta = ollama.chat(
    model=MODELO_RESPOSTA,
    messages=[
        {
            "role": "user",
            "content": prompt
            + """
Retorne somente um objeto JSON.
Use "status": "answer" quando o contexto permitir responder.
Use "status": "abstain" quando o contexto não for suficiente.
Não inclua citações de artigos no campo "text".
""",
        }
    ],
    format=formato_resposta,
    options={
        "temperature": 0,
    },
)

dados = json.loads(resposta["message"]["content"])
resposta_texto = dados["text"].strip()

if resposta_texto.lower().startswith("answer:"):
    resposta_texto = resposta_texto.split(":", 1)[1].strip()

print(f"Pergunta: {PERGUNTA}")

if dados["status"] == "answer":
    print("Sources:")

    for similaridade, numero_artigo, referencia, texto_trecho in fontes:
        print(f"- CDC, Art. {numero_artigo}-{referencia}")

    print(resposta_texto)

elif dados["status"] == "abstain":
    print(resposta_texto)

else:
    print("Status inválido; as fontes não serão exibidas.")

