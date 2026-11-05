import { Route, Routes } from "react-router-dom";

import AppShell from "./components/AppShell.tsx";
import Hub from "./pages/Hub.tsx";
import Placeholder from "./pages/Placeholder.tsx";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Hub />} />
        <Route path="/journal/*" element={<Placeholder title="Replay Journal" logo="/brand/replayjournal-logo.png" />} />
        <Route path="/news/*" element={<Placeholder title="News Room" logo="/brand/newsroom-logo.png" />} />
        <Route path="/calendar" element={<Placeholder title="Calendar" />} />
        <Route path="*" element={<Placeholder title="Not found" />} />
      </Routes>
    </AppShell>
  );
}
