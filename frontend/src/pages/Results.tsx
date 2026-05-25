import { Fragment, useEffect, useState } from "react"
import { RefreshCw, FileText, AlertCircle, BarChart3, Plus, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"

const CLASS_COLORS: Record<string, string> = {
  Invoice: "bg-blue-50 text-blue-700 border-blue-200",
  Resume: "bg-purple-50 text-purple-700 border-purple-200",
  "Utility Bill": "bg-amber-50 text-amber-700 border-amber-200",
  Other: "bg-zinc-50 text-zinc-600 border-zinc-200",
  Unclassifiable: "bg-red-50 text-red-600 border-red-200",
}

const STAT_COLORS: Record<string, string> = {
  Invoice: "text-blue-600",
  Resume: "text-purple-600",
  "Utility Bill": "text-amber-600",
  Other: "text-zinc-500",
  Unclassifiable: "text-red-500",
}

const CLASS_ORDER = ["Invoice", "Resume", "Utility Bill", "Other", "Unclassifiable"]

type Row = [string, Record<string, unknown>]

const th = "text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wide whitespace-nowrap"
const td = "px-4 py-3.5 text-sm"

function val(v: unknown, prefix = "") {
  if (v == null || String(v).trim() === "") return <span className="text-muted-foreground">—</span>
  return <span>{prefix}{String(v)}</span>
}

function FileCell({ name }: { name: string }) {
  return (
    <div className="flex items-center gap-2">
      <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
      <span className="font-mono text-xs truncate max-w-[160px]" title={name}>{name}</span>
    </div>
  )
}

function ExpandToggle({ open, onClick }: { open: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="h-6 w-6 rounded-full border flex items-center justify-center text-muted-foreground hover:bg-muted transition-colors"
      title={open ? "Collapse" : "View raw JSON"}
    >
      {open ? <X className="h-3 w-3" /> : <Plus className="h-3 w-3" />}
    </button>
  )
}

function JsonRow({ filename, data, colSpan }: { filename: string; data: Record<string, unknown>; colSpan: number }) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-4 py-0 pb-4">
        <pre className="text-xs font-mono overflow-x-auto rounded-md bg-zinc-950 text-zinc-100 p-4 leading-relaxed">
          {JSON.stringify({ [filename]: data }, null, 2)}
        </pre>
      </td>
    </tr>
  )
}

function useExpandable() {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const toggle = (name: string) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(name) ? next.delete(name) : next.add(name)
      return next
    })
  return { expanded, toggle }
}

function InvoiceTable({ rows }: { rows: Row[] }) {
  const { expanded, toggle } = useExpandable()
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b bg-muted/40">
          <th className={th}>File</th>
          <th className={th}>Invoice #</th>
          <th className={th}>Issue Date</th>
          <th className={th}>Due Date</th>
          <th className={th}>Company</th>
          <th className={th}>Total Amount</th>
          <th className={th}></th>
        </tr>
      </thead>
      <tbody className="divide-y">
        {rows.map(([filename, d]) => (
          <Fragment key={filename}>
            <tr className="hover:bg-muted/30 transition-colors">
              <td className={td}><FileCell name={filename} /></td>
              <td className={td}>{val(d.invoice_number, "#")}</td>
              <td className={cn(td, "font-mono text-xs")}>{val(d.issue_date)}</td>
              <td className={cn(td, "font-mono text-xs")}>{val(d.due_date)}</td>
              <td className={td}>{val(d.company)}</td>
              <td className={cn(td, "text-blue-700 font-medium")}>{val(d.total_amount, "$")}</td>
              <td className={cn(td, "text-right pr-4")}>
                <ExpandToggle open={expanded.has(filename)} onClick={() => toggle(filename)} />
              </td>
            </tr>
            {expanded.has(filename) && (
              <JsonRow filename={filename} data={d} colSpan={7} />
            )}
          </Fragment>
        ))}
      </tbody>
    </table>
  )
}

function ResumeTable({ rows }: { rows: Row[] }) {
  const { expanded, toggle } = useExpandable()
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b bg-muted/40">
          <th className={th}>File</th>
          <th className={th}>Name</th>
          <th className={th}>Email</th>
          <th className={th}>Phone</th>
          <th className={th}>Experience (yrs)</th>
          <th className={th}></th>
        </tr>
      </thead>
      <tbody className="divide-y">
        {rows.map(([filename, d]) => (
          <Fragment key={filename}>
            <tr className="hover:bg-muted/30 transition-colors">
              <td className={td}><FileCell name={filename} /></td>
              <td className={cn(td, "font-medium")}>{val(d.name)}</td>
              <td className={cn(td, "text-muted-foreground")}>{val(d.email)}</td>
              <td className={cn(td, "text-muted-foreground")}>{val(d.phone)}</td>
              <td className={td}>{val(d.experience_years)}</td>
              <td className={cn(td, "text-right pr-4")}>
                <ExpandToggle open={expanded.has(filename)} onClick={() => toggle(filename)} />
              </td>
            </tr>
            {expanded.has(filename) && (
              <JsonRow filename={filename} data={d} colSpan={6} />
            )}
          </Fragment>
        ))}
      </tbody>
    </table>
  )
}

function UtilityTable({ rows }: { rows: Row[] }) {
  const { expanded, toggle } = useExpandable()
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b bg-muted/40">
          <th className={th}>File</th>
          <th className={th}>Account #</th>
          <th className={th}>Issue Date</th>
          <th className={th}>Due Date</th>
          <th className={th}>Usage (kWh)</th>
          <th className={th}>Amount Due</th>
          <th className={th}></th>
        </tr>
      </thead>
      <tbody className="divide-y">
        {rows.map(([filename, d]) => (
          <Fragment key={filename}>
            <tr className="hover:bg-muted/30 transition-colors">
              <td className={td}><FileCell name={filename} /></td>
              <td className={cn(td, "font-mono text-xs")}>{val(d.account_number)}</td>
              <td className={cn(td, "font-mono text-xs")}>{val(d.issue_date)}</td>
              <td className={cn(td, "font-mono text-xs")}>{val(d.due_date)}</td>
              <td className={td}>{val(d.usage_kwh)}</td>
              <td className={cn(td, "text-amber-700 font-medium")}>{val(d.amount_due, "$")}</td>
              <td className={cn(td, "text-right pr-4")}>
                <ExpandToggle open={expanded.has(filename)} onClick={() => toggle(filename)} />
              </td>
            </tr>
            {expanded.has(filename) && (
              <JsonRow filename={filename} data={d} colSpan={7} />
            )}
          </Fragment>
        ))}
      </tbody>
    </table>
  )
}

function OtherTable({ rows }: { rows: Row[] }) {
  const { expanded, toggle } = useExpandable()
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b bg-muted/40">
          <th className={th}>File</th>
          <th className={th}>Note</th>
          <th className={th}></th>
        </tr>
      </thead>
      <tbody className="divide-y">
        {rows.map(([filename, d]) => (
          <Fragment key={filename}>
            <tr className="hover:bg-muted/30 transition-colors">
              <td className={td}><FileCell name={filename} /></td>
              <td className={cn(td, "text-xs text-muted-foreground italic")}>No fields extracted</td>
              <td className={cn(td, "text-right pr-4")}>
                <ExpandToggle open={expanded.has(filename)} onClick={() => toggle(filename)} />
              </td>
            </tr>
            {expanded.has(filename) && (
              <JsonRow filename={filename} data={d} colSpan={3} />
            )}
          </Fragment>
        ))}
      </tbody>
    </table>
  )
}

function ClassSection({ cls, rows }: { cls: string; rows: Row[] }) {
  return (
    <Card>
      <CardHeader className="pb-0">
        <div className="flex items-center gap-3">
          <span className={cn("text-xs px-2 py-0.5 rounded-md border font-medium", CLASS_COLORS[cls] ?? "bg-zinc-50 border-zinc-200")}>
            {cls}
          </span>
          <CardDescription>{rows.length} document{rows.length !== 1 ? "s" : ""}</CardDescription>
        </div>
      </CardHeader>
      <CardContent className="p-0 mt-4">
        <div className="overflow-x-auto">
          {cls === "Invoice" && <InvoiceTable rows={rows} />}
          {cls === "Resume" && <ResumeTable rows={rows} />}
          {cls === "Utility Bill" && <UtilityTable rows={rows} />}
          {(cls === "Other" || cls === "Unclassifiable") && <OtherTable rows={rows} />}
        </div>
      </CardContent>
    </Card>
  )
}

export default function ResultsPage() {
  const [results, setResults] = useState<Record<string, Record<string, unknown>> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getResults()
      setResults(data)
    } catch (err) {
      setError(String(err))
      setResults(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const total = results ? Object.keys(results).length : 0

  const grouped = results
    ? Object.entries(results).reduce<Record<string, Row[]>>((acc, [filename, data]) => {
        const cls = String(data.class ?? "Unknown")
        ;(acc[cls] ??= []).push([filename, data])
        return acc
      }, {})
    : {}

  const classCounts = Object.fromEntries(Object.entries(grouped).map(([k, v]) => [k, v.length]))

  const orderedClasses = [
    ...CLASS_ORDER.filter((c) => grouped[c]),
    ...Object.keys(grouped).filter((c) => !CLASS_ORDER.includes(c)),
  ]

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Extracted Results</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Structured data extracted from your documents.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={cn("h-4 w-4 mr-2", loading && "animate-spin")} />
          Refresh
        </Button>
      </div>

      {/* Error */}
      {error && !loading && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>No Results Available</AlertTitle>
          <AlertDescription>{error} — run the pipeline first.</AlertDescription>
        </Alert>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-40 rounded-lg bg-muted animate-pulse" />
          ))}
        </div>
      )}

      {/* Content */}
      {results && !loading && (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <BarChart3 className="h-3.5 w-3.5 text-muted-foreground" />
                <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Total</p>
              </div>
              <p className="text-2xl font-bold">{total}</p>
            </Card>
            {CLASS_ORDER.filter((c) => classCounts[c]).map((cls) => (
              <Card key={cls} className="p-4">
                <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-2">{cls}</p>
                <p className={cn("text-2xl font-bold", STAT_COLORS[cls] ?? "text-foreground")}>{classCounts[cls]}</p>
              </Card>
            ))}
          </div>

          {/* Per-class sections */}
          {orderedClasses.map((cls) => (
            <ClassSection key={cls} cls={cls} rows={grouped[cls]} />
          ))}
        </>
      )}
    </div>
  )
}
