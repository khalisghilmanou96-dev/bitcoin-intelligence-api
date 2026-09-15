CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector;
CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_search ON document_chunks USING GIN (to_tsvector('simple', content));
