import { HttpClient, HttpParams } from '@angular/common/http';
import { Service, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_URL } from '../api-url';
import {
  Campaign,
  CampaignSummary,
  Chunk,
  ChunkListItem,
  Document,
  GameSystem,
  ImportCreateResponse,
  IngestionRun,
  PageExtractorsCompare,
  PageMeta,
  PageNode,
  PageNodeLevel,
  PageNodeType,
  Section,
  StatBlockDetail,
  StatBlockIndex,
} from '../models/campaign.models';
import { encodeStatBlockName } from '../utils/stat-block-route';

export interface ChunkListParams {
  sectionId?: string;
  pageStart?: number;
  pageEnd?: number;
  limit?: number;
  offset?: number;
}

@Service()
export class CampaignApiService {
  private readonly http = inject(HttpClient);

  listCampaigns(): Observable<Campaign[]> {
    return this.http.get<Campaign[]>(`${API_URL}/campaigns`);
  }

  listDocuments(campaignId: string): Observable<Document[]> {
    return this.http.get<Document[]>(`${API_URL}/campaigns/${campaignId}/documents`);
  }

  getCampaignSummary(campaignId: string): Observable<CampaignSummary> {
    return this.http.get<CampaignSummary>(`${API_URL}/campaigns/${campaignId}/summary`);
  }

  listSections(documentId: string): Observable<Section[]> {
    return this.http.get<Section[]>(`${API_URL}/documents/${documentId}/sections`);
  }

  listChunks(documentId: string, params: ChunkListParams = {}): Observable<ChunkListItem[]> {
    let httpParams = new HttpParams();
    for (const [key, value] of Object.entries({
      section_id: params.sectionId,
      page_start: params.pageStart,
      page_end: params.pageEnd,
      limit: params.limit,
      offset: params.offset,
    })) {
      if (value != null) {
        httpParams = httpParams.set(key, value);
      }
    }
    return this.http.get<ChunkListItem[]>(`${API_URL}/documents/${documentId}/chunks`, {
      params: httpParams,
    });
  }

  getChunk(chunkId: string): Observable<Chunk> {
    return this.http.get<Chunk>(`${API_URL}/chunks/${chunkId}`);
  }

  listStatBlocks(documentId: string): Observable<StatBlockIndex[]> {
    return this.http.get<StatBlockIndex[]>(`${API_URL}/documents/${documentId}/stat-blocks`);
  }

  getStatBlock(documentId: string, name: string): Observable<StatBlockDetail> {
    return this.http.get<StatBlockDetail>(
      `${API_URL}/documents/${documentId}/stat-blocks/${encodeStatBlockName(name)}`,
    );
  }

  getStatBlockByChunkId(documentId: string, chunkId: string): Observable<StatBlockDetail> {
    return this.http.get<StatBlockDetail>(
      `${API_URL}/documents/${documentId}/stat-blocks/${chunkId}`,
    );
  }

  getPageMeta(documentId: string, pageNumber: number): Observable<PageMeta> {
    return this.http.get<PageMeta>(`${API_URL}/documents/${documentId}/pages/${pageNumber}`);
  }

  getPageRenderUrl(documentId: string, pageNumber: number, dpi = 150): string {
    const params = new HttpParams().set('dpi', dpi);
    return `${API_URL}/documents/${documentId}/pages/${pageNumber}/render?${params.toString()}`;
  }

  listPageNodes(
    documentId: string,
    pageNumber: number,
    params: { level?: PageNodeLevel; type?: PageNodeType } = {},
  ): Observable<PageNode[]> {
    let httpParams = new HttpParams();
    if (params.level) {
      httpParams = httpParams.set('level', params.level);
    }
    if (params.type) {
      httpParams = httpParams.set('type', params.type);
    }
    return this.http.get<PageNode[]>(
      `${API_URL}/documents/${documentId}/pages/${pageNumber}/nodes`,
      { params: httpParams },
    );
  }

  getPageExtractorsCompare(
    documentId: string,
    pageNumber: number,
  ): Observable<PageExtractorsCompare> {
    return this.http.get<PageExtractorsCompare>(
      `${API_URL}/documents/${documentId}/pages/${pageNumber}/extractors-compare`,
    );
  }

  listGameSystems(): Observable<GameSystem[]> {
    return this.http.get<GameSystem[]>(`${API_URL}/ingestion/game-systems`);
  }

  importPdf(formData: FormData): Observable<ImportCreateResponse> {
    return this.http.post<ImportCreateResponse>(`${API_URL}/imports`, formData);
  }

  getIngestionRun(runId: string): Observable<IngestionRun> {
    return this.http.get<IngestionRun>(`${API_URL}/ingestion-runs/${runId}`);
  }
}
