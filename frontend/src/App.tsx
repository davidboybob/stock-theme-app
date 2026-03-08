import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import IndexBar from "./components/IndexBar";
import Dashboard from "./pages/Dashboard";
import ThemeDetail from "./pages/ThemeDetail";
import Alerts from "./pages/Alerts";
import "./App.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 25000,
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="app">
          <header className="app-header">
            <div className="header-top">
              <h1 className="app-title">테마주 분석</h1>
              <nav className="app-nav">
                <NavLink to="/" end className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
                  대시보드
                </NavLink>
                <NavLink to="/alerts" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
                  알림
                </NavLink>
              </nav>
            </div>
            <IndexBar />
          </header>

          <main className="app-main">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/themes/:id" element={<ThemeDetail />} />
              <Route path="/alerts" element={<Alerts />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
