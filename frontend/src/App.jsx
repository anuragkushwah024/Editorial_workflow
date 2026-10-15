import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./AuthContext";
import Layout from "./components/Layout";
import RequireAuth from "./components/RequireAuth";
import AlertsPage from "./pages/AlertsPage";
import ArticleFormPage from "./pages/ArticleFormPage";
import ArticlePage from "./pages/ArticlePage";
import ArticlesPage from "./pages/ArticlesPage";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import SectionDetailPage from "./pages/SectionDetailPage";
import SectionsPage from "./pages/SectionsPage";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route path="/" element={<HomePage />} />
            <Route path="/sections" element={<SectionsPage />} />
            <Route path="/sections/:id" element={<SectionDetailPage />} />
            <Route path="/articles" element={<ArticlesPage />} />
            <Route path="/articles/new" element={<ArticleFormPage />} />
            <Route path="/articles/:id" element={<ArticlePage />} />
            <Route path="/articles/:id/edit" element={<ArticleFormPage />} />
            <Route path="/alerts" element={<AlertsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
