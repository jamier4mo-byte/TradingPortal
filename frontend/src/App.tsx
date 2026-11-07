import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import AppShell from "./components/AppShell.tsx";
import { SkeletonCard } from "./components/ui/index.ts";
import { RequireAdmin, RequireAuth } from "./lib/auth.tsx";
import Hub from "./pages/Hub.tsx";

// Every tool page is lazy-loaded so the Hub's first load stays under the 200KB budget (F18).
const Login = lazy(() => import("./pages/auth/Login.tsx"));
const AcceptInvite = lazy(() => import("./pages/auth/AcceptInvite.tsx"));
const ResetPassword = lazy(() => import("./pages/auth/ResetPassword.tsx"));
const Settings = lazy(() => import("./pages/Settings.tsx"));
const Tags = lazy(() => import("./pages/Tags.tsx"));
const More = lazy(() => import("./pages/More.tsx"));
const AdminUsers = lazy(() => import("./pages/admin/Users.tsx"));
const Components = lazy(() => import("./pages/dev/Components.tsx"));
const Placeholder = lazy(() => import("./pages/Placeholder.tsx"));
const CalendarPage = lazy(() => import("./pages/calendar/Calendar.tsx"));
const JournalIndex = lazy(() => import("./pages/journal/JournalIndex.tsx"));
const StrategyPage = lazy(() => import("./pages/journal/StrategyPage.tsx"));
const TradeDetail = lazy(() => import("./pages/journal/TradeDetail.tsx"));
const Annotate = lazy(() => import("./pages/journal/Annotate.tsx"));
const Matcher = lazy(() => import("./pages/journal/Matcher.tsx"));
const JournalTrash = lazy(() => import("./pages/journal/Trash.tsx"));
const JournalAnalytics = lazy(() => import("./pages/journal/AnalyticsPage.tsx"));
const NewsRoom = lazy(() => import("./pages/news/NewsRoom.tsx"));
const EventDetail = lazy(() => import("./pages/news/EventDetail.tsx"));
const AlertsSettings = lazy(() => import("./pages/news/AlertsSettings.tsx"));
const Markets = lazy(() => import("./pages/markets/Markets.tsx"));
const InstrumentView = lazy(() => import("./pages/markets/InstrumentView.tsx"));

function Loading() {
  return (
    <div className="grid grid-cols-4 gap-4 tablet:grid-cols-8 laptop:grid-cols-12">
      <SkeletonCard className="col-span-full" />
      <SkeletonCard className="col-span-full laptop:col-span-6" />
      <SkeletonCard className="col-span-full laptop:col-span-6" />
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={null}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/invite/:token" element={<AcceptInvite />} />
        <Route path="/reset/:token" element={<ResetPassword />} />
        <Route
          path="/*"
          element={
            <RequireAuth>
              <AppShell>
                <Suspense fallback={<Loading />}>
                  <Routes>
                    <Route path="/" element={<Hub />} />
                    <Route path="/journal" element={<JournalIndex />} />
                    <Route path="/journal/trash" element={<JournalTrash />} />
                    <Route path="/journal/analytics" element={<JournalAnalytics />} />
                    <Route path="/journal/strategies/:id" element={<StrategyPage />} />
                    <Route path="/journal/strategies/:id/trades/:tradeId" element={<TradeDetail />} />
                    <Route path="/journal/sessions/:sid/annotate" element={<Annotate />} />
                    <Route path="/journal/sessions/:sid/match" element={<Matcher />} />
                    <Route path="/news" element={<NewsRoom />} />
                    <Route path="/news/week" element={<NewsRoom initialView="ahead" />} />
                    <Route path="/news/events/:id" element={<EventDetail />} />
                    <Route path="/markets" element={<Markets />} />
                    <Route path="/markets/:symbol" element={<InstrumentView />} />
                    <Route path="/settings/alerts" element={<AlertsSettings />} />
                    <Route path="/calendar" element={<CalendarPage />} />
                    <Route path="/tags" element={<Tags />} />
                    <Route path="/settings" element={<Settings />} />
                    <Route path="/more" element={<More />} />
                    <Route path="/admin" element={<Navigate to="/admin/users" replace />} />
                    <Route
                      path="/admin/users"
                      element={
                        <RequireAdmin>
                          <AdminUsers />
                        </RequireAdmin>
                      }
                    />
                    <Route
                      path="/admin/tags"
                      element={
                        <RequireAdmin>
                          <Tags admin />
                        </RequireAdmin>
                      }
                    />
                    <Route path="/dev/components" element={<Components />} />
                    <Route path="*" element={<Placeholder title="Not found" text="There's no page at this address. Check the link, or head back to the Hub." />} />
                  </Routes>
                </Suspense>
              </AppShell>
            </RequireAuth>
          }
        />
      </Routes>
    </Suspense>
  );
}
