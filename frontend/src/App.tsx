import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import AppLayout from "@/layouts/AppLayout";
import { useAuth } from "@/hooks/useAuth";
import { Skeleton } from "@/components/ui/skeleton";
import LoginPage from "@/pages/LoginPage";
import DashboardPage from "@/pages/DashboardPage";
import PatientsPage from "@/pages/PatientsPage";
import PatientDetailPage from "@/pages/PatientDetailPage";
import BedsPage from "@/pages/BedsPage";
import ResourcesPage from "@/pages/ResourcesPage";
import DepartmentsPage from "@/pages/DepartmentsPage";
import RoutingPage from "@/pages/RoutingPage";
import TransfersPage from "@/pages/TransfersPage";
import DischargesPage from "@/pages/DischargesPage";
import NotificationsPage from "@/pages/NotificationsPage";
import AIAssistantPage from "@/pages/AIAssistantPage";
import AuditLogsPage from "@/pages/AuditLogsPage";
import UsersPage from "@/pages/UsersPage";
import SettingsPage from "@/pages/SettingsPage";

function Protected() {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-8"><Skeleton className="h-8 w-64" /></div>;
  return user ? <Outlet /> : <Navigate to="/login" replace />;
}

/** Frontend gate for UX only. The backend enforces every permission independently. */
function Guard({ perm, children }: { perm: string; children: JSX.Element }) {
  const { can } = useAuth();
  return can(perm) ? children : (
    <div role="alert" className="py-16 text-center">
      <h1 className="text-lg font-semibold">Access denied</h1>
      <p className="text-sm text-muted-foreground">Your role does not include access to this page.</p>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<Protected />}>
        <Route element={<AppLayout />}>
          <Route index element={<Guard perm="dashboard:read"><DashboardPage /></Guard>} />
          <Route path="patients" element={<Guard perm="patients:read"><PatientsPage /></Guard>} />
          <Route path="patients/:id" element={<Guard perm="patients:read"><PatientDetailPage /></Guard>} />
          <Route path="beds" element={<Guard perm="beds:read"><BedsPage /></Guard>} />
          <Route path="resources" element={<Guard perm="resources:read"><ResourcesPage /></Guard>} />
          <Route path="departments" element={<Guard perm="departments:read"><DepartmentsPage /></Guard>} />
          <Route path="routing" element={<Guard perm="routing:use"><RoutingPage /></Guard>} />
          <Route path="transfers" element={<Guard perm="transfers:read"><TransfersPage /></Guard>} />
          <Route path="discharges" element={<Guard perm="discharges:read"><DischargesPage /></Guard>} />
          <Route path="notifications" element={<Guard perm="notifications:read"><NotificationsPage /></Guard>} />
          <Route path="ai" element={<Guard perm="ai:use"><AIAssistantPage /></Guard>} />
          <Route path="audit" element={<Guard perm="audit:read"><AuditLogsPage /></Guard>} />
          <Route path="users" element={<Guard perm="users:manage"><UsersPage /></Guard>} />
          <Route path="settings" element={<Guard perm="settings:read"><SettingsPage /></Guard>} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
