// Renders the specialty illustrations (src/components/MedicalArt.tsx) to standalone SVG files,
// so the Keycloak login theme shows the same artwork as the app.
//
//   npx vite-node scripts/render-art.tsx [outdir]
//   (default outdir: ../infra/keycloak/themes/aegle/login/resources/img)
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { MedicalArt } from "../src/components/MedicalArt";
import { SPECIALTIES } from "../src/specialties";

const out = path.resolve(process.argv[2] ?? path.join(import.meta.dirname, "../../infra/keycloak/themes/aegle/login/resources/img"));
mkdirSync(out, { recursive: true });
// The app bundles the animation CSS; a standalone SVG has to carry it inline.
const css = readFileSync(path.join(import.meta.dirname, "../src/components/MedicalArt.css"), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
for (const s of SPECIALTIES) {
  const svg = renderToStaticMarkup(<MedicalArt specialty={s.id} motion="live" />)
    .replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ')
    .replace(/(<svg[^>]*>)/, `$1<style>${css}</style>`);
  writeFileSync(path.join(out, `art-${s.slug}.svg`), svg);
}
console.log(`wrote ${SPECIALTIES.length} illustrations to ${out}`);
