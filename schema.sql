-- CREATE TABLE IF NOT EXISTS dispositivos (
--     id SERIAL PRIMARY KEY,
--     lei TEXT NOT NULL,
--     numero_art TEXT NOT NULL,
--     titulo TEXT,
--     capitulo TEXT,
--     secao TEXT,
--     anotacoes TEXT[],
--     texto TEXT NOT NULL,
--     embedding vector(1024) NOT NULL,
--     UNIQUE (lei, numero_art)
-- );
CREATE TABLE IF NOT EXISTS artigos (
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

CREATE TABLE IF NOT EXISTS trechos (
    id          SERIAL PRIMARY KEY,
    artigo_id   INTEGER NOT NULL
                REFERENCES artigos(id) ON DELETE CASCADE,
    tipo        TEXT NOT NULL
                CHECK (tipo IN ('integral', 'inciso')),
    referencia  TEXT NOT NULL,
    texto       TEXT NOT NULL,
    embedding   vector(1024) NOT NULL,
    UNIQUE (artigo_id, tipo, referencia)
);