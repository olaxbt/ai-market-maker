import { defineConfig, loadEnv } from 'vite'
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'


function figmaAssetResolver() {
  return {
    name: 'figma-asset-resolver',
    resolveId(id) {
      if (id.startsWith('figma:asset/')) {
        const filename = id.replace('figma:asset/', '')
        return path.resolve(__dirname, 'src/assets', filename)
      }
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const flowApiBase = env.VITE_FLOW_API_BASE_URL || 'http://127.0.0.1:8001'

  const flowApiProxy = {
    '/api': {
      target: flowApiBase,
      changeOrigin: true,
      secure: false,
      /** Browser uses `/api/...`; Flow serves `...` at repo root (see `flow_stream_server`). */
      rewrite: (p: string) => p.replace(/^\/api/, ''),
    },
  }

  return {
    plugins: [
      figmaAssetResolver(),
      // The React and Tailwind plugins are both required for Make, even if
      // Tailwind is not being actively used – do not remove them
      react(),
      tailwindcss(),
    ],
    resolve: {
      alias: {
        // Alias @ to the src directory
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: { proxy: flowApiProxy },

    // Same proxy for `vite preview` so `/api/*` works locally (not only `vite dev`).
    preview: { proxy: flowApiProxy },

    // File types to support raw imports. Never add .css, .tsx, or .ts files to this.
    assetsInclude: ['**/*.svg', '**/*.csv'],
  }
})
