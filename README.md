# Legal RAG

Semantic search over Brazilian legislation, starting with the Consumer Protection Code (Código de Defesa do Consumidor — CDC, Law No. 8,078/1990).

The system receives a natural-language question and retrieves the legal passages most relevant to it. Everything runs locally, using Ollama for models and PostgreSQL with pgvector for vector search.

## How it works

```text
Official Planalto HTML
        ↓
extrair_artigos.py  →  parse, clean and organize legal articles
        ↓
indexar.py          →  create articles, passages and embeddings
        ↓
consultas.py        →  retrieve passages by cosine similarity
        ↓
responder.py        →  generate a grounded answer with a local model
```

## Project decisions

### Official HTML source

The Planalto HTML preserves the document structure and separates legal provisions into elements. The source file uses `windows-1252`, which is handled explicitly during parsing. The normative text starts at **TÍTULO I** and ends at the closing paragraph beginning with **“Brasília”**.

### Article extraction

The expression `^Art\.\s*(\d+(?:-[A-Z])?)` recognizes article beginnings. The `^` prevents references such as “art. 18” in the middle of a paragraph from being treated as new articles, while the optional suffix supports inserted articles such as 54-A through 54-G.

The source contains 130 articles. Twelve are entirely vetoed, leaving **118 indexed articles**.

Annotations such as “Incluído pela Lei”, “Redação dada” and “Vigência” are stored as metadata. Legal content inside parentheses — for example “30 (trinta) dias” or “(Conmetro)” — remains in the text.

### Chunking: complete articles and searchable passages

The database has two responsibilities:

- `artigos` stores each complete article and its metadata;
- `trechos` stores the units used for vector retrieval.

Current rules:

- an article without incisos produces one `integral` passage;
- an article with incisos produces one passage per inciso, including the caput;
- an inciso inside a paragraph also includes its parent paragraph.

This prevents identical inciso numbers from being confused:

```text
12-§1-I
12-§3-I
```

The complete article remains available in `artigos`. Paragraphs and alíneas are not separate searchable units yet. Every searchable passage starts with the law name and legal hierarchy.

The CDC is currently indexed as **118 articles and 258 passages**. Article 39 has 13 inciso passages; Article 12 has six passages, from `§1-I` to `§3-III`.

### Database model

```sql
CREATE TABLE artigos (
    id             SERIAL PRIMARY KEY,
    lei            TEXT NOT NULL,
    numero_artigo  TEXT NOT NULL,
    titulo         TEXT,
    capitulo       TEXT,
    secao          TEXT,
    anotacoes      TEXT[],
    texto          TEXT NOT NULL,
    UNIQUE (lei, numero_artigo)
);

CREATE TABLE trechos (
    id          SERIAL PRIMARY KEY,
    artigo_id   INTEGER NOT NULL REFERENCES artigos(id) ON DELETE CASCADE,
    tipo        TEXT NOT NULL CHECK (tipo IN ('integral', 'inciso')),
    referencia  TEXT NOT NULL,
    texto       TEXT NOT NULL,
    embedding   vector(1024) NOT NULL,
    UNIQUE (artigo_id, tipo, referencia)
);
```

`artigos` is the complete legal source; `trechos` is the retrieval layer. Reindexing is scoped to the law being processed and runs in one transaction. Uniqueness constraints make duplicate extraction errors visible.

## Evaluation

The evaluation set contains 15 questions: 14 with an expected article and one question without an expected CDC answer.

Before passage-level indexing, the baseline was **11/14 (78.57%)** with `k=1`. The current evaluation reports:

- **Top-1:** the first result is the expected article;
- **Recall@5:** the expected article appears among the five results.

Current result:

```text
Top-1:    10/14 (71.43%)
Recall@5: 12/14 (85.71%)
```

Finer-grained indexing improved coverage but sometimes moved the best result down the ranking. Article 35, for example, appears second for the question about an incorrectly advertised price.

### Multi-query retrieval pilot

A question written in everyday language about insurance and financing did not retrieve Article 39 in the top ten. When the system also searched a separate legal formulation — “conditioning the provision of one service on the provision of another” — passage `39-I` ranked first with a similarity of `0.71`.

The same happened for a question explicitly about tied selling. This indicates a vocabulary gap between everyday language and legal drafting. The pilot is not part of the official benchmark because the legal reformulation was supplied manually.

### Answer-generation prototype

`responder.py` uses retrieved passages as context for a local `qwen3.8:27b` model. With the relevant `39-I` passage available, the model generated an answer citing the provision. For a question outside the CDC, it correctly stated that the supplied context was insufficient instead of inventing an answer.

### Structural limitation identified

Vector search performs well when the question resembles the legal wording. It does not consistently bridge a common-language situation to the corresponding legal concept. The language model can explain retrieved passages, but it may still cite provisions that were not retrieved, even with low temperature and restrictive prompts.

```text
Direct legal wording   → consistent retrieval
Everyday wording       → requires a specialized bridge
Retrieved passages     → useful for explanation
Citations              → must be validated by the application
```

A more reliable legal system will need hybrid or lexical search, legal vocabulary/query rewriting, and programmatic citation validation.

## Known limitations

- Several passages from the same article may occupy consecutive ranks, reducing result diversity.
- The current benchmark evaluates article numbers, not exact passage references. `26-I` can therefore count as correct for a question whose specific answer is `26-II`.
- The evaluation set is still small and does not yet measure abstention as a formal metric.
- Legislative annotations are stored at article level, without identifying the exact amended provision.

## Next steps

- [x] Parse and clean the CDC HTML
- [x] Separate `artigos` and `trechos`
- [x] Index 118 articles and 258 passages
- [x] Adapt retrieval to search passages and recover the related article
- [x] Measure Top-1 and Recall@5
- [x] Prototype grounded answer generation with Qwen
- [x] Test abstention when the context is insufficient
- [ ] Evaluate exact passage references such as `26-II` and `39-I`
- [ ] Test reranking and hybrid retrieval
- [ ] Generalize query rewriting without manually changing official test questions
- [ ] Validate citations programmatically
- [ ] Add the Civil Code and other legislation

## Technology

Python · BeautifulSoup · PostgreSQL 17 · pgvector · Ollama (`bge-m3` embeddings) · psycopg 3 · NumPy · Docker

## Running the project

```bash
docker run -d --name pgvector -e POSTGRES_USER=rag -e POSTGRES_PASSWORD=rag -e POSTGRES_DB=rag -p 5432:5432 -v pgdata:/var/lib/postgresql/data pgvector/pgvector:pg17
docker exec -it pgvector psql -U rag -d rag -c "CREATE DATABASE juridico;"
docker exec -it pgvector psql -U rag -d juridico -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker exec -i pgvector psql -U rag -d juridico < schema.sql
ollama pull bge-m3
python -m venv .venv
source .venv/bin/activate
pip install ollama numpy "psycopg[binary]" pgvector beautifulsoup4
mkdir -p dados
curl -L -A "Mozilla/5.0" -o dados/cdc.htm https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm
python indexar.py
python consultas.py
python avaliar.py
```
