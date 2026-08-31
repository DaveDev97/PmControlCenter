import React from "react";
import ReactDOM from "react-dom/client";
import {
  createHashRouter,
  Navigate,
  RouterProvider,
} from "react-router-dom";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import Layout from "./components/Layout";
import AccountDashboard from "./pages/AccountDashboard";
import ContractDashboard from "./pages/ContractDashboard";
import TeamDashboard from "./pages/TeamDashboard";
import PersonDashboard from "./pages/PersonDashboard";
import Contracts from "./pages/Contracts";
import Opportunities from "./pages/Opportunities";
import OpportunityDetail from "./pages/OpportunityDetail";
import Resources from "./pages/Resources";
import CostBalancer from "./pages/CostBalancer";
import CostSpaceMonitor from "./pages/CostSpaceMonitor";
import TimeReportGenerator from "./pages/TimeReportGenerator";
import AIChatPage from "./pages/AIChatPage";
import SetupWizard from "./pages/SetupWizard";
import SettingsPage from "./pages/SettingsPage";
import { settingsApi } from "./lib/settings";
import "./lib/i18n";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, staleTime: 30_000 } },
});

/**
 * Gate the main app behind the Setup Wizard: if no data folder has been
 * configured yet, redirect to /setup. Renders the normal Layout otherwise.
 */
function ProtectedLayout() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["data-status"],
    queryFn: settingsApi.status,
    retry: false,
    // Always re-check freshly on mount, so returning from the wizard never sees
    // a stale "not configured" status (which caused the setup to run twice).
    staleTime: 0,
    gcTime: 0,
    refetchOnMount: "always",
  });

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 text-slate-500 dark:bg-slate-900">
        Loading…
      </div>
    );
  }
  // On backend error, fall through to the app rather than trapping the user.
  if (!isError && data && !data.configured) {
    return <Navigate to="/setup" replace />;
  }
  return <Layout />;
}

// Hash router so it works from file:// (Electron) without server rewrites.
const router = createHashRouter([
  { path: "/setup", element: <SetupWizard /> },
  {
    path: "/",
    element: <ProtectedLayout />,
    children: [
      { index: true, element: <AccountDashboard /> },
      { path: "contracts", element: <Contracts /> },
      { path: "contracts/:id", element: <ContractDashboard /> },
      { path: "opportunities", element: <Opportunities /> },
      { path: "opportunities/:id", element: <OpportunityDetail /> },
      { path: "team", element: <TeamDashboard /> },
      { path: "resources", element: <Resources /> },
      { path: "person/:id", element: <PersonDashboard /> },
      { path: "cost-balancer", element: <CostBalancer /> },
      { path: "cost-space", element: <CostSpaceMonitor /> },
      { path: "time-reports", element: <TimeReportGenerator /> },
      { path: "ai-chat", element: <AIChatPage /> },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>
);
