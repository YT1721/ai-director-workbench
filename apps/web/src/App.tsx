import { useEffect, useState, type ComponentType } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { ConfirmProvider } from "./components/ConfirmDialog";
import { AssetsPage } from "./pages/AssetsPage";
import { HomePage } from "./pages/HomePage";
import { StoryboardPage } from "./pages/StoryboardPage";
import { WorkspacePage } from "./pages/WorkspacePage";
import { VideoPackagePage } from "./pages/VideoPackagePage";
import { BatchVideoPage } from "./pages/BatchVideoPage";
import { SettingsPage } from "./pages/SettingsPage";
import { CheckFixPage } from "./pages/CheckFixPage";

const persistentPages: Record<string, ComponentType> = {
  "/": HomePage,
  "/start-plan": WorkspacePage,
  "/assets": AssetsPage,
  "/storyboards": StoryboardPage,
  "/video-package": VideoPackagePage,
  "/batch-video": BatchVideoPage,
  "/settings": SettingsPage,
  "/check-fix": CheckFixPage,
};

function PersistentRouteOutlet() {
  const location = useLocation();
  const currentPath = location.pathname;
  const CurrentPage = persistentPages[currentPath];
  const [visitedPaths, setVisitedPaths] = useState(
    () => new Set([currentPath]),
  );

  useEffect(() => {
    if (!CurrentPage) return;
    setVisitedPaths((current) => {
      if (current.has(currentPath)) return current;
      const next = new Set(current);
      next.add(currentPath);
      return next;
    });
  }, [CurrentPage, currentPath]);

  if (!CurrentPage) return <Navigate to="/" replace />;

  const mountedPaths = visitedPaths.has(currentPath)
    ? [...visitedPaths]
    : [...visitedPaths, currentPath];

  return mountedPaths.map((path) => {
    const Page = persistentPages[path];
    if (!Page) return null;
    const active = path === currentPath;
    return (
      <div key={path} hidden={!active} aria-hidden={!active}>
        <Page />
      </div>
    );
  });
}

export function App() {
  return (
    <ConfirmProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="*" element={<PersistentRouteOutlet />} />
        </Route>
      </Routes>
    </ConfirmProvider>
  );
}
