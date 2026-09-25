import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { API } from "../api";

export default function Prompt() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["prompt"],
    queryFn: API.getPrompt,
  });

  const [draft, setDraft] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ type: "ok" | "error"; msg: string } | null>(null);

  const activePrompt = draft ?? data?.prompt ?? "";
  const isDirty = draft !== null && draft !== (data?.prompt ?? "");
  const charCount = activePrompt.length;
  const canSave = isDirty && activePrompt.trim().length >= 10 && !saving;

  const save = async () => {
    setSaving(true);
    setStatus(null);
    try {
      await API.updatePrompt(activePrompt);
      qc.invalidateQueries({ queryKey: ["prompt"] });
      setDraft(null);
      setStatus({ type: "ok", msg: "System prompt saved. It applies to new conversations." });
    } catch (e: any) {
      setStatus({ type: "error", msg: `Failed to save: ${e?.message ?? e}` });
    } finally {
      setSaving(false);
    }
  };

  const reset = async () => {
    if (!confirm("Restore the default system prompt? Your custom prompt will be replaced.")) return;
    setSaving(true);
    setStatus(null);
    try {
      await API.resetPrompt();
      qc.invalidateQueries({ queryKey: ["prompt"] });
      setDraft(null);
      setStatus({ type: "ok", msg: "Default system prompt restored." });
    } catch (e: any) {
      setStatus({ type: "error", msg: `Failed to reset: ${e?.message ?? e}` });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>System Prompt</h1>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button onClick={reset} disabled={saving}>
            ↺ Reset to Default
          </button>
          <button
            onClick={save}
            disabled={!canSave}
            className={canSave ? "primary" : ""}
          >
            {saving ? "Saving…" : "💾 Save Prompt"}
          </button>
        </div>
      </div>

      <p style={{ color: "#6b7280", marginTop: "0.25rem" }}>
        Customize how the AI assistant responds. Changes take effect immediately for
        new conversations.
      </p>

      {status && (
        <div
          className={status.type === "ok" ? "save-ok" : "save-error"}
          style={{
            padding: "0.6rem 0.75rem",
            borderRadius: "0.375rem",
            marginBottom: "0.75rem",
            fontSize: "0.875rem",
            background: status.type === "ok" ? "#ecfdf5" : "#fef2f2",
            color: status.type === "ok" ? "#047857" : "#b91c1c",
            border: `1px solid ${status.type === "ok" ? "#a7f3d0" : "#fecaca"}`,
          }}
        >
          {status.msg}
        </div>
      )}

      {isLoading && activePrompt === "" ? (
        <p>Loading prompt…</p>
      ) : (
        <>
          <textarea
            value={activePrompt}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Enter system prompt..."
            rows={20}
            disabled={saving}
            style={{
              width: "100%",
              padding: "0.75rem",
              border: "1px solid #d1d5db",
              borderRadius: "0.375rem",
              fontSize: "0.875rem",
              fontFamily: "monospace",
              resize: "vertical",
              lineHeight: 1.5,
            }}
          />
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginTop: "0.5rem",
              color: activePrompt.trim().length < 10 ? "#b91c1c" : "#6b7280",
              fontSize: "0.8rem",
            }}
          >
            <span>
              {charCount} characters · {activePrompt.split(/\s+/).filter(Boolean).length} words
              {activePrompt.trim().length < 10 && " · must be at least 10 characters"}
            </span>
            <span>{isDirty ? "Unsaved changes" : "All changes saved"}</span>
          </div>
        </>
      )}
    </div>
  );
}