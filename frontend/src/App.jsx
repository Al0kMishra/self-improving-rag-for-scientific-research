import Sidebar from "./components/Sidebar.jsx";
import { useHashRoute } from "./hooks/useHashRoute.js";
import ExperimentsPage from "./pages/ExperimentsPage.jsx";
import ImprovementPage from "./pages/ImprovementPage.jsx";
import ResearchPage from "./pages/ResearchPage.jsx";
import SystemPage from "./pages/SystemPage.jsx";

function Page({ route }) {
  switch (route.page) {
    case "query":
      return <ResearchPage queryId={route.params[0]} />;
    case "improvement":
      return <ImprovementPage run={route.params[0] ?? null} />;
    case "experiments":
      return <ExperimentsPage run={route.params[0] ?? null} />;
    case "system":
      return <SystemPage />;
    default:
      return <ResearchPage />;
  }
}

export default function App() {
  const route = useHashRoute();
  return (
    <div className="shell">
      <Sidebar active={route.page} />
      <main className="main">
        <Page route={route} />
      </main>
    </div>
  );
}
