import { defineConfig } from 'vite';

export default defineConfig({
  // 请确保此处的 base 路径与您的 GitHub 仓库名称完全一致
  base: '/OpenRoyale/',
  build: {
    outDir: 'dist',
  }
});
