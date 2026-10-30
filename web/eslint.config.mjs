import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import prettier from "eslint-config-prettier/flat";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Last, so Prettier alone decides formatting.
  prettier,
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts", "lib/api/schema.d.ts"]),
]);

export default eslintConfig;
