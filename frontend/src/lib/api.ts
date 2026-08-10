import axios from "axios";

export const api = axios.create({ baseURL: "/api" });

/** Canonical detail schema — every source conforms to this exact shape. */
export interface Person {
  name: string;
}

export interface Actor {
  name: string;
  role: string;
  type: string;
  thumb: string;
}

export interface SourceDetail {
  source: string;
  id: string;
  url: string;
  match_score: number;
  media_type: string;
  code: string;
  title: string;
  original_title: string;
  plot: string;
  year: string;
  premiered: string;
  runtime: string;
  studio: string;
  label: string;
  series: string;
  directors: Person[];
  actors: Actor[];
  genres: string[];
  tags: string[];
  rating: { score: number | null; votes: number | null };
  unique_ids: { code: string };
  images: { poster: string; fanart: string; thumb: string };
  sample_images: string[];
  trailers: string[];
}

export interface MetadataResult {
  query: string;
  sources: SourceDetail[];
}

export interface PreviewItem {
  source: string;
  id: string;
  title_cn: string | null;
  title_native: string | null;
  title_english: string | null;
  year: string | null;
  url: string | null;
  cover: string | null;
  score: number;
  overview: string;
  aliases: string[];
  hint: string;
}

export interface SourceStatus {
  name: string;
  enabled: boolean;
  ready: boolean;
  requires_key: boolean;
  nfo_crawl: boolean;
}

export interface SettingsOut {
  enabled_sources: string[];
}

export interface SettingsPatch {
  enabled_sources?: string[];
}

/** 圖片一律走後端 proxy（帶正確 Referer 破防盜連；cover 裁右半正面） */
export function proxyImage(url: string | null | undefined, crop?: "cover"): string {
  if (!url) return "";
  const params = new URLSearchParams({ url });
  if (crop) params.set("crop", crop);
  return `/api/image?${params.toString()}`;
}

export const Api = {
  health: () => api.get<{ status: string }>("/health").then(r => r.data),
  sources: () => api.get<SourceStatus[]>("/sources").then(r => r.data),
  preview: (q: string, source = "all") =>
    api.get<PreviewItem[]>("/preview", { params: { q, source } }).then(r => r.data),
  metadata: (q: string, source = "all") =>
    api.get<MetadataResult>("/metadata", { params: { q, source } }).then(r => r.data),
  metadataById: (source: string, id: string) =>
    api.get<SourceDetail>(`/metadata/${source}/${id}`).then(r => r.data),

  getSettings: () => api.get<SettingsOut>("/settings").then(r => r.data),
  updateSettings: (patch: SettingsPatch) =>
    api.put<SettingsOut>("/settings", patch).then(r => r.data),
};
