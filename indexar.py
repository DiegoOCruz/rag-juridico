import psycopg
from pgvector.psycopg import register_vector

from config import CONEXAO, embed
from extrair_artigos import (
    NOME_LEI,
    agrupar_artigos,
    ler_paragrafos,
    limpar_artigos,
    montar_texto,
)

SIGLA = "CDC"
ARQUIVO = "dados/cdc.htm"


if __name__ == "__main__":
    artigos = limpar_artigos(agrupar_artigos(ler_paragrafos(ARQUIVO)))
    textos = [montar_texto(art, NOME_LEI) for art in artigos]
    vetores = embed(textos)

    with psycopg.connect(CONEXAO) as conn:
        register_vector(conn)

        with conn.cursor() as cur:
            cur.execute("DELETE FROM dispositivos WHERE lei = %s", (SIGLA,))

            for art, texto, vetor in zip(artigos, textos, vetores):
                cur.execute(
                    """INSERT INTO dispositivos
                           (lei, numero_art, titulo, capitulo, secao, anotacoes, texto, embedding)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        SIGLA,
                        art["numero"],
                        art["titulo"],
                        art["capitulo"],
                        art["secao"],
                        art["anotacoes"],
                        texto,
                        vetor,
                    ),
                )

            cur.execute("SELECT count(*) FROM dispositivos WHERE lei = %s", (SIGLA,))
            total = cur.fetchone()[0]

    print(f"{len(artigos)} artigos processados, {total} gravados no banco ({SIGLA}).")