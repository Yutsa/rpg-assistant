export interface Campaign {
  id: string;
  title: string;
  game_system: string;
  created_at: string | null;
  updated_at: string | null;
  document_count: number;
}

export interface Document {
  id: string;
  campaign_id: string;
  filename: string;
  page_count: number;
  content_hash: string;
  created_at: string | null;
  section_count: number;
  chunk_count: number;
  latest_ingestion_run_id: string | null;
  latest_ingestion_status: string | null;
}

export interface CampaignSummary {
  campaign_id: string;
  document_count: number;
  section_count: number;
  chunk_count: number;
  chunks_total: number;
  chunks_classified: number;
  entities: number;
  relations: number;
  low_confidence_entities: number;
  needs_review: number;
}

export interface Section {
  id: string;
  campaign_id: string;
  document_id: string;
  parent_section_id: string | null;
  title: string;
  level: number;
  page_start: number;
  page_end: number;
}

export interface ChunkListItem {
  id: string;
  section_id: string | null;
  page_start: number;
  page_end: number;
  chunk_type: string | null;
  chunk_type_hint: string | null;
  token_count: number;
  needs_rechunk: boolean;
  text_preview: string;
}

export interface SourceSpan {
  page: number;
  page_block_ids: string[];
  bbox: { x0: number; y0: number; x1: number; y1: number } | null;
}

export interface Chunk {
  id: string;
  campaign_id: string;
  document_id: string;
  section_id: string | null;
  page_start: number;
  page_end: number;
  text: string;
  chunk_type: string | null;
  chunk_type_hint: string | null;
  token_count: number;
  source_spans: SourceSpan[];
  metadata: Record<string, unknown>;
  needs_rechunk: boolean;
}

export interface StatBlockIndex {
  name: string;
  nc: number | null;
  chunk_id: string;
  pages: { start: number; end: number };
}

export interface StatBlockDetail {
  name?: string;
  subtitle?: string;
  nc?: number;
  attributes?: Record<string, string>;
  abilities?: string[];
  game_system?: string;
  chunk_id: string;
  pages: { start: number; end: number };
  source_refs?: Array<{
    document_id: string;
    page: number;
    chunk_id: string;
    page_block_ids: string[];
    bbox: { x0: number; y0: number; x1: number; y1: number } | null;
  }>;
}

export interface SectionNode extends Section {
  children: SectionNode[];
}
