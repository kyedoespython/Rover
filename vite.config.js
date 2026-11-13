import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
    root: resolve(__dirname, "frontend"),
    build: {
        emptyOutDir: true,
        outDir: resolve(__dirname, "main/static/react"),
        rollupOptions: {
            input: resolve(__dirname, "frontend/src/main.jsx"),
            output: {
                assetFileNames: "assets/[name][extname]",
                chunkFileNames: "chunks/[name].js",
                entryFileNames: "app.js",
            },
        },
    },
});
