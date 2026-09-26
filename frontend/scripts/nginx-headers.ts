// Prints security-headers.ts as nginx add_header directives, for the production image.
// Usage: VITE_KEYCLOAK_URL=... node scripts/nginx-headers.ts > security-headers.conf
import { keycloakOrigin, securityHeaders } from "../security-headers.ts";

const headers = securityHeaders(keycloakOrigin(process.env.VITE_KEYCLOAK_URL), true);
for (const [name, value] of Object.entries(headers)) {
  if (value.includes('"')) throw new Error(`Header ${name} cannot contain a double quote`);
  console.log(`add_header ${name} "${value}" always;`);
}
