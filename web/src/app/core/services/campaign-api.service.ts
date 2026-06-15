import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  Campaign,
  CampaignSummary,
  Chunk,
  ChunkListItem,
  Document,
  Section,
  StatBlockDetail,
  StatBlockIndex,
} from '../models/campaign.models';

export interface ChunkListParams {
  sectionId?: string | null;
  pageStart?: number | null;
  pageEnd?: number | null;
  limit?: number;
  offset?: number;
}

@Injectable({ providedIn: 'root' })
export class CampaignApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiUrl;

  listCampaigns(): Observable<Campaign[]> {
    return this.http.get<Campaign[]>(`${this.baseUrl}/campaigns`);
  }

  listDocuments(campaignId: string): Observable<Document[]> {
    return this.http.get<Document[]>(`${this.baseUrl}/campaigns/${campaignId}/documents`);
  }

  getCampaignSummary(campaignId: string): Observable<CampaignSummary> {
    return this.http.get<CampaignSummary>(`${this.baseUrl}/campaigns/${campaignId}/summary`);
  }

  listSections(documentId: string): Observable<Section[]> {
    return this.http.get<Section[]>(`${this.baseUrl}/documents/${documentId}/sections`);
  }

  listChunks(documentId: string, params: ChunkListParams = {}): Observable<ChunkListItem[]> {
    let httpParams = new HttpParams();
    if (params.sectionId) {
      httpParams = httpParams.set('section_id', params.sectionId);
    }
    if (params.pageStart != null) {
      httpParams = httpParams.set('page_start', params.pageStart);
    }
    if (params.pageEnd != null) {
      httpParams = httpParams.set('page_end', params.pageEnd);
    }
    if (params.limit != null) {
      httpParams = httpParams.set('limit', params.limit);
    }
    if (params.offset != null) {
      httpParams = httpParams.set('offset', params.offset);
    }
    return this.http.get<ChunkListItem[]>(`${this.baseUrl}/documents/${documentId}/chunks`, {
      params: httpParams,
    });
  }

  getChunk(chunkId: string): Observable<Chunk> {
    return this.http.get<Chunk>(`${this.baseUrl}/chunks/${chunkId}`);
  }

  listStatBlocks(documentId: string): Observable<StatBlockIndex[]> {
    return this.http.get<StatBlockIndex[]>(`${this.baseUrl}/documents/${documentId}/stat-blocks`);
  }

  getStatBlock(documentId: string, name: string): Observable<StatBlockDetail> {
    return this.http.get<StatBlockDetail>(
      `${this.baseUrl}/documents/${documentId}/stat-blocks/${encodeURIComponent(name)}`,
    );
  }
}
