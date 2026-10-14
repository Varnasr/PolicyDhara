import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://policydhara.impactmojo.in',
  base: '/',
  trailingSlash: 'ignore',
  build: {
    format: 'directory'
  },
  integrations: [
    sitemap({
      // Exclude only the iframe widget pages — /embed/ itself is the
      // human-facing embed documentation and belongs in the sitemap.
      filter: (page) => !page.includes('/embed/feed') && !page.includes('/embed/stats'),
      changefreq: 'daily',
      priority: 0.7,
      serialize(item) {
        // Higher priority for hub pages
        if (/^https:\/\/[^/]+\/?$/.test(item.url)) {
          item.priority = 1.0;
          item.changefreq = 'hourly';
        } else if (/\/(sectors|states|search|digest|alerts)\/?$/.test(item.url)) {
          item.priority = 0.9;
          item.changefreq = 'daily';
        } else if (/\/policies\//.test(item.url)) {
          item.priority = 0.6;
          item.changefreq = 'monthly';
        }
        return item;
      }
    })
  ],
  vite: {
    build: {
      rollupOptions: {
        output: {
          assetFileNames: 'assets/[name].[hash][extname]'
        }
      }
    }
  }
});
