import { createRoot } from 'react-dom/client';
import '@fontsource/zen-kaku-gothic-new/400.css';
import '@fontsource/zen-kaku-gothic-new/500.css';
import '@fontsource/zen-kaku-gothic-new/700.css';
import '@fontsource-variable/saira/wdth.css';
import '@fontsource/shippori-mincho/700.css';
import '@fontsource/shippori-mincho/800.css';
import './ui/theme/tokens.css';
import './ui/theme/base.css';
import './ui/theme/screens.css';
import './ui/theme/picker.css';
import './ui/theme/online.css';
import './ui/theme/hud.css';
import { App } from './App';
import { initAccount } from './store/account';

// A deploy replaces the hashed files: a game opened before it then asks for a chunk (a model loader, the audio) that
// is gone. Load the new build instead of failing; not twice within a minute (a second failure is something else).
window.addEventListener('vite:preloadError', (e) => {
  try {
    if (Date.now() - Number(sessionStorage.getItem('touge-reloaded') ?? 0) < 60_000) return;
    sessionStorage.setItem('touge-reloaded', String(Date.now()));
  } catch {
    return;
  }
  e.preventDefault();
  location.reload();
});

// who plays (a member logged in through Authentik, or a guest): asked while the game loads
void initAccount();

// StrictMode is intentionally not used: the 3D world is a heavyweight singleton.
createRoot(document.getElementById('root')!).render(<App />);
