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
        │              remove vetados, anotações e identifica a hierarquia
        ▼
indexar.py ────────── monta artigos e trechos pesquisáveis, gera embeddings
        │              (bge-m3) e grava no PostgreSQL + pgvector
        ▼
consultas.py ──────── vetoriza a pergunta e busca os trechos mais próximos
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

### Chunking: artigo completo e trechos por inciso
O banco separa duas funções:

- `artigos` preserva cada artigo completo, com seus metadados;
- `trechos` guarda as unidades que participam da busca vetorial.

A regra atual é:

- artigo sem incisos: um trecho `integral` com o artigo completo;
- artigo com incisos: um trecho para cada inciso, sempre com o caput;
- inciso dentro de parágrafo: o parágrafo pai também entra no trecho.

Por isso, os dois incisos abaixo têm referências diferentes:

```text
12-§1-I
12-§3-I
```

Incisos com o mesmo algarismo em parágrafos diferentes não são confundidos. Parágrafos e alíneas ainda permanecem no texto completo do artigo; a divisão específica por alínea fica para uma etapa futura.

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

### Resultado da indexação por trechos
O CDC foi indexado com **118 artigos** e **258 trechos**. O art. 39, por exemplo, possui 13 trechos de inciso; o art. 12 possui seis, com referências `§1-I` a `§3-III`.

### Um banco para todas as leis
As leis se relacionam, e uma pergunta pode ter resposta em mais de uma. Por isso há um único banco, com a lei como coluna, em vez de um banco por lei. Assim é possível buscar em toda a legislação ou filtrar uma só (`WHERE lei = 'CDC'`) na mesma consulta.

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

`artigos` é a fonte completa; `trechos` é a camada de recuperação. A chave estrangeira faz cada trecho apontar para seu artigo, e `ON DELETE CASCADE` remove os trechos quando o artigo é removido.

### Indexação idempotente
A reindexação apaga **apenas as linhas da lei** que está sendo processada e grava de novo, numa única transação. O banco fica sempre igual à versão atual da lei, inclusive se um artigo deixar de existir, e as demais leis não são afetadas. As restrições de unicidade de `artigos` e `trechos` funcionam como testes automáticos da extração: uma duplicidade gera erro, em vez de passar em silêncio.

---

## Avaliação

O conjunto inicial tinha 10 perguntas. Nessa primeira rodada, o artigo esperado ficou em primeiro em 8/10 casos e entre os três primeiros em 10/10.

A avaliação ampliada está em `avaliacao.csv` e é executada com `python avaliar.py`. Ela contém 15 perguntas: 14 com artigo esperado e uma sem resposta esperada no CDC.

Antes da divisão em trechos, o baseline era **11/14 (78,57%)** com `k=1`. Depois da indexação atual, a avaliação mede duas dimensões:

- **Top-1:** o primeiro resultado é o artigo esperado;
- **Recall@5:** o artigo esperado aparece entre os cinco resultados.

Resultado atual: **Top-1 = 10/14 (71,43%)** e **Recall@5 = 12/14 (85,71%)**.

O art. 35, por exemplo, aparece em segundo lugar na pergunta sobre preço anunciado. As duas falhas que não chegam ao top 5 são venda casada e seguro vinculado a financiamento, ambas esperadas no art. 39.

### Piloto de múltiplas consultas

Uma pergunta cotidiana sobre seguro e financiamento não recuperou o art. 39 no top 10. Quando a busca recebeu também uma consulta separada com a redação jurídica do dispositivo, o `39-I` ficou em primeiro, com similaridade `0,71`.

O mesmo resultado ocorreu para a pergunta sobre venda casada. Isso indica uma lacuna entre a linguagem cotidiana e a redação legal, e mostra que combinar consultas independentes pode melhorar a recuperação. Esse piloto ainda não foi aplicado à avaliação oficial, para não introduzir manualmente informação jurídica nas perguntas de teste.

### Primeiro protótipo de resposta

O `responder.py` usa os trechos recuperados como contexto para o modelo `qwen3.8:27b`. No caso do seguro condicionado ao financiamento, o modelo recuperou o `39-I` e respondeu citando o artigo.

Também foi testada uma pergunta fora do escopo do CDC (prazo para contestar multa de trânsito). Mesmo recebendo trechos semanticamente próximos, o modelo informou que o contexto não era suficiente e não inventou uma resposta. Essa abstenção é um requisito de segurança do RAG.

### Limitação estrutural identificada

Os experimentos mostraram que a busca vetorial funciona bem quando a pergunta usa uma formulação próxima da redação legal. Ela tem dificuldade, porém, de fazer sozinha a ponte entre uma situação cotidiana e o conceito jurídico correspondente. Por exemplo, “a loja quer obrigar um seguro junto com o financiamento” não recupera consistentemente o `39-I`, enquanto a formulação “condicionar o fornecimento de um produto ou serviço ao fornecimento de outro” recupera esse trecho em primeiro lugar.

A geração também não deve ser tratada como fonte jurídica: mesmo com temperatura baixa e um prompt restritivo, o modelo pode citar dispositivos que não foram recuperados. Por isso, temperatura e `k` não resolvem isoladamente o problema.

Conclusão do protótipo:

```text
redação jurídica direta → recuperação consistente
pergunta cotidiana      → depende de uma ponte especializada
trechos recuperados     → modelo consegue explicar e resumir
citações                → devem ser validadas pelo programa
```

Uma versão mais confiável precisará combinar busca vetorial com busca lexical ou híbrida, vocabulário jurídico/reescrita de consulta e validação programática das citações.

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

**Resultado da rodada inicial: acerto no topo 8/10 · acerto entre os 3 primeiros 10/10**

Na rodada inicial, os erros mais informativos foram:

- **Venda casada.** O termo é da prática e da doutrina, não da lei: o art. 39, I fala em "condicionar o fornecimento de produto ou de serviço ao fornecimento de outro". Além disso, o inciso fica diluído num artigo com 14 incisos. Os scores ficaram baixos (~0,45), sinal de baixa confiança.
- **Garantia legal.** O art. 50 ("garantia contratual... mediante termo escrito") ficou à frente do art. 24 ("a garantia legal... **independe** de termo expresso") por repetir as palavras da pergunta. Embeddings captam bem o assunto, mas mal a negação.

---

## Limitações conhecidas

- Vários trechos do mesmo artigo podem ocupar posições consecutivas; isso melhora a cobertura, mas reduz a diversidade dos resultados.
- A avaliação atual ainda compara o número do artigo, não a referência exata do trecho. Assim, `26-I` pode contar como acerto para uma pergunta cuja resposta específica está em `26-II`.
- As anotações ficam no nível do artigo, sem indicar qual dispositivo foi alterado.
- O conjunto de avaliação ainda é pequeno. Há uma pergunta sem artigo esperado no CDC, mas o buscador ainda retorna o artigo mais próximo e não avalia abstenção.

## Próximos passos

- [x] Avaliação ampliada em `avaliacao.csv` e execução por `avaliar.py`
- [x] Corrigir os resíduos de limpeza no art. 6º, III, e no art. 39, XI, e medir o efeito; o resultado permaneceu em 11/14
- [x] Separar `artigos` e `trechos` no banco
- [x] Indexar os 118 artigos e 258 trechos
- [x] Adaptar a busca para consultar `trechos` e recuperar o artigo relacionado
- [x] Medir Top-1 e Recall@5
- [ ] Testar `k=10` nas duas perguntas que não recuperam o art. 39 no top 5
- [ ] Ampliar a avaliação para o identificador exato do trecho (`26-II`, `39-I` etc.)
- [ ] Estudar reordenação/reranking para melhorar o Top-1
- [ ] Avaliar múltiplas consultas sem alterar artificialmente o conjunto oficial de perguntas
- [x] Protótipo de resposta com Qwen e citação do trecho recuperado
- [x] Teste de abstenção quando o contexto não responde à pergunta
- [x] Documentar a limitação da busca semântica e da geração livre
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
python avaliar.py
```
