import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { WorklistPage } from "./pages/WorklistPage";
import { UploadPage } from "./pages/UploadPage";
import { StudyDetailPage } from "./pages/StudyDetailPage";
import { AuditPage } from "./pages/AuditPage";
import { DicomSourcesPage } from "./pages/DicomSourcesPage";
import { ModelsPage } from "./pages/ModelsPage";
import { OverviewPage } from "./pages/OverviewPage";

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

/** Clinicians land on their worklist; admins and auditors, who see no patient data, on governance. */
function Home() {
  const { roles } = useAuth();
  const clinician = roles.includes("RADIOLOGIST") || roles.includes("PHYSICIAN");
  return <Navigate to={clinician ? "/overview" : "/models"} replace />;
}

function Router() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="overview" element={<OverviewPage />} />
        <Route path="worklist" element={<WorklistPage />} />
        <Route path="worklist/:specialty" element={<WorklistPage />} />
        <Route path="models" element={<ModelsPage />} />
        <Route path="upload" element={<UploadPage />} />
        <Route path="studies/:id" element={<StudyDetailPage />} />
        <Route path="audit" element={<AuditRoute />} />
        <Route path="admin/dicom" element={<AdminRoute />} />
        <Route path="*" element={<Home />} />
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
