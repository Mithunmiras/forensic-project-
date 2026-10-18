import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { Card, PageHeader, Spinner } from "./components/ui";
import { makeQueryClient } from "./queryClient";

// Route-level code splitting keeps the first load small (charts are only fetched when a page needs them).
const Overview = lazy(() => import("./pages/Overview"));
const Assistant = lazy(() => import("./pages/Assistant"));
const Predict = lazy(() => import("./pages/Predict"));
const Knowledge = lazy(() => import("./pages/Knowledge"));
const Status = lazy(() => import("./pages/Status"));
const About = lazy(() => import("./pages/About"));

function NotFound() {
  return (
    <>
      <PageHeader title="Page not found" />
      <Card>
        <p className="text-sm text-slate-600">That page does not exist. Use the navigation on the left.</p>
      </Card>
    </>
  );
}

export default function App({ client = makeQueryClient() }: { client?: QueryClient }) {
  return (
    <QueryClientProvider client={client}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Suspense fallback={<div className="p-8"><Spinner label="Loading page" /></div>}>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Overview />} />
              <Route path="assistant" element={<Assistant />} />
              <Route path="predict" element={<Predict />} />
              <Route path="knowledge" element={<Knowledge />} />
              <Route path="status" element={<Status />} />
              <Route path="about" element={<About />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
