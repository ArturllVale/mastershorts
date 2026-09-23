import js from "@eslint/js";
import globals from "globals";

export default [
  {
    ignores: [
      "**/node_modules/**",
      "**/dist/**",
      "**/build/**",
      "backend/**",
      "frontend/public/**",
      "render-service/**",
      "remotion/**"
    ]
  },
  js.configs.recommended,
  {
    files: ["scripts/**/*.{js,cjs,mjs}"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "commonjs",
      globals: {
        ...globals.node
      }
    }
  },
  {
    files: ["frontend/**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: {
        ...globals.browser
      },
      parserOptions: {
        ecmaFeatures: { jsx: true }
      }
    },
    rules: {
      "no-unused-vars": ["error", {
        varsIgnorePattern: "^[A-Z_]",
        argsIgnorePattern: "^_",
        caughtErrors: "none"
      }]
    }
  }
];
