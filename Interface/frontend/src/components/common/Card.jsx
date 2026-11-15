
export default function Card({
  children,
  className = "",
  padding = "p-4 sm:p-5",
  as: Component = "div",
  ...props
}) {
  return (
    <Component
      className={`min-w-0 rounded-card border border-surface-border bg-surface-card shadow-card ${padding} ${className}`}
      {...props}
    >
      {children}
    </Component>
  );
}

export function CardHeader({ title, subtitle, action, className = "" }) {
  return (
    <div className={`mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4 ${className}`}>
      <div className="min-w-0">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>

        {subtitle && (
          <p className="mt-0.5 text-xs text-ink-secondary">{subtitle}</p>
        )}
      </div>

      {action && (
        <div className="shrink-0">
          {action}
        </div>
      )}
    </div>
  );
}
