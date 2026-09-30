import { HttpClient, HttpInterceptorFn } from "@angular/common/http";
import { Injectable, inject, signal } from "@angular/core";
import { Observable } from "rxjs";

export interface LatencyStats { n: number; p50: number; p95: number; p99: number; }

export interface Overview {
  inference_status: string;
  engagement: { placement: string; impressions: number; clicks: number; add_to_cart: number; ctr: number | null; add_to_cart_rate: number | null }[];
  events_24h: Record<string, number>;
  model?: {
    registry: { model_uri?: string; version?: string | number; alias?: string; load_seconds?: number };
    data_source: string;
    created_at: string;
    serves_from: string;
    metrics: Record<string, number>;
    ablation: Record<string, number>;
    top_features: Record<string, number>;
    n_articles: number;
    n_customers: number;
  };
  service?: {
    uptime_seconds: number;
    requests_last_minute: number;
    latency_ms: Partial<Record<string, LatencyStats>>;
    cache_hit_rate: number | null;
    counts: Record<string, number>;
  };
}

export interface ModelVersion {
  version: string;
  aliases: string[];
  created: number;
  run_id: string;
  data_source: string | null;
  metrics: Record<string, number>;
}

const TOKEN_KEY = "tl.ops.token";

/** Adds the ops token to every /api/ops request. */
export const opsTokenInterceptor: HttpInterceptorFn = (req, next) => {
  const token = sessionStorage.getItem(TOKEN_KEY);
  return next(token && req.url.includes("/api/ops/") ? req.clone({ setHeaders: { "X-Ops-Token": token } }) : req);
};

@Injectable({ providedIn: "root" })
export class OpsService {
  private http = inject(HttpClient);
  readonly token = signal<string>(sessionStorage.getItem(TOKEN_KEY) ?? "");

  setToken(t: string): void {
    sessionStorage.setItem(TOKEN_KEY, t);
    this.token.set(t);
  }

  overview(): Observable<Overview> {
    return this.http.get<Overview>("/api/ops/overview/");
  }

  models(): Observable<{ registry: string; versions: ModelVersion[] }> {
    return this.http.get<{ registry: string; versions: ModelVersion[] }>("/api/ops/models/");
  }

  promote(version: string): Observable<{ champion: string; inference_reload: Record<string, unknown> }> {
    return this.http.post<{ champion: string; inference_reload: Record<string, unknown> }>(`/api/ops/models/${version}/promote/`, {});
  }
}
