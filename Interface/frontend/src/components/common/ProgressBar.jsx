const TONES = {
  orange: "bg-orange",
  success: "bg-state-success",
  info: "bg-state-info",
  muted: "bg-ink-muted",
};

export default function ProgressBar({
  value = 0,
  tone = "orange",
  height = "h-1.5",
  showLabel = false,
  className = "",
}) {
  const clamped = Math.min(100, Math.max(0, value));
  return (
    <div className={className}>
      <div className={`w-full ${height} bg-surface-border rounded-full overflow-hidden`}>
        <div
          className={`${height} ${TONES[tone]} rounded-full transition-all duration-500 ease-out`}
          style={{ width: `${clamped}%` }}
        />
      </div>
      {showLabel && (
        <span className="text-xs text-ink-muted mt-1 inline-block">{clamped}%</span>
      )}
    </div>
  );
}
