import type { Article, Customer, CustomerDetail, EventType, Feed, Page } from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} on ${path}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  feed: (body: { customer_id: string | null; session_article_ids: number[]; age: number | null }) =>
    request<Feed>("/api/feed/", { method: "POST", body: JSON.stringify(body) }),
  demoCustomers: () => request<Customer[]>("/api/customers/demo/?n=12"),
  customer: (id: string) => request<CustomerDetail>(`/api/customers/${encodeURIComponent(id)}/`),
  article: (id: number) => request<Article>(`/api/articles/${id}/`),
  similar: (id: number) => request<Article[]>(`/api/articles/${id}/similar/`),
  completeTheLook: (id: number) => request<Article[]>(`/api/articles/${id}/complete-the-look/`),
  facets: () => request<Record<string, string[]>>("/api/articles/facets/"),
  search: (params: URLSearchParams) => request<Page<Article>>(`/api/articles/?${params.toString()}`),
  checkout: (body: { session_id: string; customer_id: string | null; article_ids: number[] }) =>
    request<{ order_items: number; total: string }>("/api/checkout/", { method: "POST", body: JSON.stringify(body) }),
};

// ---- Event logging: batched, fire-and-forget. Impressions and clicks train the next model.
interface PendingEvent {
  session_id: string;
  customer_id: string | null;
  article_id: number;
  event_type: EventType;
  placement: string;
  model_version: string;
}

let queue: PendingEvent[] = [];
let timer: number | undefined;

function flush() {
  if (!queue.length) return;
  const batch = queue;
  queue = [];
  fetch(`${BASE}/api/events/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(batch),
    keepalive: true,
  }).catch(() => {
    /* analytics must never break the page */
  });
}

export function track(e: PendingEvent) {
  queue.push(e);
  window.clearTimeout(timer);
  timer = window.setTimeout(flush, 1500);
}

window.addEventListener("pagehide", flush);
