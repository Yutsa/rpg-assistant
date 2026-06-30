import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Router } from '@angular/router';
import { Subscription, switchMap, takeWhile, timer } from 'rxjs';

import { CampaignApiService } from '../../../../core/services/campaign-api.service';
import { GameSystem, IngestionRun } from '../../../../core/models/campaign.models';

type DialogPhase = 'form' | 'importing' | 'success' | 'error';

const TERMINAL_STATUSES = new Set(['completed', 'failed', 'rejected']);
const POLL_INTERVAL_MS = 2000;
const POLL_MAX_ATTEMPTS = 150;

function slugFromFilename(filename: string): string {
  const base = filename.replace(/\.pdf$/i, '');
  const normalized = base
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  const slug = (normalized || 'campagne').slice(0, 64);
  return /^[a-z0-9]/.test(slug) ? slug : `c${slug}`.slice(0, 64);
}

@Component({
  selector: 'app-import-campaign-dialog',
  imports: [
    FormsModule,
    MatDialogModule,
    MatButtonModule,
    MatCheckboxModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
  ],
  templateUrl: './import-campaign-dialog.component.html',
  styleUrl: './import-campaign-dialog.component.scss',
})
export class ImportCampaignDialogComponent {
  private readonly api = inject(CampaignApiService);
  private readonly dialogRef = inject(MatDialogRef<ImportCampaignDialogComponent>);
  private readonly router = inject(Router);

  private pollSub: Subscription | null = null;

  readonly phase = signal<DialogPhase>('form');
  readonly gameSystems = signal<GameSystem[]>([]);
  readonly gameSystemsLoading = signal(true);
  readonly gameSystemsError = signal<string | null>(null);
  readonly statusMessage = signal('Import en cours…');
  readonly errorMessage = signal<string | null>(null);
  readonly successSummary = signal<string | null>(null);

  selectedFile: File | null = null;
  campaignId = '';
  campaignTitle = '';
  gameSystem = 'cof2';
  reimport = true;

  constructor() {
    this.api.listGameSystems().subscribe({
      next: (systems) => {
        this.gameSystems.set(systems);
        const defaultSystem = systems.find((entry) => entry.default) ?? systems[0];
        if (defaultSystem) {
          this.gameSystem = defaultSystem.id;
        }
        this.gameSystemsLoading.set(false);
      },
      error: () => {
        this.gameSystemsError.set('Impossible de charger les profils de jeu.');
        this.gameSystemsLoading.set(false);
      },
    });
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    this.selectedFile = file;
    if (file && !this.campaignId.trim()) {
      this.campaignId = slugFromFilename(file.name);
    }
  }

  submit(): void {
    if (!this.selectedFile || !this.campaignId.trim() || !this.gameSystem) {
      this.errorMessage.set('Sélectionnez un PDF, un identifiant de campagne et un profil de jeu.');
      return;
    }

    this.errorMessage.set(null);
    this.phase.set('importing');
    this.statusMessage.set('Téléversement du PDF…');

    const formData = new FormData();
    formData.append('file', this.selectedFile);
    formData.append('campaign_id', this.campaignId.trim());
    if (this.campaignTitle.trim()) {
      formData.append('campaign_title', this.campaignTitle.trim());
    }
    formData.append('game_system', this.gameSystem);
    formData.append('reimport', String(this.reimport));

    this.api.importPdf(formData).subscribe({
      next: (response) => {
        this.statusMessage.set('Extraction en cours (pipeline Clojure)…');
        this.pollImportStatus(response.ingestion_run_id);
      },
      error: (err) => {
        const detail = err?.error?.error ?? 'Échec du lancement de l’import.';
        this.phase.set('error');
        this.errorMessage.set(detail);
      },
    });
  }

  retry(): void {
    this.phase.set('form');
    this.errorMessage.set(null);
    this.successSummary.set(null);
  }

  close(): void {
    this.pollSub?.unsubscribe();
    this.dialogRef.close();
  }

  private pollImportStatus(runId: string): void {
    this.pollSub?.unsubscribe();
    this.pollSub = timer(0, POLL_INTERVAL_MS)
      .pipe(
        takeWhile((attempt) => attempt < POLL_MAX_ATTEMPTS, true),
        switchMap(() => this.api.getIngestionRun(runId)),
        takeWhile((run) => !TERMINAL_STATUSES.has(run.status), true),
      )
      .subscribe({
        next: (run) => this.handleRunUpdate(run),
        error: () => {
          this.phase.set('error');
          this.errorMessage.set('Impossible de suivre la progression de l’import.');
        },
      });
  }

  private handleRunUpdate(run: IngestionRun): void {
    if (run.status === 'running') {
      this.statusMessage.set('Extraction en cours (pipeline Clojure)…');
      return;
    }

    if (run.status === 'completed' && run.document_id) {
      const profile = String(run.stats?.['stat_block_profile'] ?? this.gameSystem);
      const count = Number(run.stats?.['stat_block_count'] ?? 0);
      this.successSummary.set(`Profil appliqué : ${profile.toUpperCase()} — ${count} fiche(s) détectée(s)`);
      this.phase.set('success');
      void this.router.navigate(['/documents', run.document_id]);
      setTimeout(() => this.close(), 1200);
      return;
    }

    const message =
      run.error_message ??
      (run.status === 'rejected'
        ? 'PDF rejeté : couverture texte insuffisante (PDF scanné ?).'
        : 'Import échoué.');
    this.phase.set('error');
    this.errorMessage.set(message);
  }
}
