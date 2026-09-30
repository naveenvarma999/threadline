import { Component, inject, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { RouterLink, RouterLinkActive, RouterOutlet } from "@angular/router";
import { OpsService } from "./ops.service";

@Component({
  selector: "tl-root",
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, FormsModule],
  template: `
    <header class="bar">
      <div class="brand">
        <span class="mark" aria-hidden="true"></span>
        <span>Threadline <b>Ops</b></span>
      </div>
      <nav>
        <a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: true }">Overview</a>
        <a routerLink="/models" routerLinkActive="active">Models</a>
      </nav>
      <form class="token" (ngSubmit)="save()">
        <label for="token">Ops token</label>
        <input id="token" name="token" type="password" [(ngModel)]="draft" autocomplete="off" placeholder="X-Ops-Token" />
        <button type="submit">{{ saved() ? "Saved" : "Use" }}</button>
      </form>
    </header>
    <main><router-outlet /></main>
  `,
})
export class AppComponent {
  private ops = inject(OpsService);
  draft = this.ops.token();
  saved = signal(false);

  save(): void {
    this.ops.setToken(this.draft.trim());
    this.saved.set(true);
    setTimeout(() => this.saved.set(false), 1500);
  }
}
