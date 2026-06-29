import { Injectable, computed, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class PdfViewerService {
  readonly documentId = signal<string | null>(null);
  readonly pageNumber = signal(1);

  readonly isOpen = computed(() => this.documentId() !== null);

  open(documentId: string, pageNumber = 1): void {
    this.documentId.set(documentId);
    this.pageNumber.set(pageNumber);
  }

  close(): void {
    this.documentId.set(null);
  }

  setPage(pageNumber: number): void {
    this.pageNumber.set(pageNumber);
  }
}
