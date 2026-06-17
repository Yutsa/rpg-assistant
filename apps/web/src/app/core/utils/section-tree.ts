import { Section, SectionNode } from '../models/campaign.models';

export function buildSectionTree(sections: Section[]): SectionNode[] {
  const byId = new Map<string, SectionNode>();
  for (const section of sections) {
    byId.set(section.id, { ...section, children: [] });
  }

  const roots: SectionNode[] = [];
  for (const node of byId.values()) {
    if (node.parent_section_id && byId.has(node.parent_section_id)) {
      byId.get(node.parent_section_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  }

  const sortNodes = (nodes: SectionNode[]): void => {
    nodes.sort((a, b) => a.page_start - b.page_start || a.title.localeCompare(b.title));
    for (const node of nodes) {
      sortNodes(node.children);
    }
  };
  sortNodes(roots);
  return roots;
}
