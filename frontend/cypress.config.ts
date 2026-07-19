import { defineConfig } from "cypress";

export default defineConfig({
  allowCypressEnv: false,
  video: false,
  component: {
    devServer: {
      framework: "react",
      bundler: "vite",
    },
    specPattern: "cypress/component/**/*.cy.tsx",
    supportFile: "cypress/support/component.ts",
    viewportWidth: 1100,
    viewportHeight: 760,
  },
});
