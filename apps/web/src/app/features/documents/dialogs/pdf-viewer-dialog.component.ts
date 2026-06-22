import { Component, inject, signal } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { PageLayoutViewerComponent } from '../../../shared/components/page-layout-viewer/page-layout-viewer.component';
import { PdfViewerDialogData } from './pdf-viewer-dialog.data';

@Component({
  selector: 'app-pdf-viewer-dialog',
  imports: [MatDialogModule, MatButtonModule, MatIconModule, PageLayoutViewerComponent],
  templateUrl: './pdf-viewer-dialog.component.html',
  styleUrl: './pdf-viewer-dialog.component.scss',
})
export class PdfViewerDialogComponent {
  private readonly dialogRef = inject(MatDialogRef<PdfViewerDialogComponent>);
  readonly data = inject<PdfViewerDialogData>(MAT_DIALOG_DATA);

  readonly pageNumber = signal(this.data.pageNumber ?? 1);

  close(): void {
    this.dialogRef.close();
  }
}
