-- MateScale RAG — Postgres schema.
--
-- Runs on the VectorChord image (which bundles pgvector). Patch embeddings use
-- pgvector's dimension-free `vector` type (robust to the model's projection dim);
-- VectorChord's native MaxSim is the documented scale-up, swappable behind the
-- VectorStore protocol. The property graph is plain relational tables.
CREATE EXTENSION IF NOT EXISTS vector;
-- VectorChord (native multi-vector MaxSim) — present in the VectorChord image.
-- Non-fatal if absent so the schema also applies on a plain pgvector server.
DO $$ BEGIN
    CREATE EXTENSION IF NOT EXISTS vchord CASCADE;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'vchord extension unavailable (ok on pgvector-only): %', SQLERRM;
END $$;
-- --------------------------------------------------------------------------- --
-- Corpus
-- --------------------------------------------------------------------------- --
CREATE TABLE IF NOT EXISTS documents (
    doc_id     text PRIMARY KEY,
    title      text NOT NULL DEFAULT '',
    path       text NOT NULL DEFAULT '',
    pages      int  NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS pages (
    doc_id     text NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    page       int  NOT NULL,
    image_path text NOT NULL DEFAULT '',
    content    text NOT NULL DEFAULT '',   -- OCR (DeepSeek-OCR-2) / PDFium text
    pooled     vector,                     -- mean-pooled page vector (ANN candidate gen)
    PRIMARY KEY (doc_id, page)
);
-- One row per ColModernVBERT patch vector (late interaction / MaxSim).
CREATE TABLE IF NOT EXISTS page_patches (
    id        bigserial PRIMARY KEY,
    doc_id    text NOT NULL,
    page      int  NOT NULL,
    patch_idx int  NOT NULL,
    embedding vector NOT NULL,
    FOREIGN KEY (doc_id, page) REFERENCES pages(doc_id, page) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS page_patches_doc_page ON page_patches (doc_id, page);
-- --------------------------------------------------------------------------- --
-- Property graph (LLM-harvested). Summaries/metadata live in the OKF bundle.
-- --------------------------------------------------------------------------- --
CREATE TABLE IF NOT EXISTS entities (
    id          bigserial PRIMARY KEY,
    name        text NOT NULL,
    name_key    text NOT NULL UNIQUE,       -- lower(name) — merge key
    type        text NOT NULL DEFAULT '',
    description text NOT NULL DEFAULT '',
    doc_id      text,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS relations (
    id          bigserial PRIMARY KEY,
    source_key  text NOT NULL,
    target_key  text NOT NULL,
    type        text NOT NULL DEFAULT '',
    description text NOT NULL DEFAULT '',
    doc_id      text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_key, target_key, type)
);
CREATE INDEX IF NOT EXISTS relations_source ON relations (source_key);
CREATE INDEX IF NOT EXISTS relations_target ON relations (target_key);
-- Provenance: which document/page each entity was harvested from. Entities and
-- relations merge globally (by name), so page-level provenance lives here.
CREATE TABLE IF NOT EXISTS entity_mentions (
    name_key text NOT NULL,
    doc_id   text NOT NULL,
    page     int  NOT NULL,
    PRIMARY KEY (name_key, doc_id, page)
);
CREATE INDEX IF NOT EXISTS entity_mentions_name ON entity_mentions (name_key);
CREATE INDEX IF NOT EXISTS entity_mentions_doc ON entity_mentions (doc_id);
