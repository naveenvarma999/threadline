import { DatePipe, DecimalPipe } from "@angular/common";
import { Component, OnInit, inject, signal } from "@angular/core";
import { ModelVersion, OpsService } from "./ops.service";

@Component({
  selector: "tl-models",
  standalone: true,
  imports: [DatePipe, DecimalPipe],
  template: `
    <section class="head">
      <div>
        <p class="eyebrow">MLflow model registry</p>
        <h1>Models</h1>
      </div>
      <p class="refresh">Registered model: <span class="mono">{{ registry() || '—' }}</span></p>
    </section>

    <p class="lede">
      Training registers each new version as <b>challenger</b>. The pipeline promotes it automatically only if it beats
      the champion's MAP&#64;12 by 1%. You can also promote a version by hand; the inference service reloads it straight away.
    </p>

    @if (message()) {
      <p class="alert" [class.bad]="failed()" role="status">{{ message() }}</p>
    }

    @if (versions().length) {
      <div class="table-wrap panel">
        <table>
          <thead>
            <tr>
              <th>Version</th><th>Aliases</th><th>Registered</th><th>Data</th>
              <th>MAP&#64;12</th><th>vs popularity</th><th>Candidate recall</th><th>AUC</th><th></th>
            </tr>
          </thead>
          <tbody>
            @for (v of versions(); track v.version) {
              <tr [class.champ]="v.aliases.includes('champion')">
                <td class="mono">v{{ v.version }}</td>
                <td>
                  @for (a of v.aliases; track a) { <span class="pill" [class.ok]="a === 'champion'">{{ a }}</span> }
                </td>
                <td>{{ v.created | date: 'd MMM y, HH:mm' }}</td>
                <td>{{ v.data_source ?? '—' }}</td>
                <td class="num">{{ v.metrics['test_map12'] | number: '1.4-4' }}</td>
                <td class="num">{{ v.metrics['test_baseline_pop_map12'] | number: '1.4-4' }}</td>
                <td class="num">{{ v.metrics['test_candidate_recall'] | number: '1.3-3' }}</td>
                <td class="num">{{ v.metrics['test_auc'] | number: '1.3-3' }}</td>
                <td>
                  @if (!v.aliases.includes('champion')) {
                    @if (confirming() === v.version) {
                      <span class="confirm">
                        Serve v{{ v.version }} to all shoppers?
                        <button class="danger" (click)="promote(v.version)" [disabled]="busy()">Promote</button>
                        <button class="link" (click)="confirming.set(null)">Cancel</button>
                      </span>
                    } @else {
                      <button (click)="confirming.set(v.version)">Make champion</button>
                    }
                  } @else {
                    <span class="muted">Serving</span>
                  }
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    } @else {
      <p class="empty">{{ loading() ? 'Loading…' : 'No registered versions. Run the training pipeline, or set MLFLOW_TRACKING_URI on the API.' }}</p>
    }
  `,
})
export class ModelsComponent implements OnInit {
  private ops = inject(OpsService);
  versions = signal<ModelVersion[]>([]);
  registry = signal("");
  loading = signal(true);
  busy = signal(false);
  confirming = signal<string | null>(null);
  message = signal("");
  failed = signal(false);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.ops.models().subscribe({
      next: (r) => {
        this.versions.set(r.versions);
        this.registry.set(r.registry);
        this.loading.set(false);
      },
      error: (e) => {
        this.loading.set(false);
        this.failed.set(true);
        this.message.set(e.status === 403 ? "Enter the ops token in the top bar." : "Couldn't load the registry.");
      },
    });
  }

  promote(version: string): void {
    this.busy.set(true);
    this.ops.promote(version).subscribe({
      next: (r) => {
        const err = r.inference_reload["error"];
        this.failed.set(Boolean(err));
        this.message.set(err ? `v${version} is champion, but the inference reload failed: ${err}` : `v${version} is now serving.`);
        this.busy.set(false);
        this.confirming.set(null);
        this.load();
      },
      error: () => {
        this.failed.set(true);
        this.message.set(`Promotion of v${version} failed. Nothing changed.`);
        this.busy.set(false);
      },
    });
  }
}
