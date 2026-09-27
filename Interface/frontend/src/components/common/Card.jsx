export default function Card({
  children,
  className = "",
  padding = "p-5",
  as: Component = "div",
  ...props
}) {
  return (
    <Component
      className={`bg-surface-card border border-surface-border rounded-card shadow-card ${padding} ${className}`}
      {...props}
    >
      {children}
    </Component>
  );
}

export function CardHeader({ title, subtitle, action, className = "" }) {
  return (
    <div className={`flex items-start justify-between gap-4 mb-4 ${className}`}>
      <div>
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        {subtitle && (
          <p className="text-xs text-ink-secondary mt-0.5">{subtitle}</p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
