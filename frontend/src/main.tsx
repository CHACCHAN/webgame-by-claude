import { createRoot } from 'react-dom/client';
import '@fontsource/zen-kaku-gothic-new/400.css';
import '@fontsource/zen-kaku-gothic-new/700.css';
import '@fontsource/rajdhani/500.css';
import '@fontsource/rajdhani/700.css';
import '@fontsource/shippori-mincho/700.css';
import '@fontsource/shippori-mincho/800.css';
import './ui/styles.css';
import { App } from './App';

// StrictMode is intentionally not used: the 3D world is a heavyweight singleton.
createRoot(document.getElementById('root')!).render(<App />);
