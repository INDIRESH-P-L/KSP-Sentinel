// Compiles app/globals.css (Tailwind v4 + @theme tokens) into a static
// stylesheet the design-sync converter can copy verbatim — the converter
// only copies CSS files, it never runs a Tailwind build itself. Run this
// before every design-sync rebuild if globals.css (or any synced
// component's utility classes) changed. Requires postcss +
// @tailwindcss/postcss, which live in .ds-sync/node_modules (npm i there
// first — see .design-sync/NOTES.md).
import postcss from 'postcss';
import tailwind from '@tailwindcss/postcss';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';

const input = resolve('app/globals.css');
const output = resolve('.ds-sync/compiled-tailwind.css');

const css = readFileSync(input, 'utf8');
const result = await postcss([tailwind({ base: resolve('.') })]).process(css, {
  from: input,
  to: output,
});
mkdirSync(dirname(output), { recursive: true });
writeFileSync(output, result.css);
console.log('wrote', output, result.css.length, 'bytes');
