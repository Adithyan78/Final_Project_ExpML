
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
    <div className={`w-full min-w-0 ${className}`}>
      <div
        className={`w-full ${height} overflow-hidden rounded-full bg-surface-border`}
      >
        <div
          className={`${height} ${TONES[tone]} rounded-full transition-all duration-500 ease-out`}
          style={{ width: `${clamped}%` }}
        />
      </div>

      {showLabel && (
        <span className="mt-1 inline-block text-xs text-ink-muted">
          {clamped}%
        </span>
      )}
    </div>
  );
}
