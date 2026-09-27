const VARIANTS = {
  primary:
    "bg-orange text-white hover:bg-orange-light shadow-sm",
  secondary:
    "bg-white text-ink border border-surface-border hover:border-ink/20 hover:bg-surface-page",
  ghost: "bg-transparent text-ink-secondary hover:bg-surface-page",
  danger: "bg-state-error text-white hover:opacity-90",
};

const SIZES = {
  sm: "text-xs px-3 py-1.5 gap-1.5",
  md: "text-sm px-4 py-2 gap-2",
  lg: "text-sm px-5 py-2.5 gap-2",
};

export default function Button({
  children,
  variant = "primary",
  size = "md",
  icon: Icon,
  iconPosition = "left",
  className = "",
  disabled = false,
  type = "button",
  ...props
}) {
  return (
    <button
      type={type}
      disabled={disabled}
      className={`inline-flex items-center justify-center font-medium rounded-lg transition-default disabled:opacity-50 disabled:cursor-not-allowed ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...props}
    >
      {Icon && iconPosition === "left" && <Icon size={16} />}
      {children}
      {Icon && iconPosition === "right" && <Icon size={16} />}
    </button>
  );
}
