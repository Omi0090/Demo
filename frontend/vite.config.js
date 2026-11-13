import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins:[react()],
  build:{rollupOptions:{output:{manualChunks(id){
    if (/node_modules\/(react|react-dom|react-is|scheduler)\//.test(id)) return 'react-vendor';
    if (id.includes('node_modules/lucide-react/')) return 'icons';
    if (id.includes('node_modules/')) return 'charts-vendor';
  }}}},
  server:{host:'0.0.0.0',allowedHosts:['.e2b.app','localhost'],proxy:{'/api':{target:'http://127.0.0.1:8000',changeOrigin:true}}}
});
