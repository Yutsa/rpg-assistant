import { inject, Injectable } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';

import { PdfViewerDialogComponent } from '../../features/documents/dialogs/pdf-viewer-dialog.component';

@Injectable({ providedIn: 'root' })
export class PdfViewerService {
  private readonly dialog = inject(MatDialog);

  open(documentId: string, pageNumber?: number): void {
    this.dialog.open(PdfViewerDialogComponent, {
      data: { documentId, pageNumber },
      panelClass: 'pdf-viewer-dialog-panel',
      width: 'min(96vw, 1200px)',
      maxWidth: '96vw',
      height: '92vh',
      autoFocus: false,
    });
  }
}
