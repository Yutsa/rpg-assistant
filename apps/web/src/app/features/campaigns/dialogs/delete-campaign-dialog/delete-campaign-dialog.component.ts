import { Component, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { CampaignApiService } from '../../../../core/services/campaign-api.service';

export interface DeleteCampaignDialogData {
  campaignId: string;
  campaignTitle: string;
  documentCount: number;
}

@Component({
  selector: 'app-delete-campaign-dialog',
  imports: [MatDialogModule, MatButtonModule, MatIconModule, MatProgressSpinnerModule],
  templateUrl: './delete-campaign-dialog.component.html',
  styleUrl: './delete-campaign-dialog.component.scss',
})
export class DeleteCampaignDialogComponent {
  private readonly api = inject(CampaignApiService);
  private readonly dialogRef = inject(MatDialogRef<DeleteCampaignDialogComponent>);
  readonly data = inject<DeleteCampaignDialogData>(MAT_DIALOG_DATA);

  readonly deleting = signal(false);
  readonly errorMessage = signal<string | null>(null);

  confirm(): void {
    this.deleting.set(true);
    this.errorMessage.set(null);
    this.api.deleteCampaign(this.data.campaignId).subscribe({
      next: () => this.dialogRef.close(true),
      error: (err) => {
        this.deleting.set(false);
        this.errorMessage.set(err?.error?.error ?? 'Impossible de supprimer la campagne.');
      },
    });
  }

  cancel(): void {
    this.dialogRef.close(false);
  }
}
