// Centralized mock data. Swap for real API responses in src/services/*
// when the FastAPI backend is wired up — shapes are kept close to the
// eventual response bodies so that swap is mostly a drop-in.

export const dashboardStats = [
  { label: "Total Projects", value: 12 },
  { label: "Datasets", value: 8 },
  { label: "Experiments", value: 24 },
  { label: "Completed Runs", value: 19 },
];

export const recentExperiments = [
  {
    id: "exp_1042",
    name: "Customer Churn",
    dataset: "customer_churn.csv",
    status: "Completed",
    bestModel: "XGBoost",
    f1: 0.853,
    updated: "2 hours ago",
  },
  {
    id: "exp_1041",
    name: "Housing Classification",
    dataset: "housing.csv",
    status: "Completed",
    bestModel: "Random Forest",
    f1: 0.812,
    updated: "Yesterday",
  },
  {
    id: "exp_1039",
    name: "Loan Default Risk",
    dataset: "loan_applications.csv",
    status: "Training",
    bestModel: "—",
    f1: null,
    updated: "3 days ago",
  },
  {
    id: "exp_1035",
    name: "Employee Attrition",
    dataset: "hr_attrition.csv",
    status: "Completed",
    bestModel: "Logistic Regression",
    f1: 0.771,
    updated: "1 week ago",
  },
];

export const recentUploads = [
  {
    id: "ds_301",
    name: "customer_churn.csv",
    rows: 7043,
    columns: 21,
    uploadedAt: "2 hours ago",
  },
  {
    id: "ds_300",
    name: "housing.csv",
    rows: 20640,
    columns: 10,
    uploadedAt: "Yesterday",
  },
  {
    id: "ds_298",
    name: "loan_applications.csv",
    rows: 12684,
    columns: 17,
    uploadedAt: "3 days ago",
  },
  {
    id: "ds_294",
    name: "hr_attrition.csv",
    rows: 1470,
    columns: 35,
    uploadedAt: "1 week ago",
  },
];

export const datasetProfile = {
  fileName: "customer_churn.csv",
  rows: 7043,
  columns: 21,
  missingValues: 1247,
  missingPercentage: 0.8,
  targetColumn: "Churn",
  duplicates: 0,
  columnTypes: [
    { type: "Numeric", count: 6 },
    { type: "Categorical", count: 14 },
    { type: "Datetime", count: 0 },
    { type: "Text", count: 1 },
  ],
  targetDistribution: [
    { label: "No", value: 5174 },
    { label: "Yes", value: 1869 },
  ],
  qualityFlags: [
    { label: "customerID looks ID-like — excluded from modeling", level: "info" },
    { label: "TotalCharges has 11 missing values (0.16%)", level: "warning" },
    { label: "No duplicate rows detected", level: "success" },
    { label: "Class balance is moderately skewed (73% / 27%)", level: "warning" },
  ],
  columnDetails: [
    { name: "tenure", type: "Numeric", missing: "0%", cardinality: "-", skew: "0.24" },
    { name: "MonthlyCharges", type: "Numeric", missing: "0%", cardinality: "-", skew: "-0.22" },
    { name: "TotalCharges", type: "Numeric", missing: "0.16%", cardinality: "-", skew: "0.96" },
    { name: "Contract", type: "Categorical", missing: "0%", cardinality: "3", skew: "-" },
    { name: "PaymentMethod", type: "Categorical", missing: "0%", cardinality: "4", skew: "-" },
    { name: "InternetService", type: "Categorical", missing: "0%", cardinality: "3", skew: "-" },
  ],
};

export const preprocessingSteps = [
  {
    id: "missing",
    title: "Missing Value Handling",
    description: "Choose how missing values are imputed per column type.",
    recommended: "Median for numeric, mode for categorical",
  },
  {
    id: "encoding",
    title: "Categorical Encoding",
    description: "Convert categorical columns into a model-ready format.",
    recommended: "One-hot encoding (cardinality < 10), target encoding otherwise",
  },
  {
    id: "scaling",
    title: "Feature Scaling",
    description: "Normalize numeric feature ranges for distance-based models.",
    recommended: "Standard scaling (z-score)",
  },
  {
    id: "outliers",
    title: "Outlier Handling",
    description: "Detect and cap extreme values in numeric columns.",
    recommended: "IQR-based capping",
  },
];

export const candidateModels = [
  { id: "logreg", name: "Logistic Regression", description: "Fast linear baseline" },
  { id: "rf", name: "Random Forest", description: "Ensemble of decision trees" },
  { id: "xgb", name: "XGBoost", description: "Gradient-boosted trees" },
];

export const trainingStages = [
  { id: "preprocessing", label: "Preprocessing", status: "complete", progress: 100 },
  { id: "selection", label: "Model Selection", status: "complete", progress: 100 },
  { id: "rf", label: "Random Forest", status: "complete", progress: 100 },
  { id: "xgb", label: "XGBoost", status: "in_progress", progress: 64 },
  { id: "eval", label: "Evaluation", status: "pending", progress: 0 },
];

export const modelMetrics = [
  {
    model: "XGBoost",
    accuracy: 0.867,
    precision: 0.842,
    recall: 0.865,
    f1: 0.853,
    rocAuc: 0.911,
    trainingTime: "18.2s",
    selected: true,
  },
  {
    model: "Random Forest",
    accuracy: 0.849,
    precision: 0.821,
    recall: 0.804,
    f1: 0.812,
    rocAuc: 0.887,
    trainingTime: "9.6s",
    selected: false,
  },
  {
    model: "Logistic Regression",
    accuracy: 0.798,
    precision: 0.762,
    recall: 0.781,
    f1: 0.771,
    rocAuc: 0.842,
    trainingTime: "1.1s",
    selected: false,
  },
];

export const featureImportance = [
  { feature: "Contract", importance: 0.24 },
  { feature: "tenure", importance: 0.19 },
  { feature: "MonthlyCharges", importance: 0.15 },
  { feature: "InternetService", importance: 0.12 },
  { feature: "PaymentMethod", importance: 0.09 },
  { feature: "TotalCharges", importance: 0.08 },
  { feature: "OnlineSecurity", importance: 0.06 },
  { feature: "TechSupport", importance: 0.04 },
];

export const shapExplanation = {
  predictionExample: {
    id: "row_4821",
    predicted: "Churn: Yes",
    confidence: 0.81,
  },
  contributions: [
    { feature: "Contract = Month-to-month", value: 0.31, direction: "positive" },
    { feature: "tenure = 3 months", value: 0.22, direction: "positive" },
    { feature: "InternetService = Fiber optic", value: 0.14, direction: "positive" },
    { feature: "TechSupport = No", value: 0.09, direction: "positive" },
    { feature: "PaymentMethod = Credit card (auto)", value: -0.12, direction: "negative" },
    { feature: "MonthlyCharges = $70.35", value: -0.05, direction: "negative" },
  ],
};

export const chatMessages = [
  {
    id: 1,
    role: "user",
    text: "Why was XGBoost selected as the best model?",
  },
  {
    id: 2,
    role: "assistant",
    text: "XGBoost was selected because it achieved the highest F1-score (0.853) and ROC-AUC (0.911) across the 5-fold cross-validation runs, outperforming Random Forest and Logistic Regression on this dataset. It handled the class imbalance in Churn better than the other candidates during hyperparameter search.",
  },
  {
    id: 3,
    role: "user",
    text: "Which features drove that performance?",
  },
  {
    id: 4,
    role: "assistant",
    text: "Contract type and tenure were the two strongest predictors, together accounting for about 43% of the model's feature importance. Customers on month-to-month contracts with short tenure show the highest churn risk in this run.",
  },
];

export const runHistory = [
  {
    id: "run_1042",
    project: "Retention Analysis",
    dataset: "customer_churn.csv",
    status: "Completed",
    bestModel: "XGBoost",
    f1: 0.853,
    created: "2026-09-25",
  },
  {
    id: "run_1041",
    project: "Housing Study",
    dataset: "housing.csv",
    status: "Completed",
    bestModel: "Random Forest",
    f1: 0.812,
    created: "2026-09-24",
  },
  {
    id: "run_1039",
    project: "Risk Modeling",
    dataset: "loan_applications.csv",
    status: "Training",
    bestModel: "—",
    f1: null,
    created: "2026-09-22",
  },
  {
    id: "run_1035",
    project: "People Analytics",
    dataset: "hr_attrition.csv",
    status: "Completed",
    bestModel: "Logistic Regression",
    f1: 0.771,
    created: "2026-09-18",
  },
  {
    id: "run_1030",
    project: "Retention Analysis",
    dataset: "customer_churn_v0.csv",
    status: "Failed",
    bestModel: "—",
    f1: null,
    created: "2026-09-12",
  },
];
