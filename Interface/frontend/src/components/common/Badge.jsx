const TONES = {
  neutral: "bg-surface-page text-ink-secondary border-surface-border",
  success: "bg-[#EAF7F1] text-state-success border-[#CDEEE0]",
  warning: "bg-[#FEF5E7] text-state-warning border-[#FCE6BE]",
  error: "bg-[#FCEAEA] text-state-error border-[#F6CACB]",
  info: "bg-[#EAF2FE] text-state-info border-[#CBDFFC]",
  orange: "bg-orange-50 text-orange border-[#FFDCC4]",
};

export default function Badge({ children, tone = "neutral", className = "" }) {
  return (
    <span
      className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-md border ${TONES[tone]} ${className}`}
    >
      {children}
    </span>
  );
}
