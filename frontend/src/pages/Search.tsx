import { useState, type KeyboardEvent } from "react"
import { Search, FileText, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { type SearchResult, api } from "@/lib/api"

export default function SearchPage() {
  const [query, setQuery] = useState("")
  const [topK, setTopK] = useState(5)
  const [results, setResults] = useState<SearchResult[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastQuery, setLastQuery] = useState("")

  const runSearch = async () => {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    setResults(null)
    setLastQuery(query.trim())
    try {
      const res = await api.search(query.trim(), topK)
      setResults(res.results)
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") runSearch()
  }

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Semantic Search</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Search across indexed documents using natural language.
        </p>
      </div>

      {/* Search bar */}
      <div className="flex gap-3 items-end">
        <div className="flex-1 space-y-1.5">
          <Label htmlFor="query">Query</Label>
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground pointer-events-none" />
            <Input
              id="query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder='e.g. "invoice due in January"'
              className="pl-9"
              autoFocus
            />
          </div>
        </div>
        <div className="w-24 space-y-1.5">
          <Label htmlFor="topk">Results</Label>
          <Input
            id="topk"
            type="number"
            min={1}
            max={50}
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
          />
        </div>
        <Button onClick={runSearch} disabled={loading || !query.trim()}>
          {loading ? "Searching…" : "Search"}
        </Button>
      </div>

      {/* Error */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Search Failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Results */}
      {results !== null && (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {results.length > 0
              ? `${results.length} result${results.length !== 1 ? "s" : ""} for "${lastQuery}"`
              : `No results found for "${lastQuery}"`}
          </p>

          {results.map((r, i) => (
            <Card key={r.filename} className="hover:shadow-sm transition-shadow">
              <CardContent className="p-5">
                <div className="flex items-center justify-between gap-4 mb-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-xs font-medium text-muted-foreground w-5 shrink-0 text-right">
                      {i + 1}
                    </span>
                    <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                    <span className="font-mono text-sm font-medium truncate">{r.filename}</span>
                  </div>
                  <div className="flex items-center gap-2.5 shrink-0">
                    <div className="w-24 h-1.5 rounded-full bg-muted overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full"
                        style={{ width: `${Math.min(r.score * 100, 100)}%` }}
                      />
                    </div>
                    <span className="text-xs font-mono text-muted-foreground w-12 text-right">
                      {r.score.toFixed(3)}
                    </span>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed line-clamp-3 pl-7">
                  {r.snippet}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Empty state */}
      {results === null && !loading && !error && (
        <div className="text-center py-20">
          <Search className="h-10 w-10 mx-auto text-muted-foreground/25 mb-3" />
          <p className="text-sm text-muted-foreground">Enter a query above to search your documents</p>
          <p className="text-xs text-muted-foreground/60 mt-1">
            Requires the pipeline to have been run first
          </p>
        </div>
      )}
    </div>
  )
}
