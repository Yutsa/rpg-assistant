export interface BBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface SourceSpan {
  page: number;
  page_block_ids: string[];
  bbox: BBox | null;
}

export interface Campaign {
  id: string;
  title: string;
  game_system: string;
  document_count: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface Document {
  id: string;
  campaign_id: string;
  filename: string;
  page_count: number;
  content_hash: string;
  section_count: number;
  chunk_count: number;
  latest_ingestion_run_id?: string | null;
  latest_ingestion_status?: string | null;
  created_at?: string | null;
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

export interface Chunk extends ChunkListItem {
  campaign_id: string;
  document_id: string;
  text: string;
  source_spans: SourceSpan[];
  metadata: Record<string, unknown>;
}

export interface StatBlockIndexEntry {
  name: string;
  nc: number | null;
  chunk_id: string;
  pages: { start: number; end: number };
}

export interface StatBlockSourceRef {
  document_id: string;
  page: number;
  chunk_id: string;
  page_block_ids: string[];
  bbox: BBox | null;
}

export interface StatAbility {
  title: string;
  text: string;
}

export interface StatBlockDetail {
  name: string;
  subtitle?: string | null;
  nc?: number | null;
  attributes?: Record<string, string | number>;
  abilities?: StatAbility[];
  game_system?: string;
  chunk_id: string;
  pages: { start: number; end: number };
  source_refs: StatBlockSourceRef[];
}

export interface PageMeta {
  page_number: number;
  width: number;
  height: number;
}

export interface PageBlock {
  id: string;
  page_number: number;
  block_index: number;
  text: string;
  bbox: BBox;
  metadata: Record<string, unknown>;
}

export interface ApiErrorBody {
  error: string;
  code?: string;
  candidates?: Array<{
    name: string;
    nc: number | null;
    chunk_id: string;
    pages: { start: number; end: number };
  }>;
}

export interface PdfHighlight {
  pageBlockIds: string[];
  bboxFallbacks: BBox[];
}
