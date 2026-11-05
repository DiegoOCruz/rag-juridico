import csv
import psycopg
from pgvector.psycopg import register_vector
import time

from config import (
    embed,
    CONEXAO,
    buscar_lei,
    buscar_multiplas
)

CAMINHO_ARQUIVO = 'avaliacao.csv'

def ler_arquivo(arquivo):
    with open(arquivo, 'r', encoding='utf-8') as f:
        next(f)  # Pular o cabeçalho
        leitor = csv.reader(f)
        return list(leitor)


if __name__ == "__main__":
    perguntas = ler_arquivo(CAMINHO_ARQUIVO)

    acertos_top1 = 0
    acertos_top5 = 0
    total = sum(1 for p in perguntas if p[1].strip())

    inicio = time.time()

    with psycopg.connect(CONEXAO) as conn:
        conn.execute("SET enable_seqscan = off")
        register_vector(conn)

            #resultados = buscar_lei(conn, pergunta, k=5)
        for p in perguntas:
            pergunta = p[0]
            esperado = p[1].strip()

            print(f"\n> {pergunta}")

            resultados = buscar_lei(conn, pergunta, k=5)

            for posicao, (similaridade, n_art, referencia, texto) in enumerate(
                resultados,
                start=1,
            ):
                print(
                    f"{posicao}º  {similaridade:.2f}  "
                    f"Artigo {n_art}-{referencia}"
                )

            if esperado:
                artigos_retornados = [
                    n_art
                    for similaridade, n_art, referencia, texto in resultados
                ]

                if artigos_retornados[0] == esperado:
                    acertos_top1 += 1

                if esperado in artigos_retornados:
                    acertos_top5 += 1

                print(f"Esperado: Art. {esperado}")

            print("-" * 80)

    fim = time.time()

    print(
        f"\nTop-1: {acertos_top1}/{total} "
        f"({(acertos_top1 / total) * 100:.2f}%)"
    )
    print(
        f"Recall@5: {acertos_top5}/{total} "
        f"({(acertos_top5 / total) * 100:.2f}%)"
    )
    print(f"\nTempo de execução: {fim - inicio:.2f} segundos")