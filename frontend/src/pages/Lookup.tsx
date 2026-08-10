import { useEffect, useState } from "react";
import { Api, MetadataResult, SourceDetail, proxyImage } from "../lib/api";

const ACCENT: Record<string, string> = {
  javbus: "#d81b60",
  javtrailers: "#7e57c2",
  missav: "#ffa000",
};

export default function Lookup() {
  const [q, setQ] = useState("");
  const [result, setResult] = useState<MetadataResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function search(term = q.trim()) {
    if (!term) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      setResult(await Api.metadata(term));
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e.message ?? "查詢失敗");
    } finally {
      setLoading(false);
    }
  }

  // 支援 ?q= 深連結：開頁自動帶入並查詢
  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get("q");
    if (initial) {
      setQ(initial);
      search(initial);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px" }}>
      <header style={{ marginBottom: 32, display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 28 }}>🎬 影片 Metadata 查詢</h1>
          <p style={{ color: "#8b949e", marginTop: 6 }}>
            以番號同時查 JavBus / JavTrailers / MissAV，所有來源使用相同 schema
          </p>
        </div>
        <nav style={{ display: "flex", gap: 14, fontSize: 15, paddingTop: 6 }}>
          <a href="#settings">⚙️ 設定</a>
        </nav>
      </header>

      <div style={{ display: "flex", gap: 10, marginBottom: 24 }}>
        <input
          autoFocus
          value={q}
          onChange={e => setQ(e.target.value)}
          onKeyDown={e => e.key === "Enter" && search()}
          placeholder="輸入番號,例如:SSIS-001、CAWD-088"
          style={{ flex: 1, fontSize: 16, padding: "10px 14px" }}
        />
        <button onClick={() => search()} disabled={loading} style={{ fontSize: 15, padding: "10px 22px" }}>
          {loading ? "查詢中…" : "查詢"}
        </button>
      </div>

      {error && (
        <div style={{ background: "#3d1a1d", border: "1px solid #a40e26", padding: 12, borderRadius: 6, marginBottom: 16 }}>
          ❌ {String(typeof error === "object" ? JSON.stringify(error) : error)}
        </div>
      )}

      {result && (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))",
          gap: 20,
        }}>
          {result.sources.map((d, i) => (
            <SourceCard key={`${d.source}-${d.id}-${i}`} d={d} />
          ))}
        </div>
      )}

      {!result && !loading && !error && (
        <div style={{ color: "#6e7681", textAlign: "center", marginTop: 80 }}>
          輸入番號後按 Enter
        </div>
      )}
    </div>
  );
}

function SourceCard({ d }: { d: SourceDetail }) {
  const accent = ACCENT[d.source] ?? "#8b949e";
  const label = d.source.toUpperCase();

  if (!d.id) {
    return (
      <div style={{
        background: "#0d1117", border: "1px dashed #30363d", borderRadius: 10,
        padding: 40, textAlign: "center", color: "#6e7681",
      }}>
        {d.source.toUpperCase()} 沒有找到結果
      </div>
    );
  }

  return (
    <div style={{
      background: "#161b22", border: "1px solid #21262d", borderRadius: 10,
      borderTop: `4px solid ${accent}`, padding: 18, overflow: "hidden",
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14, gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <h3 style={{ margin: 0, color: accent }}>{label}</h3>
          <span style={{
            background: "#21262d", color: "#c9d1d9",
            padding: "2px 8px", borderRadius: 10, fontSize: 12, fontWeight: 600,
          }}>
            {d.code}
          </span>
        </div>
        <div style={{ display: "flex", gap: 12, fontSize: 13, flexShrink: 0 }}>
          <a href={`/api/metadata/${d.source}/${d.id}`} target="_blank" rel="noreferrer">JSON</a>
          {d.url && <a href={d.url} target="_blank" rel="noreferrer">原站連結 →</a>}
        </div>
      </div>

      <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
        {d.images.poster && (
          <img src={proxyImage(d.images.poster, "cover")} alt=""
               style={{ width: 130, height: 184, objectFit: "cover", borderRadius: 6, flexShrink: 0, background: "#0d1117" }} />
        )}
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 17, fontWeight: 700, lineHeight: 1.4, wordBreak: "break-word" }}>
            {d.title || "(無標題)"}
          </div>
        </div>
      </div>

      <Row label="發行日" value={d.premiered} />
      <Row label="片長" value={d.runtime ? `${d.runtime} 分` : ""} />
      <Row label="導演" value={d.directors.map(p => p.name).join("、")} />
      <Row label="製作商" value={d.studio} />
      <Row label="發行商" value={d.label} />
      <Row label="系列" value={d.series} />

      <Block label="類別">
        <Chips items={d.genres} />
      </Block>

      <Block label={`演員 (${d.actors.length})`}>
        {d.actors.length > 0 ? (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {d.actors.map((a, i) => (
              <span key={i} style={{
                display: "inline-flex", alignItems: "center", gap: 6,
                background: "#21262d", color: "#c9d1d9", padding: "3px 10px 3px 3px",
                borderRadius: 14, fontSize: 12,
              }}>
                {a.thumb ? (
                  <img src={proxyImage(a.thumb)} alt=""
                       style={{ width: 22, height: 22, borderRadius: "50%", objectFit: "cover" }} />
                ) : (
                  <span style={{
                    width: 22, height: 22, borderRadius: "50%", background: "#30363d",
                    display: "inline-flex", alignItems: "center", justifyContent: "center",
                    fontSize: 11, color: "#8b949e",
                  }}>{a.name.charAt(0)}</span>
                )}
                {a.name}
              </span>
            ))}
          </div>
        ) : (
          <span style={{ color: "#6e7681" }}>—</span>
        )}
      </Block>

      {d.plot && (
        <Block label="簡介">
          <p style={{ whiteSpace: "pre-wrap", margin: 0, lineHeight: 1.7, color: "#c9d1d9", fontSize: 14 }}>
            {d.plot}
          </p>
        </Block>
      )}

      {d.sample_images.length > 0 && (
        <Block label={`劇照 (${d.sample_images.length})`}>
          <div style={{ display: "flex", gap: 6, overflowX: "auto", paddingBottom: 4 }}>
            {d.sample_images.slice(0, 8).map((u, i) => (
              <a key={i} href={proxyImage(u)} target="_blank" rel="noreferrer" style={{ flexShrink: 0 }}>
                <img src={proxyImage(u)} alt=""
                     style={{ height: 70, borderRadius: 4, background: "#0d1117" }} />
              </a>
            ))}
          </div>
        </Block>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  const empty = !value;
  return (
    <div style={{ display: "flex", gap: 12, padding: "6px 0", fontSize: 14 }}>
      <span style={{ color: "#8b949e", width: 70, flexShrink: 0 }}>{label}</span>
      <span style={{ color: empty ? "#6e7681" : "#e6edf3", wordBreak: "break-word" }}>{empty ? "—" : value}</span>
    </div>
  );
}

function Block({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid #21262d" }}>
      <div style={{ color: "#8b949e", fontSize: 13, marginBottom: 8 }}>{label}</div>
      {children}
    </div>
  );
}

function Chips({ items }: { items: string[] }) {
  if (!items.length) return <span style={{ color: "#6e7681" }}>—</span>;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {items.map((t, i) => (
        <span key={i} style={{
          background: "#21262d", color: "#c9d1d9", padding: "3px 9px",
          borderRadius: 12, fontSize: 12,
        }}>{t}</span>
      ))}
    </div>
  );
}
