import { DecimalPipe, PercentPipe } from "@angular/common";
import { Component, OnDestroy, OnInit, computed, inject, signal } from "@angular/core";
import { OpsService, Overview } from "./ops.service";

interface Bar { label: string; value: number; pct: number; highlight: boolean; }

@Component({
  selector: "tl-overview",
  standalone: true,
  imports: [DecimalPipe, PercentPipe],
  template: `
    <section class="head">
      <div>
        <p class="eyebrow">Recommender health</p>
        <h1>Overview</h1>
      </div>
      <p class="refresh">
        @if (updated()) { Updated {{ updated() }} · refreshes every 10 s }
        <button class="link" (click)="load()">Refresh now</button>
      </p>
    </section>

    @if (error()) {
      <p class="alert bad" role="alert">{{ error() }}</p>
    }

    @if (data(); as d) {
      <section class="status-row">
        <span class="pill" [class.ok]="d.inference_status === 'ok'" [class.bad]="d.inference_status !== 'ok'">
          Inference {{ d.inference_status === 'ok' ? 'healthy' : d.inference_status }}
        </span>
        @if (d.model; as m) {
          <span class="pill">Champion {{ versionLabel(m.registry.version) }}</span>
          <span class="pill">Data: {{ m.data_source }}</span>
          <span class="pill">Serving from {{ m.serves_from }}</span>
        }
        @if ((d.service?.counts?.['fallback'] ?? 0) > 0) {
          <span class="pill warn">{{ d.service?.counts?.['fallback'] }} fallbacks served</span>
        }
      </section>

      @if (d.model; as m) {
        <section class="tiles" aria-label="Offline evaluation on the held-out test week">
          <div class="tile">
            <span class="k">MAP&#64;12</span>
            <span class="v">{{ m.metrics['test_map12'] | number: '1.4-4' }}</span>
            <span class="s">popularity baseline {{ m.metrics['test_baseline_pop_map12'] | number: '1.4-4' }}
              · {{ lift() | number: '1.1-1' }}× lift</span>
          </div>
          <div class="tile">
            <span class="k">Candidate recall</span>
            <span class="v">{{ m.metrics['test_candidate_recall'] | percent: '1.1-1' }}</span>
            <span class="s">ceiling for the ranker</span>
          </div>
          <div class="tile">
            <span class="k">Ranker AUC</span>
            <span class="v">{{ m.metrics['test_auc'] | number: '1.3-3' }}</span>
            <span class="s">on test-week candidates</span>
          </div>
          <div class="tile">
            <span class="k">Catalogue coverage</span>
            <span class="v">{{ m.metrics['test_coverage'] | percent: '1.0-0' }}</span>
            <span class="s">of {{ m.n_articles | number }} articles shown in some top 12</span>
          </div>
        </section>
      }

      @if (d.service; as s) {
        <section class="tiles" aria-label="Live service">
          <div class="tile">
            <span class="k">/recommend p95</span>
            <span class="v">{{ s.latency_ms['/recommend']?.p95 ?? 0 | number: '1.0-0' }}<small> ms</small></span>
            <span class="s">p50 {{ s.latency_ms['/recommend']?.p50 ?? 0 | number: '1.0-0' }} · p99 {{ s.latency_ms['/recommend']?.p99 ?? 0 | number: '1.0-0' }} ms</span>
          </div>
          <div class="tile">
            <span class="k">Requests / min</span>
            <span class="v">{{ s.requests_last_minute | number }}</span>
            <span class="s">uptime {{ s.uptime_seconds / 3600 | number: '1.1-1' }} h</span>
          </div>
          <div class="tile">
            <span class="k">Cache hit rate</span>
            <span class="v">{{ s.cache_hit_rate === null ? '—' : (s.cache_hit_rate | percent: '1.0-0') }}</span>
            <span class="s">Redis or in-process TTL cache</span>
          </div>
        </section>
      }

      <div class="split">
        @if (ablation().length) {
          <section class="panel">
            <h2>Ablation · MAP&#64;12 on test week</h2>
            <ul class="bars">
              @for (b of ablation(); track b.label) {
                <li [class.hl]="b.highlight">
                  <span class="bl">{{ b.label }}</span>
                  <span class="track"><span class="fill" [style.width.%]="b.pct"></span></span>
                  <span class="bv">{{ b.value | number: '1.4-4' }}</span>
                </li>
              }
            </ul>
          </section>
        }
        @if (features().length) {
          <section class="panel">
            <h2>Top ranker features · AUC drop when shuffled</h2>
            <ul class="bars">
              @for (b of features(); track b.label) {
                <li>
                  <span class="bl mono">{{ b.label }}</span>
                  <span class="track"><span class="fill alt" [style.width.%]="b.pct"></span></span>
                  <span class="bv">{{ b.value | number: '1.4-4' }}</span>
                </li>
              }
            </ul>
          </section>
        }
      </div>

      <section class="panel">
        <h2>Engagement by placement</h2>
        @if (d.engagement.length) {
          <div class="table-wrap">
            <table>
              <thead><tr><th>Placement</th><th>Impressions</th><th>Clicks</th><th>CTR</th><th>Add to bag</th><th>Add rate</th></tr></thead>
              <tbody>
                @for (e of d.engagement; track e.placement) {
                  <tr>
                    <td class="mono">{{ e.placement }}</td>
                    <td>{{ e.impressions | number }}</td>
                    <td>{{ e.clicks | number }}</td>
                    <td>{{ e.ctr === null ? '—' : (e.ctr | percent: '1.1-1') }}</td>
                    <td>{{ e.add_to_cart | number }}</td>
                    <td>{{ e.add_to_cart_rate === null ? '—' : (e.add_to_cart_rate | percent: '1.1-1') }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        } @else {
          <p class="empty">No storefront events yet. Browse the storefront and impressions and clicks will appear here.</p>
        }
      </section>
    } @else if (!error()) {
      <p class="empty">Loading…</p>
    }
  `,
})
export class OverviewComponent implements OnInit, OnDestroy {
  private ops = inject(OpsService);
  data = signal<Overview | null>(null);
  error = signal<string | null>(null);
  updated = signal<string>("");
  private timer?: ReturnType<typeof setInterval>;

  lift = computed(() => {
    const m = this.data()?.model?.metrics;
    return m && m["test_baseline_pop_map12"] ? m["test_map12"] / m["test_baseline_pop_map12"] : 0;
  });

  ablation = computed<Bar[]>(() => this.toBars(this.data()?.model?.ablation ?? {}, "full ranker"));
  features = computed<Bar[]>(() => this.toBars(this.data()?.model?.top_features ?? {}, ""));

  versionLabel(v: string | number | undefined): string {
    return v === undefined ? "—" : /^\d+$/.test(String(v)) ? `v${v}` : String(v);
  }

  ngOnInit(): void {
    this.load();
    this.timer = setInterval(() => this.load(), 10_000);
  }

  ngOnDestroy(): void {
    clearInterval(this.timer);
  }

  load(): void {
    this.ops.overview().subscribe({
      next: (d) => {
        this.data.set(d);
        this.error.set(null);
        this.updated.set(new Date().toLocaleTimeString());
      },
      error: (e) =>
        this.error.set(
          e.status === 403
            ? "The API rejected the ops token. Enter the OPS_TOKEN value in the top bar."
            : `Couldn't reach the API (${e.status || "network error"}).`,
        ),
    });
  }

  private toBars(obj: Record<string, number>, highlight: string): Bar[] {
    const entries = Object.entries(obj);
    const max = Math.max(...entries.map(([, v]) => v), 1e-9);
    return entries.map(([label, value]) => ({ label, value, pct: Math.max(0, (value / max) * 100), highlight: label === highlight }));
  }
}
