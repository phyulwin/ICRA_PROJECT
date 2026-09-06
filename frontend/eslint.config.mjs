// frontend/eslint.config.mjs
import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTypeScript from 'eslint-config-next/typescript';

// Apply the supported Next.js 16 flat configuration to TypeScript application code.
const eslintConfig = defineConfig([
    ...nextVitals,
    ...nextTypeScript,
    globalIgnores(['.next/**', 'out/**', 'build/**', 'next-env.d.ts']),
]);

export default eslintConfig;

