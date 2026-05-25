const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000"

export interface SearchResult {
  filename: string
  score: number
  snippet: string
}

export interface SearchResponse {
  query: string
  results: SearchResult[]
}

export interface IndexStatus {
  exists: boolean
}

export interface PipelineResponse {
  total: number
  results: Record<string, Record<string, unknown>>
}

export interface UploadResponse {
  filename: string
  size: number
  saved_to: string
}

export interface ChatSource {
  filename: string
  snippet: string
  score: number
}

export interface ChatResponse {
  answer: string
  sources: ChatSource[]
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(BASE + url, options)
  const data = await res.json()
  if (!res.ok) {
    throw new Error((data as { detail?: string })?.detail ?? `HTTP ${res.status}`)
  }
  return data as T
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  indexStatus: () => request<IndexStatus>("/index/status"),

  runPipeline: (body: {
    input_folder: string
    output_path?: string
    rebuild_index?: boolean
    filenames?: string[]
  }) =>
    request<PipelineResponse>("/pipeline/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  getResults: () => request<Record<string, Record<string, unknown>>>("/results"),

  search: (query: string, top_k = 5) =>
    request<SearchResponse>("/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_k }),
    }),

  upload: (file: File) => {
    const form = new FormData()
    form.append("file", file)
    return request<UploadResponse>("/documents/upload", {
      method: "POST",
      body: form,
    })
  },

  chat: (question: string, top_k = 3) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k }),
    }),
}
