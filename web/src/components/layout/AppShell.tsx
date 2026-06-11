import { Link, Outlet, useLocation } from "react-router-dom";

function crumbsFromPath(pathname: string) {
  const parts = pathname.split("/").filter(Boolean);
  const items: { label: string; to?: string }[] = [{ label: "Campagnes", to: "/" }];
  if (parts[0] === "campaigns" && parts[1]) {
    items.push({ label: parts[1], to: `/campaigns/${parts[1]}` });
  }
  if (parts[0] === "documents" && parts[1]) {
    items.push({ label: parts[1], to: `/documents/${parts[1]}` });
    if (parts[2] === "stat-blocks") {
      items.push({
        label: "Fiches stats",
        to: `/documents/${parts[1]}/stat-blocks`,
      });
      if (parts[3]) {
        items.push({ label: decodeURIComponent(parts[3]) });
      }
    } else if (parts[2] === "chunks" && parts[3]) {
      items.push({ label: `Chunk ${parts[3]}` });
    }
  }
  return items;
}

export function AppShell() {
  const location = useLocation();
  const crumbs = crumbsFromPath(location.pathname);
  const documentMatch = location.pathname.match(/^\/documents\/([^/]+)/);
  const documentId = documentMatch?.[1];

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>RPG Assistant</h1>
        <nav className="breadcrumb" aria-label="Fil d'Ariane">
          {crumbs.map((item, index) => (
            <span key={`${item.label}-${index}`}>
              {index > 0 && <span aria-hidden> / </span>}
              {item.to ? <Link to={item.to}>{item.label}</Link> : <strong>{item.label}</strong>}
            </span>
          ))}
        </nav>
      </header>

      {documentId && !location.pathname.includes("/stat-blocks") && (
        <nav className="sub-nav">
          <Link
            to={`/documents/${documentId}`}
            className={location.pathname === `/documents/${documentId}` ? "active" : ""}
          >
            Exploration
          </Link>
          <Link
            to={`/documents/${documentId}/stat-blocks`}
            className={location.pathname.includes("/stat-blocks") ? "active" : ""}
          >
            Fiches stats
          </Link>
        </nav>
      )}

      {documentId && location.pathname.includes("/stat-blocks") && (
        <nav className="sub-nav">
          <Link to={`/documents/${documentId}`}>Exploration</Link>
          <Link
            to={`/documents/${documentId}/stat-blocks`}
            className="active"
          >
            Fiches stats
          </Link>
        </nav>
      )}

      <Outlet />
    </div>
  );
}
