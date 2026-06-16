import { Component, input, output } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';

import { SectionNode } from '../../../core/models/campaign.models';

@Component({
  selector: 'app-section-tree-node',
  imports: [MatButtonModule, SectionTreeNodeComponent],
  templateUrl: './section-tree-node.component.html',
  styleUrl: './section-tree-node.component.scss',
})
export class SectionTreeNodeComponent {
  readonly node = input.required<SectionNode>();
  readonly selectedSectionId = input<string | null>(null);
  readonly sectionSelected = output<string | null>();
}
