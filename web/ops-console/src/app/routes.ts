import { Routes } from "@angular/router";
import { OverviewComponent } from "./overview.component";
import { ModelsComponent } from "./models.component";

export const routes: Routes = [
  { path: "", component: OverviewComponent, title: "Overview · Threadline Ops" },
  { path: "models", component: ModelsComponent, title: "Models · Threadline Ops" },
  { path: "**", redirectTo: "" },
];
