import type { StatBlockDetail } from "../../api/types";
import { usePdfPanel } from "../../context/PdfPanelContext";

export function StatBlockDetailView({ detail }: { detail: StatBlockDetail }) {
  const { showSource } = usePdfPanel();
  const firstRef = detail.source_refs[0];

  return (
    <article className="chunk-reader">
      <header>
        <h2 style={{ marginTop: 0 }}>{detail.name}</h2>
        {detail.subtitle && <p className="muted">{detail.subtitle}</p>}
        {detail.nc != null && <p>NC {detail.nc}</p>}
      </header>

      {detail.attributes && Object.keys(detail.attributes).length > 0 && (
        <>
          <h3>Attributs</h3>
          <table className="stat-table">
            <tbody>
              {Object.entries(detail.attributes).map(([key, value]) => (
                <tr key={key}>
                  <th>{key}</th>
                  <td>{value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {detail.abilities && detail.abilities.length > 0 && (
        <>
          <h3>Capacités</h3>
          <ul>
            {detail.abilities.map((ability) => (
              <li key={ability.title}>
                <strong>{ability.title}</strong>
                {ability.text && (
                  <p style={{ margin: "0.35rem 0 0", whiteSpace: "pre-wrap" }}>
                    {ability.text}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </>
      )}

      {firstRef && (
        <div className="chunk-actions">
          <button
            type="button"
            className="btn primary"
            onClick={() =>
              showSource(firstRef.page, {
                pageBlockIds: firstRef.page_block_ids,
                bboxFallbacks: firstRef.bbox ? [firstRef.bbox] : [],
              })
            }
          >
            Voir la source
          </button>
        </div>
      )}
    </article>
  );
}
