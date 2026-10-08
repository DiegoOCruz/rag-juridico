CREATE TABLE IF NOT EXISTS dispositivos (
    id SERIAL PRIMARY KEY,
    lei TEXT NOT NULL,
    numero_art TEXT NOT NULL,
    titulo TEXT,
    capitulo TEXT,
    secao TEXT,
    anotacoes TEXT[],
    texto TEXT NOT NULL,
    embedding vector(1024) NOT NULL,
    UNIQUE (lei, numero_art)
);