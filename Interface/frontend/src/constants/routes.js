export const ROUTES = {
  HOME: "/",
  LOGIN: "/login",
  SIGNUP: "/signup",
  DASHBOARD: "/dashboard",
  UPLOAD: "/upload",
  TRAINING: "/experiment/training",
  COMPARISON: "/experiment/comparison",
  EXPLAINABILITY: "/experiment/explainability",
  CHAT: "/experiment/chat",
  HISTORY: "/history",
};

export const NAV_ITEMS = [
  { label: "Home", path: ROUTES.DASHBOARD, icon: "LayoutGrid" },
  { label: "Datasets", path: ROUTES.UPLOAD, icon: "Database" },
  { label: "Training", path: ROUTES.TRAINING, icon: "Cpu" },
  { label: "Models", path: ROUTES.COMPARISON, icon: "BarChart3" },
  { label: "Explainability", path: ROUTES.EXPLAINABILITY, icon: "Lightbulb" },
  { label: "AI Assistant", path: ROUTES.CHAT, icon: "MessageSquare" },
  { label: "History", path: ROUTES.HISTORY, icon: "History" },
];
