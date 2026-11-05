import psycopg
from pgvector.psycopg import register_vector


from config import CONEXAO, embed
from extrair_artigos import (
    NOME_LEI,
    agrupar_artigos,
    ler_paragrafos,
    limpar_artigos,
    localizar_incisos,
    montar_texto,
    montar_chunk_inciso,
    montar_chunk_inciso
)

SIGLA = "CDC"
ARQUIVO = "dados/cdc.htm"


if __name__ == "__main__":
    artigos = limpar_artigos(agrupar_artigos(ler_paragrafos(ARQUIVO)))
    chunks = []

    for art in artigos:
        incisos = localizar_incisos(art)

        if incisos:
            for inciso in incisos:
                chunks.append(
                    montar_chunk_inciso(art, inciso)
                )
        else:
            chunks.append(
                {
                    "id_chunk": art["numero"],
                    "numero_art": art["numero"],
                    "texto": montar_texto(art, NOME_LEI),
                    "tipo": "integral",
                    "referencia": "completo",
                }
            )

    textos = [chunk["texto"] for chunk in chunks]
    vetores = embed(textos)
    trechos_por_artigo = {}

    for chunk, vetor in zip(chunks, vetores):
        numero_artigo = chunk["numero_art"]

        if numero_artigo not in trechos_por_artigo:
            trechos_por_artigo[numero_artigo] = []

        trechos_por_artigo[numero_artigo].append((chunk, vetor))

    with psycopg.connect(CONEXAO) as conn:
        register_vector(conn)

        with conn.cursor() as cur:
            for art in artigos:
                cur.execute(
                    """
                    INSERT INTO artigos
                        (lei, numero_artigo, titulo, capitulo, secao, anotacoes, texto)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        SIGLA,
                        art["numero"],
                        art["titulo"],
                        art["capitulo"],
                        art["secao"],
                        art["anotacoes"],
                        "\n".join(art["dispositivos"]),
                    ),
                )

                artigo_id = cur.fetchone()[0]

                for chunk, vetor in trechos_por_artigo[art["numero"]]:
                    cur.execute(
                        """
                        INSERT INTO trechos
                            (artigo_id, tipo, referencia, texto, embedding)
                        VALUES
                            (%s, %s, %s, %s, %s)
                        """,
                        (
                            artigo_id,
                            chunk["tipo"],
                            chunk["referencia"],
                            chunk["texto"],
                            vetor,
                        ),
                    )
