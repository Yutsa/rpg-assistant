import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';
import { filter, map, startWith } from 'rxjs';

interface BreadcrumbItem {
  label: string;
  link: string[];
}

@Component({
  selector: 'app-app-shell',
  imports: [RouterOutlet, RouterLink, MatToolbarModule],
  templateUrl: './app-shell.component.html',
  styleUrl: './app-shell.component.scss',
})
export class AppShellComponent {
  private readonly router = inject(Router);

  private readonly url = toSignal(
    this.router.events.pipe(
      filter((event) => event instanceof NavigationEnd),
      map(() => this.router.url),
      startWith(this.router.url),
    ),
    { initialValue: this.router.url },
  );

  readonly breadcrumbs = computed(() => this.buildBreadcrumbs(this.url()));

  private buildBreadcrumbs(url: string): BreadcrumbItem[] {
    const items: BreadcrumbItem[] = [{ label: 'Campagnes', link: ['/campaigns'] }];
    const parts = url.split('?')[0].split('/').filter(Boolean);

    if (parts[0] === 'campaigns' && parts[1]) {
      items.push({ label: parts[1], link: ['/campaigns', parts[1]] });
    }
    if (parts[0] === 'documents' && parts[1]) {
      items.push({ label: parts[1], link: ['/documents', parts[1]] });
    }
    if (parts[2] === 'chunks' && parts[3]) {
      items.push({ label: `Chunk ${parts[3]}`, link: ['/documents', parts[1], 'chunks', parts[3]] });
    }
    if (parts[2] === 'stat-blocks' && parts[3]) {
      const label = parts[3].startsWith('chunk_') ? `Fiche ${parts[3]}` : decodeURIComponent(parts[3]);
      items.push({
        label,
        link: ['/documents', parts[1], 'stat-blocks', parts[3]],
      });
    }

    return items;
  }
}
