import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://varnasr.github.io',
  base: '/india-policy-tracker',
  build: {
    format: 'directory'
  },
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
