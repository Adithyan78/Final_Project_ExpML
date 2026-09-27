import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ROUTES } from "../constants/routes";

import LandingPage from "../pages/Landing/LandingPage";
import LoginPage from "../pages/Auth/LoginPage";
import SignupPage from "../pages/Auth/SignupPage";
import DashboardPage from "../pages/Dashboard/DashboardPage";
import UploadPage from "../pages/Upload/UploadPage";
import TrainingPage from "../pages/Experiment/TrainingPage";
import ModelComparisonPage from "../pages/Experiment/ModelComparisonPage";
import ExplainabilityPage from "../pages/Experiment/ExplainabilityPage";
import ChatPage from "../pages/Experiment/ChatPage";
import RunHistoryPage from "../pages/History/RunHistoryPage";

export default function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path={ROUTES.HOME} element={<LandingPage />} />
        <Route path={ROUTES.LOGIN} element={<LoginPage />} />
        <Route path={ROUTES.SIGNUP} element={<SignupPage />} />
        <Route path={ROUTES.DASHBOARD} element={<DashboardPage />} />
        <Route path={ROUTES.UPLOAD} element={<UploadPage />} />
        <Route path={ROUTES.TRAINING} element={<TrainingPage />} />
        <Route path={ROUTES.COMPARISON} element={<ModelComparisonPage />} />
        <Route path={ROUTES.EXPLAINABILITY} element={<ExplainabilityPage />} />
        <Route path={ROUTES.CHAT} element={<ChatPage />} />
        <Route path={ROUTES.HISTORY} element={<RunHistoryPage />} />
      </Routes>
    </BrowserRouter>
  );
}
