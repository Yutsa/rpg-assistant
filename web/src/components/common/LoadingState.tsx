export function LoadingState({ label = "Chargement…" }: { label?: string }) {
  return (
    <div className="state-box" role="status">
      <div className="spinner" />
      <p className="muted">{label}</p>
    </div>
  );
}
