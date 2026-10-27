import csv
import psycopg
from pgvector.psycopg import register_vector
import time

from config import (
    embed,
    CONEXAO,
    buscar_lei
)

CAMINHO_ARQUIVO = 'avaliacao.csv'

def ler_arquivo(arquivo):
    with open(arquivo, 'r', encoding='utf-8') as f:
        next(f)  # Pular o cabeçalho
        leitor = csv.reader(f)
        return list(leitor)


if __name__ == "__main__":
    perguntas = ler_arquivo(CAMINHO_ARQUIVO)
    acerto = 0
    total = sum(1 for p in perguntas if p[1].strip()) 
    inicio = time.time()
    with psycopg.connect(CONEXAO) as conn:
        conn.execute("SET enable_seqscan = off")
        register_vector(conn)
        for p in perguntas:
            print(f"\n> {p[0]}")
            for similaridade, n_art, texto in buscar_lei(conn, p[0]):
                print(f"Art. esperado: {p[1]}  Art. retornado: {n_art}") 
                if p[1]:
                    if n_art == p[1]:
                        acerto += 1
                    print(f"  {similaridade:.2f}  Artigo {n_art}  Texto: {texto}")
                    print(f"Texto: {texto}")
            print("-" * 80)
    fim = time.time()
    print(f"\nAcertos: {acerto}/{total} ({(acerto/total)*100:.2f}%)")
    print(f"\nTempo de execução: {fim - inicio:.2f} segundos")