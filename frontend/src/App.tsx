import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { WorklistPage } from "./pages/WorklistPage";
import { UploadPage } from "./pages/UploadPage";
import { StudyDetailPage } from "./pages/StudyDetailPage";
import { AuditPage } from "./pages/AuditPage";
import { DicomSourcesPage } from "./pages/DicomSourcesPage";

function AuditRoute() {
  const { roles } = useAuth();
  if (!roles.includes("ADMIN") && !roles.includes("AUDITOR")) {
    return <Navigate to="/worklist" replace />;
  }
  return <AuditPage />;
}

function AdminRoute() {
  const { roles } = useAuth();
  if (!roles.includes("ADMIN")) {
    return <Navigate to="/worklist" replace />;
  }
  return <DicomSourcesPage />;
}

function Router() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/worklist" replace />} />
        <Route path="worklist" element={<WorklistPage />} />
        <Route path="upload" element={<UploadPage />} />
        <Route path="studies/:id" element={<StudyDetailPage />} />
        <Route path="audit" element={<AuditRoute />} />
        <Route path="admin/dicom" element={<AdminRoute />} />
        <Route path="*" element={<Navigate to="/worklist" replace />} />
      </Route>
    </Routes>
  );
}

export function App() {
  return (
    <AuthProvider>
      <Router />
    </AuthProvider>
  );
}
