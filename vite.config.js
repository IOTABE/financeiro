import { defineConfig } from "vite";

export default defineConfig({
  build: {
    outDir: "src/static/vendor",
    emptyOutDir: true,
    lib: {
      entry: "src/static/js/material-entry.js",
      formats: ["es"],
      fileName: "material",
    },
  },
});
