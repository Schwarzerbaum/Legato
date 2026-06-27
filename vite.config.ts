import path, { resolve } from 'path'
import { readFileSync } from 'fs'
import { defineConfig, type Plugin } from 'vite'
import { cloudflare } from '@cloudflare/vite-plugin'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

function openaiDevProxy(): Plugin {
  return {
    name: 'openai-dev-proxy',
    enforce: 'pre',
    configureServer(server) {
      let apiKey = ''
      try {
        const content = readFileSync(resolve(__dirname, '.dev.vars'), 'utf-8')
        const match = content.match(/^OPENAI_API_KEY=(.+)$/m)
        if (match) apiKey = match[1].trim()
      } catch {}

      server.middlewares.use('/api/ai', async (req, res, next) => {
        if (!apiKey) { next(); return }
        try {
          const targetUrl = `https://api.openai.com${req.url ?? '/'}`

          const chunks: Buffer[] = []
          await new Promise<void>((resolve) => {
            req.on('data', (chunk: Buffer) => chunks.push(chunk))
            req.on('end', () => resolve())
          })
          const body = Buffer.concat(chunks)

          const headers: Record<string, string> = {}
          for (const [key, value] of Object.entries(req.headers)) {
            if (!['host', 'connection', 'transfer-encoding', 'origin', 'referer'].includes(key) && typeof value === 'string') {
              headers[key] = value
            }
          }
          headers['authorization'] = `Bearer ${apiKey}`

          const response = await fetch(targetUrl, {
            method: req.method,
            headers,
            body: body.length > 0 ? body : undefined,
          })

          res.statusCode = response.status
          for (const [key, value] of response.headers.entries()) {
            if (!['content-encoding', 'transfer-encoding'].includes(key)) {
              res.setHeader(key, value)
            }
          }

          if (response.body) {
            const reader = response.body.getReader()
            const pump = async (): Promise<void> => {
              const { done, value } = await reader.read()
              if (done) { res.end(); return }
              res.write(Buffer.from(value))
              return pump()
            }
            await pump()
          } else {
            res.end()
          }
        } catch (err) {
          next(err)
        }
      })
    },
  }
}

export default defineConfig({
  plugins: [openaiDevProxy(), react(), tailwindcss(), cloudflare()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
