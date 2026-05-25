import { useEffect, useState } from "react"
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom"
import { Bot, Brain, FileStack, Search, Zap } from "lucide-react"
import { Separator } from "@/components/ui/separator"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import ChatPage from "@/pages/Chat"
import PipelinePage from "@/pages/Pipeline"
import ResultsPage from "@/pages/Results"
import SearchPage from "@/pages/Search"

function IndexStatusDot() {
  const [exists, setExists] = useState<boolean | null>(null)

  useEffect(() => {
    api
      .indexStatus()
      .then((r) => setExists(r.exists))
      .catch(() => setExists(false))
  }, [])

  return (
    <div className="flex items-center gap-2 text-xs text-sidebar-foreground/60">
      <div
        className={cn(
          "h-2 w-2 rounded-full shrink-0",
          exists === null
            ? "bg-zinc-300 animate-pulse"
            : exists
              ? "bg-green-500"
              : "bg-zinc-400"
        )}
      />
      <span>
        {exists === null ? "Checking…" : exists ? "Index ready" : "Index not built"}
      </span>
    </div>
  )
}

const NAV = [
  { to: "/", icon: Zap, label: "Pipeline" },
  { to: "/results", icon: FileStack, label: "Results" },
  { to: "/search", icon: Search, label: "Search" },
  { to: "/chat", icon: Bot, label: "Chatbot" },
]

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden bg-background">
        {/* ── Sidebar ─────────────────────────────── */}
        <aside className="w-56 shrink-0 border-r border-sidebar-border flex flex-col bg-sidebar">
          <div className="px-5 py-5 flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shrink-0">
              <Brain className="h-4 w-4" />
            </div>
            <div>
              <p className="font-semibold text-sm text-sidebar-foreground leading-none">DocAI</p>
              <p className="text-[11px] text-sidebar-foreground/50 mt-0.5">Document Intelligence</p>
            </div>
          </div>

          <Separator className="bg-sidebar-border" />

          <nav className="flex-1 p-3 space-y-0.5">
            {NAV.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                    isActive
                      ? "bg-sidebar-accent text-sidebar-accent-foreground"
                      : "text-sidebar-foreground/60 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
                  )
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                {label}
              </NavLink>
            ))}
          </nav>

          <div className="p-4 border-t border-sidebar-border">
            <IndexStatusDot />
          </div>
        </aside>

        {/* ── Main content ─────────────────────────── */}
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<PipelinePage />} />
            <Route path="/results" element={<ResultsPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/chat" element={<ChatPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
