import { useState, useRef, type DragEvent, type ChangeEvent } from "react"
import { Upload, Play, CheckCircle2, AlertCircle, FileText, RotateCcw, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
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

const UPLOAD_FOLDER = "./documents"
const OUTPUT_PATH = "./output.json"

export default function PipelinePage() {
  const [dragging, setDragging] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([])
  const [uploading, setUploading] = useState(false)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<Record<string, Record<string, unknown>> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const uploadFiles = async (files: File[]) => {
    const valid = files.filter((f) => f.name.endsWith(".pdf") || f.name.endsWith(".txt"))
    if (!valid.length) return
    setUploading(true)
    try {
      for (const file of valid) {
        await api.upload(file)
        setUploadedFiles((prev) => [...prev.filter((n) => n !== file.name), file.name])
      }
    } catch (err) {
      setError(String(err))
    } finally {
      setUploading(false)
    }
  }

  const handleDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    uploadFiles(Array.from(e.dataTransfer.files))
  }

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) uploadFiles(Array.from(e.target.files))
  }

  const runPipeline = async () => {
    setRunning(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.runPipeline({
        input_folder: UPLOAD_FOLDER,
        output_path: OUTPUT_PATH,
        rebuild_index: false,
        filenames: uploadedFiles,
      })
      setResult(res.results)
    } catch (err) {
      setError(String(err))
    } finally {
      setRunning(false)
    }
  }

  const classCounts = result
    ? Object.values(result).reduce<Record<string, number>>((acc, r) => {
        const c = String(r.class ?? "Unknown")
        acc[c] = (acc[c] ?? 0) + 1
        return acc
      }, {})
    : null

  return (
    <div className="p-8 max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Run Pipeline</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Upload documents and run the full AI extraction pipeline.
        </p>
      </div>

      {/* Upload card — centered */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Upload Documents</CardTitle>
          <CardDescription>PDF and TXT files only</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              "border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors select-none",
              dragging
                ? "border-primary bg-primary/5"
                : "border-border hover:border-primary/40 hover:bg-muted/30"
            )}
          >
            <Upload className="h-7 w-7 mx-auto mb-2 text-muted-foreground" />
            <p className="text-sm font-medium">Drop files here or click to browse</p>
            <p className="text-xs text-muted-foreground mt-1">.pdf · .txt</p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.txt"
              className="hidden"
              onChange={handleFileChange}
            />
          </div>

          {uploadedFiles.length > 0 && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">{uploadedFiles.length} file{uploadedFiles.length !== 1 ? "s" : ""} ready</span>
                <button
                  onClick={() => setUploadedFiles([])}
                  className="text-xs text-muted-foreground hover:text-destructive flex items-center gap-1 transition-colors"
                >
                  <X className="h-3 w-3" /> Clear
                </button>
              </div>
              <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
                {uploadedFiles.map((name) => (
                  <div key={name} className="flex items-center gap-2 text-sm px-2.5 py-1.5 bg-muted rounded-md">
                    <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <span className="truncate flex-1 text-xs font-mono">{name}</span>
                    <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0" />
                  </div>
                ))}
              </div>
            </div>
          )}

          {uploading && (
            <p className="text-xs text-muted-foreground text-center animate-pulse">Uploading…</p>
          )}
        </CardContent>
      </Card>

      {/* Run button */}
      <Button className="w-full" size="lg" onClick={runPipeline} disabled={running || uploading || uploadedFiles.length === 0}>
        {running ? (
          <>
            <RotateCcw className="h-4 w-4 mr-2 animate-spin" />
            Processing…
          </>
        ) : (
          <>
            <Play className="h-4 w-4 mr-2" />
            Run Pipeline
          </>
        )}
      </Button>

      {/* Error */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Results */}
      {result && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-500" />
              Pipeline complete — {Object.keys(result).length} documents processed
            </CardTitle>
            {classCounts && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {Object.entries(classCounts).map(([cls, count]) => (
                  <span
                    key={cls}
                    className={cn(
                      "text-xs px-2 py-0.5 rounded-md border font-medium",
                      CLASS_COLORS[cls] ?? "bg-zinc-50 border-zinc-200"
                    )}
                  >
                    {cls} · {count}
                  </span>
                ))}
              </div>
            )}
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-t bg-muted/40">
                    <th className="text-left px-5 py-3 font-medium text-muted-foreground text-xs uppercase tracking-wide">File</th>
                    <th className="text-left px-5 py-3 font-medium text-muted-foreground text-xs uppercase tracking-wide">Class</th>
                    <th className="text-left px-5 py-3 font-medium text-muted-foreground text-xs uppercase tracking-wide">Key Field</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {Object.entries(result).map(([filename, data]) => {
                    const keyField =
                      data.invoice_number ?? data.name ?? data.account_number ?? "—"
                    return (
                      <tr key={filename} className="hover:bg-muted/30 transition-colors">
                        <td className="px-5 py-3 font-mono text-xs text-muted-foreground truncate max-w-[180px]">
                          {filename}
                        </td>
                        <td className="px-5 py-3">
                          <span
                            className={cn(
                              "text-xs px-2 py-0.5 rounded-md border font-medium",
                              CLASS_COLORS[data.class as string] ?? "bg-zinc-50 border-zinc-200"
                            )}
                          >
                            {data.class as string}
                          </span>
                        </td>
                        <td className="px-5 py-3 text-sm">{String(keyField)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
