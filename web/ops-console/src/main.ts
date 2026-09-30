import { bootstrapApplication } from "@angular/platform-browser";
import { provideHttpClient, withInterceptors } from "@angular/common/http";
import { provideRouter, withHashLocation } from "@angular/router";
import { AppComponent } from "./app/app.component";
import { routes } from "./app/routes";
import { opsTokenInterceptor } from "./app/ops.service";

bootstrapApplication(AppComponent, {
  providers: [provideRouter(routes, withHashLocation()), provideHttpClient(withInterceptors([opsTokenInterceptor]))],
}).catch((err) => console.error(err));
