// Docker development adapter: keep source config intact and observe watcher coverage.
import base from './vite.config.ts'
import { mergeConfig } from 'vite'
import { resolve } from 'node:path'

export default mergeConfig(base, {
  server: {
    watch: { usePolling: true, interval: 250 },
    proxy: {
      '/api': { changeOrigin: false },
      '/manual': { target: process.env.BAGO_API_PROXY_TARGET, changeOrigin: false },
      '/ws': { target: process.env.BAGO_API_PROXY_TARGET, changeOrigin: false, ws: true },
    },
  },
  plugins: [{
    name: 'bago-docker-watch-coverage',
    configureServer(server) {
      const directories = [resolve(server.config.root, 'src'), server.config.publicDir].filter(Boolean)
      let closed = false
      let attempts = 0
      let ready = false
      const covered = () => directories.every(path => Object.hasOwn(server.watcher.getWatched(), path))
      const arm = () => {
        if (closed) return
        server.watcher.add(directories)
        ready = covered()
        if (ready) console.log('BAGO_DEV_WATCH_READY ' + JSON.stringify({ directories }))
      }
      // An initial ready event without src/public coverage is insufficient on Docker Desktop.
      server.watcher.once('ready', arm)
      const timer = setInterval(() => {
        if (closed || ready) return
        if (++attempts <= 40) arm()
      }, 250)
      timer.unref()
      server.middlewares.use('/__bago_dev_health', (_request, response) => {
        ready = !closed && covered()
        response.statusCode = ready ? 200 : 503
        response.setHeader('Content-Type', 'application/json')
        response.end(JSON.stringify({ ready, watcherCoverage: ready }))
      })
      server.httpServer?.once('close', () => { closed = true; ready = false; clearInterval(timer) })
    },
  }],
})
