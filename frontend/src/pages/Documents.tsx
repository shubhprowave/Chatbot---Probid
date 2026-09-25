import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { API } from "../api";

type ParamSchema = {
  type: string;
  label: string;
  default: number;
  min: number;
  max: number;
  step?: number;
};

type StrategyMeta = {
  id: string;
  label: string;
  description: string;
  auto: boolean;
  params: Record<string, ParamSchema>;
};

// Used when /admin/chunking/strategies is unreachable or the API is stale,
// so the selector still renders. Mirrors app/ingestion/chunker.py.
const FALLBACK_STRATEGIES: StrategyMeta[] = [
  {
    id: "auto",
    label: "Auto-detect",
    description: "Pick the best strategy automatically from the file type (RECOMMENDED for unknown document structures).",
    auto: true,
    params: {},
  },
  {
    id: "recursive",
    label: "Recursive character",
    description: "Splits on paragraph, sentence and word boundaries. Good default for prose (PDFs, Word, plain text).",
    auto: false,
    params: {
      chunk_size: { type: "int", label: "Chunk size (chars)", default: 800, min: 100, max: 4000 },
      chunk_overlap: { type: "int", label: "Overlap (chars)", default: 120, min: 0, max: 400 },
      min_chars: { type: "int", label: "Min chunk length", default: 30, min: 0, max: 500 },
    },
  },
  {
    id: "fixed",
    label: "Fixed size",
    description: "Hard character-limit chunks, no separator awareness. Use for arbitrary/unstructured text.",
    auto: false,
    params: {
      chunk_size: { type: "int", label: "Chunk size (chars)", default: 800, min: 100, max: 4000 },
      chunk_overlap: { type: "int", label: "Overlap (chars)", default: 0, min: 0, max: 400 },
      min_chars: { type: "int", label: "Min chunk length", default: 30, min: 0, max: 500 },
    },
  },
  {
    id: "markdown",
    label: "Markdown structure",
    description: "Keeps headings as context — ideal for .md docs with sections so retrieval is aware of the structure.",
    auto: false,
    params: {
      max_chars: { type: "int", label: "Max section chars", default: 1200, min: 200, max: 4000 },
      chunk_overlap: { type: "int", label: "Overlap (chars)", default: 100, min: 0, max: 400 },
      min_chars: { type: "int", label: "Min chunk length", default: 30, min: 0, max: 500 },
    },
  },
  {
    id: "json",
    label: "JSON structure",
    description: "Splits JSON documents by nested keys/arrays so each chunk keeps its key path.",
    auto: false,
    params: {
      max_chars: { type: "int", label: "Max chunk chars", default: 1200, min: 200, max: 4000 },
      min_chars: { type: "int", label: "Min chunk length", default: 0, min: 0, max: 1000 },
    },
  },
  {
    id: "page",
    label: "Page",
    description: "One chunk per page. Uses real page boundaries from PDFs (falls back to paragraphs).",
    auto: false,
    params: {
      min_chars: { type: "int", label: "Min chunk length", default: 30, min: 0, max: 500 },
    },
  },
  {
    id: "paragraph",
    label: "Paragraph",
    description: "One chunk per paragraph (blank-line delimited). Long paragraphs are split further.",
    auto: false,
    params: {
      max_chars: { type: "int", label: "Max paragraph chars", default: 1600, min: 200, max: 4000 },
      chunk_overlap: { type: "int", label: "Overlap (chars)", default: 0, min: 0, max: 400 },
      min_chars: { type: "int", label: "Min chunk length", default: 30, min: 0, max: 500 },
    },
  },
  {
    id: "sentence",
    label: "Sentence",
    description: "Groups consecutive sentences into chunks (sentences per chunk + overlap). Good for Q&A content.",
    auto: false,
    params: {
      sentences_per_chunk: { type: "int", label: "Sentences per chunk", default: 5, min: 1, max: 50 },
      sentence_overlap: { type: "int", label: "Overlap (sentences)", default: 1, min: 0, max: 20 },
      max_chars: { type: "int", label: "Max chunk chars", default: 1200, min: 200, max: 4000 },
      min_chars: { type: "int", label: "Min chunk length", default: 30, min: 0, max: 500 },
    },
  },
];

const FIELD_STYLE: React.CSSProperties = {
  padding: '8px',
  fontSize: '13px',
  border: '1.5px solid var(--border-strong, #dde3ec)',
  borderRadius: '10px',
  background: '#fff',
  color: 'var(--text)',
  fontFamily: 'inherit',
};

export default function Documents() {
  const qc = useQueryClient();
  const { data: docs } = useQuery({ queryKey: ["docs"], queryFn: API.documents });
  const { data: stratData } = useQuery({ queryKey: ["chunking"], queryFn: API.chunkingStrategies, retry: 1, staleTime: 60_000 });
  const strategies: StrategyMeta[] =
    stratData?.strategies?.length ? stratData.strategies : FALLBACK_STRATEGIES;
  const [uploading, setUploading] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [showTextModal, setShowTextModal] = useState(false);
  const [strategy, setStrategy] = useState("auto");
  const [chunkParams, setChunkParams] = useState<Record<string, string>>({});

  const upload = async (files: File[]) => {
    if (!files.length) return;
    setUploading(true);
    try {
      const res = await API.uploadDocuments(files, strategy, chunkParams);
      console.log("upload result:", res);
      alert(
        (res.results || [])
          .map((r: any) => `${r.file || "?"} → ${r.status}${r.chunks ? ` (${r.chunks} chunks)` : ""}${r.strategy ? ` [${r.strategy}]` : ""}`)
          .join("\n") || "Uploaded."
      );
      qc.invalidateQueries({ queryKey: ["docs"] });
      qc.invalidateQueries({ queryKey: ["overview"] });
    } catch (e) {
      alert(`Upload failed: ${e}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <h1>Documents</h1>
      <p className="page-desc">Upload files or add text content — they're chunked and embedded for retrieval.</p>

      <div className="upload-bar">
        <input
          type="file"
          multiple
          accept=".pdf,.docx,.txt,.md,.json,.html"
          onChange={(e) => {
            const files = e.target.files ? Array.from(e.target.files) : [];
            e.target.value = "";
            upload(files);
          }}
        />
        <button
          onClick={() => setShowTextModal(true)}
          style={{ marginLeft: '10px' }}
        >
          ➕ Add Text Document
        </button>
        {uploading && <span>Uploading & embedding…</span>}
      </div>

      <ChunkStrategyForm
        strategies={strategies}
        strategy={strategy}
        params={chunkParams}
        onStrategy={setStrategy}
        onParams={setChunkParams}
        compact
      />

      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Filename</th>
              <th>Type</th>
              <th>Chunking</th>
              <th>Chunks</th>
              <th>Size</th>
              <th>Status</th>
              <th>Uploaded</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {docs?.map((d) => (
              <tr key={d.id}>
                <td>{d.title || d.filename}</td>
                <td>{d.source_type}</td>
                <td>
                  {d.chunk_strategy
                    ? <span className="badge">{d.chunk_strategy}</span>
                    : <span className="table-text" style={{ color: 'var(--text-3)' }}>—</span>}
                </td>
                <td>{d.chunk_count}</td>
                <td>{Math.round((d.size_bytes || 0) / 1024)} KB</td>
                <td><span className={`badge ${d.status}`}>{d.status}</span></td>
                <td>{new Date(d.created_at).toLocaleString()}</td>
                <td>
                  <button onClick={() => setSelected(d.id)}>View</button>{" "}
                  <button
                    className="danger"
                    onClick={async () => {
                      if (!confirm(`Delete "${d.filename}"?`)) return;
                      await API.deleteDocument(d.id);
                      qc.invalidateQueries({ queryKey: ["docs"] });
                    }}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected && <ChunkViewer docId={selected} onClose={() => setSelected(null)} />}
      {showTextModal && (
        <TextDocumentModal
          strategies={strategies}
          onClose={() => setShowTextModal(false)}
          onSuccess={() => {
            setShowTextModal(false);
            qc.invalidateQueries({ queryKey: ["docs"] });
          }}
        />
      )}
    </div>
  );
}

// -------------------------------------------------------------------
// Shared strategy selector — rendered dynamically from the API registry
// -------------------------------------------------------------------
function ChunkStrategyForm({
  strategies,
  strategy,
  params,
  onStrategy,
  onParams,
  compact,
}: {
  strategies: StrategyMeta[];
  strategy: string;
  params: Record<string, string>;
  onStrategy: (v: string) => void;
  onParams: (v: Record<string, string>) => void;
  compact?: boolean;
}) {
  const active = strategies.find((s) => s.id === strategy) || strategies.find((s) => s.id === "recursive");

  return (
    <div
      style={{
        margin: compact ? '6px 0 14px' : '12px 0 14px',
        display: 'flex',
        flexWrap: 'wrap',
        gap: '10px',
        alignItems: 'flex-end',
        background: 'var(--surface-2, #f8fafd)',
        border: '1px solid var(--border, #e8ecf3)',
        borderRadius: '12px',
        padding: '10px 12px',
      }}
    >
      <div style={{ minWidth: 200, flex: 1 }}>
        <label style={{ display: 'block', marginBottom: '5px', fontWeight: 600, fontSize: '12.5px' }}>
          Chunking strategy
        </label>
        <select
          value={strategy}
          onChange={(e) => {
            onStrategy(e.target.value);
            onParams({});
          }}
          style={{ width: '100%', ...FIELD_STYLE }}
        >
          {strategies.map((s) => (
            <option key={s.id} value={s.id}>{s.label}</option>
          ))}
        </select>
        {active?.description && (
          <p style={{ margin: '4px 0 0', fontSize: '11.5px', color: 'var(--text-3)' }}>{active.description}</p>
        )}
      </div>

      {strategy !== "auto" &&
        active &&
        Object.entries(active.params).map(([key, schema]) => (
          <div key={key} style={{ width: 150 }}>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 600, fontSize: '12.5px' }}>
              {schema.label}
            </label>
            <input
              type="number"
              value={params[key] ?? schema.default}
              min={schema.min}
              max={schema.max}
              step={schema.step ?? 1}
              onChange={(e) => onParams({ ...params, [key]: e.target.value })}
              style={{ width: '100%', ...FIELD_STYLE }}
            />
          </div>
        ))}
    </div>
  );
}

function TextDocumentModal({
  strategies,
  onClose,
  onSuccess,
}: {
  strategies: StrategyMeta[];
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [strategy, setStrategy] = useState("auto");
  const [chunkParams, setChunkParams] = useState<Record<string, string>>({});

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !text.trim()) {
      alert("Please provide both title and text");
      return;
    }

    setLoading(true);
    try {
      await API.createTextDocument(title, text, strategy, chunkParams);
      alert("Document created and embedded.");
      onSuccess();
    } catch (error) {
      alert(`Failed to create document: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal">
      <div className="modal-body" style={{ maxWidth: '800px' }}>
        <button className="close" onClick={onClose}>✕</button>
        <h2>Add Text Document</h2>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '15px' }}>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
              Title *
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., GEM Registration Guide"
              style={{ width: '100%', padding: '8px', fontSize: '14px' }}
              required
            />
          </div>
          <div style={{ marginBottom: '15px' }}>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
              Text Content *
            </label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste or type your content here..."
              style={{
                width: '100%',
                minHeight: '300px',
                padding: '8px',
                fontSize: '14px',
                fontFamily: 'monospace'
              }}
              required
            />
          </div>

          <ChunkStrategyForm
            strategies={strategies}
            strategy={strategy}
            params={chunkParams}
            onStrategy={setStrategy}
            onParams={setChunkParams}
          />

          <div style={{ display: 'flex', gap: '10px' }}>
            <button type="submit" disabled={loading}>
              {loading ? 'Creating...' : 'Create Document'}
            </button>
            <button type="button" onClick={onClose} disabled={loading}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function ChunkViewer({ docId, onClose }: { docId: string; onClose: () => void }) {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["chunks", docId], queryFn: () => API.docChunks(docId) });
  const [editingChunk, setEditingChunk] = useState<string | null>(null);
  const [editText, setEditText] = useState("");

  const startEdit = (chunkId: string, currentText: string) => {
    setEditingChunk(chunkId);
    setEditText(currentText);
  };

  const saveEdit = async (chunkId: string) => {
    try {
      await API.updateChunk(chunkId, editText);
      qc.invalidateQueries({ queryKey: ["chunks", docId] });
      setEditingChunk(null);
      alert("Chunk updated and re-embedded successfully!");
    } catch (error) {
      alert(`Failed to update chunk: ${error}`);
    }
  };

  const deleteChunk = async (chunkId: string) => {
    if (!confirm("Delete this chunk?")) return;
    try {
      await API.deleteChunk(chunkId);
      qc.invalidateQueries({ queryKey: ["chunks", docId] });
    } catch (error) {
      alert(`Failed to delete chunk: ${error}`);
    }
  };

  return (
    <div className="modal">
      <div className="modal-body">
        <button className="close" onClick={onClose}>✕</button>
        <h2>Chunks ({data?.length || 0})</h2>
        <div className="chunks">
          {data?.map((c) => (
            <div key={c.id} className="chunk">
              <div className="chunk-meta">
                #{c.chunk_index} · {c.char_count} chars ·{" "}
                {c.has_embedding ? "✅ embedded" : "❌ missing"}
                <div style={{ float: 'right' }}>
                  {editingChunk === c.id ? (
                    <>
                      <button onClick={() => saveEdit(c.id)} style={{ marginRight: '5px' }}>
                        💾 Save
                      </button>
                      <button onClick={() => setEditingChunk(null)}>
                        ✕ Cancel
                      </button>
                    </>
                  ) : (
                    <>
                      <button onClick={() => startEdit(c.id, c.text)} style={{ marginRight: '5px' }}>
                        ✏️ Edit
                      </button>
                      <button onClick={() => deleteChunk(c.id)} className="danger">
                        🗑️ Delete
                      </button>
                    </>
                  )}
                </div>
              </div>
              {editingChunk === c.id ? (
                <textarea
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  style={{
                    width: '100%',
                    minHeight: '150px',
                    fontFamily: 'monospace',
                    padding: '10px',
                    fontSize: '13px'
                  }}
                />
              ) : (
                <pre>{c.text}</pre>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}