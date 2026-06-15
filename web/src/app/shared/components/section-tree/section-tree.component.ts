import { Component, input, output } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';

import { SectionNode } from '../../../core/models/campaign.models';
import { SectionTreeNodeComponent } from './section-tree-node.component';

@Component({
  selector: 'app-section-tree',
  imports: [MatButtonModule, SectionTreeNodeComponent],
  templateUrl: './section-tree.component.html',
  styleUrl: './section-tree.component.scss',
})
export class SectionTreeComponent {
  readonly nodes = input.required<SectionNode[]>();
  readonly selectedSectionId = input<string | null>(null);
  readonly sectionSelected = output<string | null>();

  selectAll(): void {
    this.sectionSelected.emit(null);
  }
}
