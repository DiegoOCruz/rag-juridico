# RAG Jurídico

Busca semântica na legislação brasileira, começando pelo **Código de Defesa do Consumidor** (Lei nº 8.078/1990).

O sistema recebe uma pergunta em linguagem natural, como um advogado a faria, e encontra os artigos de lei que a respondem, mesmo quando a pergunta não usa as palavras do texto legal. Tudo roda localmente: modelos via Ollama e vetores no PostgreSQL com pgvector.


---

## Exemplo

> **Pergunta:** Qual o prazo para o consumidor desistir de uma compra feita pela internet?

| Posição | Similaridade | Artigo |
|:---:|:---:|---|
| 1º | 0,71 | **Art. 49** — direito de arrependimento em 7 dias |
| 2º | 0,62 | Art. 18 — vício do produto |
| 3º | 0,59 | Art. 26 — prazos decadenciais |

O art. 49 não menciona "internet": o texto de 1990 fala em contratação "fora do estabelecimento comercial, especialmente por telefone ou a domicílio". A busca por significado fez a mesma ponte que um advogado faz ao aplicar o artigo às compras on-line. Uma busca por palavra-chave não teria encontrado nada.

---

## Como funciona

```
HTML oficial do Planalto
        │
        ▼
extrair_artigos.py ── lê o HTML, agrupa os dispositivos por artigo,
        │              remove vetados e separa as anotações de alteração
        ▼
indexar.py ────────── monta o texto de cada artigo, gera os embeddings (bge-m3)
        │              e grava no PostgreSQL + pgvector
        ▼
consultas.py ──────── vetoriza a pergunta e busca os artigos mais próximos
                       pela distância de cosseno
```

---

## Decisões de projeto

### Fonte: HTML oficial, e não PDF
O PDF perde a estrutura do documento e não diferencia o texto em vigor do texto alterado. O HTML do Planalto preserva cada dispositivo num elemento próprio, o que permite reconstruir a hierarquia da lei. Detalhe prático: a página não declara a codificação e está em `windows-1252`, o que foi identificado e tratado na leitura.

### Delimitação da lei
O texto normativo começa no **TÍTULO I** e termina no parágrafo de fecho que começa com **"Brasília"**. A regra de fim não depende do número do último artigo, então serve para qualquer lei federal.

### Identificação dos artigos
A regex `^Art\.\s*(\d+(?:-[A-Z])?)` reconhece o início de cada artigo:

- o `^` exige que o "Art." esteja no **começo** do parágrafo, para não confundir remissões no meio do texto ("nos termos do art. 18") com artigos novos;
- o sufixo opcional aceita os artigos inseridos depois, como o **54-A** a **54-G** (superendividamento, 2021).

**Resultado:** 130 artigos (119 originais + 11 inseridos), sem lacunas nem repetições na sequência.

### Dispositivos vetados
O texto compilado mantém 42 dispositivos marcados como "(Vetado)", sem conteúdo normativo. Em todos os casos o dispositivo continha apenas o marcador, então a regra é removê-lo por inteiro. Os **12 artigos inteiramente vetados** saem da base.

**Resultado:** 130 − 12 = **118 artigos indexados**.

A numeração oficial é preservada: o art. 51 passa do inciso IV para o VI, porque o V foi vetado. Quem procura o § 4º precisa encontrar o § 4º.

### Anotações de alteração como metadado
Antes de definir a regra, todos os trechos entre parênteses foram contados e classificados:

| Tipo | Ocorrências | Tratamento |
|---|---:|---|
| Incluído pela Lei / Medida Provisória | 83 | metadado |
| Vetado | 42 | dispositivo removido |
| Redação dada pela Lei | 13 | metadado |
| Vigência | 2 | metadado |
| Números por extenso, valores, siglas, remissões | — | **permanecem no texto** |

A maioria dos parênteses é **conteúdo da lei**: "prazo de 30 (trinta) dias", "(Conmetro)", "(art. 170 da Constituição Federal)". Por isso a limpeza usa uma lista explícita do que remover, e não "remover tudo entre parênteses", o que apagaria prazos. As anotações removidas vão para uma coluna própria (`TEXT[]`), disponíveis para citação e para filtros.

### Chunking: um artigo por chunk
Incisos e alíneas isolados perdem o sentido: "a) por iniciativa direta;" só significa algo junto ao inciso e ao caput do art. 4º. Cada chunk é, portanto, um artigo completo, com caput, parágrafos, incisos e alíneas.

O texto vetorizado começa com o **nome da lei e a hierarquia**:

```
Código de Defesa do Consumidor (Lei nº 8.078/1990)
TÍTULO I Dos Direitos do Consumidor
CAPÍTULO IV Da Qualidade de Produtos e Serviços, da Prevenção e da Reparação dos Danos
SEÇÃO II Da Responsabilidade pelo Fato do Produto e do Serviço
Art. 17. Para os efeitos desta Seção, equiparam-se aos consumidores todas as vítimas do evento.
```

Sem a hierarquia, o "desta Seção" do art. 17 não teria referência. Com o nome da lei, o art. 18 do CDC não se confunde com o art. 18 de outros códigos quando a base crescer.

O maior artigo (art. 51, cerca de 3 mil caracteres) cabe com folga no limite do modelo de embeddings.

### Um banco para todas as leis
As leis se relacionam, e uma pergunta pode ter resposta em mais de uma. Por isso há um único banco, com a lei como coluna, em vez de um banco por lei. Assim é possível buscar em toda a legislação ou filtrar uma só (`WHERE lei = 'CDC'`) na mesma consulta.

```sql
CREATE TABLE dispositivos (
    id         SERIAL PRIMARY KEY,
    lei        TEXT NOT NULL,
    numero_art TEXT NOT NULL,          -- texto, para aceitar "54-A"
    titulo     TEXT,
    capitulo   TEXT,
    secao      TEXT,
    anotacoes  TEXT[],
    texto      TEXT NOT NULL,
    embedding  vector(1024) NOT NULL,
    UNIQUE (lei, numero_art)
);
```

### Indexação idempotente
A reindexação apaga **apenas as linhas da lei** que está sendo processada e grava de novo, numa única transação. O banco fica sempre igual à versão atual da lei, inclusive se um artigo deixar de existir, e as demais leis não são afetadas. A restrição `UNIQUE (lei, numero_art)` funciona como teste automático da extração: um artigo duplicado gera erro, em vez de passar em silêncio.

---

## Avaliação

Conjunto inicial de 10 perguntas escritas por mim, cada uma com o artigo esperado.

| Pergunta (resumo) | Esperado | Posição |
|---|:---:|:---:|
| Direito básico do consumidor | 6 | 1º |
| Prescrição por fato do produto | 27 | 1º |
| Vício aparente em produto durável | 26 | 1º (empate com o 18) |
| Desistência de compra pela internet | 49 | 1º |
| Publicidade enganosa | 37 | 1º |
| Venda casada | 39, I | 3º |
| Restituição em dobro | 42 | 1º |
| Garantia legal depende de termo escrito? | 24 | 2º |
| Consequência da cláusula abusiva | 51 | 1º |
| Recusa em cumprir a oferta | 35 | 1º |

**Acerto no topo: 8/10 · Acerto entre os 3 primeiros: 10/10**

Os erros são os casos mais informativos:

- **Venda casada.** O termo é da prática e da doutrina, não da lei: o art. 39, I fala em "condicionar o fornecimento de produto ou de serviço ao fornecimento de outro". Além disso, o inciso fica diluído num artigo com 14 incisos. Os scores ficaram baixos (~0,45), sinal de baixa confiança.
- **Garantia legal.** O art. 50 ("garantia contratual... mediante termo escrito") ficou à frente do art. 24 ("a garantia legal... **independe** de termo expresso") por repetir as palavras da pergunta. Embeddings captam bem o assunto, mas mal a negação.

---

## Limitações conhecidas

- Artigos em forma de lista (arts. 6º, 39 e 51) concentram muitos assuntos num único vetor, o que dificulta encontrar um inciso específico.
- Dois resíduos de limpeza: um "Vigência" sem parênteses no art. 6º, III, e uma nota editorial do Planalto no art. 39, XI.
- As anotações ficam no nível do artigo, sem indicar qual dispositivo foi alterado.
- O conjunto de avaliação ainda é pequeno e não inclui perguntas sem resposta no CDC.

## Próximos passos

- [ ] Avaliação automatizada (`avaliacao.csv` + script de métricas), com mais perguntas em linguagem do dia a dia e perguntas sem resposta na lei
- [ ] Corrigir os resíduos de limpeza e medir o efeito
- [ ] Chunks adicionais por inciso nos artigos-lista, sempre com o caput, comparando com a avaliação
- [ ] Geração da resposta com LLM, **citando o artigo** que a fundamenta
- [ ] Incluir o Código Civil e outras leis

---

## Tecnologias

Python · BeautifulSoup · PostgreSQL 17 · pgvector · Ollama (`bge-m3` para embeddings) · psycopg 3 · numpy · Docker

## Como executar

```bash
# banco com pgvector
docker run -d --name pgvector \
  -e POSTGRES_USER=rag -e POSTGRES_PASSWORD=rag -e POSTGRES_DB=rag \
  -p 5432:5432 -v pgdata:/var/lib/postgresql/data \
  pgvector/pgvector:pg17

docker exec -it pgvector psql -U rag -d rag -c "CREATE DATABASE juridico;"
docker exec -it pgvector psql -U rag -d juridico -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker exec -i pgvector psql -U rag -d juridico < schema.sql

# modelo de embeddings
ollama pull bge-m3

# dependências
python -m venv .venv && source .venv/bin/activate
pip install ollama numpy "psycopg[binary]" pgvector beautifulsoup4

# texto da lei (não versionado)
mkdir -p dados
curl -L -A "Mozilla/5.0" -o dados/cdc.htm \
  https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm

# indexação e consulta
python indexar.py
python consultas.py
```
