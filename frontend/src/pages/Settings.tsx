import { useEffect, useState } from "react";
import { Api, SettingsOut, SettingsPatch, SourceStatus } from "../lib/api";

export default function Settings() {
  const [eff, setEff] = useState<SettingsOut | null>(null);
  const [sources, setSources] = useState<SourceStatus[]>([]);
  const [enabled, setEnabled] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function reload() {
    const s = await Api.getSettings();
    setEff(s);
    setEnabled(s.enabled_sources);
    setSources(await Api.sources());
  }
  useEffect(() => { reload().catch(() => setMsg("無法讀取目前設定")); }, []);

  async function save() {
    setBusy(true); setMsg("");
    try {
      const patch: SettingsPatch = {
        enabled_sources: enabled,
      };
      const updated = await Api.updateSettings(patch);
      setEff(updated);
      setEnabled(updated.enabled_sources);
      setSources(await Api.sources());
      setMsg("✅ 已儲存,新設定立即生效");
    } catch (e: any) {
      setMsg("❌ 儲存失敗:" + (e?.response?.data?.detail ?? e.message));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "32px 24px" }}>
      <header style={{ marginBottom: 24, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 24 }}>⚙️ 設定</h1>
          <p style={{ color: "#8b949e", marginTop: 4 }}>
            修改後寫進 <code>data/settings.json</code>,重啟也不會掉
          </p>
        </div>
        <a href="#" style={{ fontSize: 14 }}>← 返回查詢</a>
      </header>

      <Section title="來源">
        <Field label="啟用的 metadata 來源" hint="停用的來源不參與搜尋(source=all 會跳過,指名查詢會回錯誤);立即生效">
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {sources.map(s => (
              <label key={s.name} style={{
                display: "flex", alignItems: "center", gap: 10,
                background: "#0d1117", border: "1px solid #30363d", borderRadius: 6,
                padding: "8px 10px", cursor: "pointer",
              }}>
                <input
                  type="checkbox"
                  checked={enabled.includes(s.name)}
                  onChange={e => setEnabled(
                    e.target.checked
                      ? [...enabled, s.name]
                      : enabled.filter(n => n !== s.name)
                  )}
                />
                <span style={{ fontWeight: 600, width: 110 }}>{s.name}</span>
                <span style={{ fontSize: 12, color: "#3fb950" }}>✓ 可用</span>
              </label>
            ))}
          </div>
        </Field>
      </Section>

      <div style={{ marginTop: 24, display: "flex", gap: 10, alignItems: "center" }}>
        <button onClick={save} disabled={busy}>{busy ? "儲存中…" : "儲存設定"}</button>
        <button onClick={reload} disabled={busy} style={{ background: "#30363d" }}>還原成目前值</button>
        {msg && <span style={{ color: "#8b949e" }}>{msg}</span>}
      </div>

      {eff && (
        <div style={{ marginTop: 32, padding: 16, background: "#161b22", border: "1px solid #21262d", borderRadius: 8 }}>
          <div style={{ color: "#8b949e", fontSize: 13, marginBottom: 8 }}>目前生效</div>
          <pre style={{ margin: 0, color: "#c9d1d9", fontSize: 12, whiteSpace: "pre-wrap" }}>
{JSON.stringify(eff, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginTop: 20 }}>
      <h3 style={{ margin: "0 0 12px", fontSize: 15, color: "#c9d1d9" }}>{title}</h3>
      <div style={{ padding: 16, background: "#161b22", border: "1px solid #21262d", borderRadius: 8 }}>
        {children}
      </div>
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 13, color: "#c9d1d9", marginBottom: 4 }}>{label}</div>
      {children}
      {hint && <div style={{ fontSize: 12, color: "#6e7681", marginTop: 4 }}>{hint}</div>}
    </div>
  );
}
