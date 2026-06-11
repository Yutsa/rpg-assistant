import type { Section } from "../../api/types";

interface SectionNode extends Section {
  children: SectionNode[];
}

function buildTree(sections: Section[]): SectionNode[] {
  const byId = new Map<string, SectionNode>();
  const roots: SectionNode[] = [];
  for (const section of sections) {
    byId.set(section.id, { ...section, children: [] });
  }
  for (const node of byId.values()) {
    if (node.parent_section_id && byId.has(node.parent_section_id)) {
      byId.get(node.parent_section_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  }
  return roots;
}

function SectionBranch({
  node,
  selectedId,
  onSelect,
}: {
  node: SectionNode;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <li>
      <button
        type="button"
        className={selectedId === node.id ? "active" : ""}
        style={{ paddingLeft: `${0.75 + (node.level - 1) * 0.75}rem` }}
        onClick={() => onSelect(node.id)}
      >
        {node.title}
        <span className="pages">
          p.{node.page_start}
          {node.page_end !== node.page_start ? `–${node.page_end}` : ""}
        </span>
      </button>
      {node.children.length > 0 && (
        <ul>
          {node.children.map((child) => (
            <SectionBranch
              key={child.id}
              node={child}
              selectedId={selectedId}
              onSelect={onSelect}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

export function SectionTree({
  sections,
  selectedId,
  onSelect,
}: {
  sections: Section[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const tree = buildTree(sections);
  if (tree.length === 0) {
    return <p className="muted" style={{ padding: "1rem" }}>Aucune section.</p>;
  }
  return (
    <nav className="section-tree" aria-label="Sections">
      <ul>
        {tree.map((node) => (
          <SectionBranch
            key={node.id}
            node={node}
            selectedId={selectedId}
            onSelect={onSelect}
          />
        ))}
      </ul>
    </nav>
  );
}
