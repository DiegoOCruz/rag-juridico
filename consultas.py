import psycopg
from pgvector.psycopg import register_vector
import time

from config import (
    embed,
    CONEXAO,
    buscar_lei
)

if __name__ == "__main__":
    consulta = [
        "Qual dos seguintes é um direito básico do consumidor previsto no CDC?",
        "Qual é o prazo prescricional para reparação de danos causados por fato do produto ou serviço?",
        "Qual é o prazo para reclamar de vícios aparentes em produtos duráveis?",
        "Qual o prazo para o consumidor desistir de uma compra feita pela internet?",
        "O que caracteriza uma publicidade enganosa segundo o CDC?",
        "O que é considerado venda casada nas relações de consumo?",
        "Em quais situações o consumidor tem direito à restituição em dobro de valores cobrados indevidamente?",
        "A garantia legal depende de termo escrito fornecido pelo fabricante?",
        "Qual é a consequência jurídica de uma cláusula abusiva em um contrato de consumo?",
        "Quais são as opções do consumidor quando o fornecedor se recusa a cumprir uma oferta?"
    ]
    inicio = time.time()
    with psycopg.connect(CONEXAO) as conn:
        conn.execute("SET enable_seqscan = off")
        register_vector(conn)
        for c in consulta:
            print(f"\n> {c}")
            for similaridade, n_art, texto in buscar_lei(conn, c): 
                print(f"  {similaridade:.2f}  Artigo {n_art}  Texto: {texto}")
                print("-" * 80)
    fim = time.time()
    print(f"\nTempo de execução: {fim - inicio:.2f} segundos")
