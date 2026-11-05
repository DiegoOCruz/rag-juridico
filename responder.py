import ollama
import psycopg
from pgvector.psycopg import register_vector

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
PERGUNTA = "A loja quer me obrigar a contratar um seguro junto com o financiamento."

CONSULTAS_BUSCA = [PERGUNTA]

# consulta_auxiliar = input(
#     "Digite uma formulação jurídica auxiliar (opcional): "
# ).strip()
consulta_auxiliar = "É abusivo condicionar o fornecimento de um produto ou serviço à contratação de outro."

if consulta_auxiliar:
    CONSULTAS_BUSCA.append(consulta_auxiliar)


with psycopg.connect(CONEXAO) as conn:
    register_vector(conn)

    resultados = buscar_multiplas(
        conn,
        CONSULTAS_BUSCA,
        k=5,
    )


contexto = "\n\n---\n\n".join(
    f"Artigo {numero_artigo}-{referencia}:\n{texto}"
    for similaridade, numero_artigo, referencia, texto in resultados
)
referencias_disponiveis = ", ".join(
    f"{numero_artigo}-{referencia}"
    for similaridade, numero_artigo, referencia, texto in resultados
)

prompt = f"""
Responda à pergunta usando somente o contexto jurídico fornecido.

Pergunta:
{PERGUNTA}

Contexto:
{contexto}

Referências disponíveis no contexto:
{referencias_disponiveis}

Regras adicionais:
- só cite artigos e incisos que aparecem nessa lista;
- não cite outros incisos, mesmo que você conheça o CDC;
- não reproduza texto que não esteja nos trechos fornecidos;
- se uma informação não estiver nos trechos, diga que ela não foi fornecida.
 se uma informação não estiver nos trechos, diga que ela não foi fornecida.
"""

resposta = ollama.chat(
    model=MODELO_RESPOSTA,
    messages=[
        {
            "role": "user",
            "content": prompt,
        }
    ],
    options={
        "temperature": 0,
    },
)
print(f'Pergunta: {PERGUNTA}')
print(resposta["message"]["content"])