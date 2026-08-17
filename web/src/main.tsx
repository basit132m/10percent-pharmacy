import { StrictMode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

import { initFirebase, loadFirebaseConfig } from './lib/firebase';
import './styles.css';

const container = document.getElementById('root');
if (!container) {
  throw new Error('Missing #root element');
}
const root = createRoot(container);

/**
 * Firebase is configured from the server before the app is imported, because
 * modules that talk to Firestore read `auth`/`db` as soon as they load.
 */
async function bootstrap(root: Root): Promise<void> {
  try {
    initFirebase(await loadFirebaseConfig());
  } catch (error) {
    root.render(
      <div className="splash">
        {error instanceof Error ? error.message : 'Could not start the dashboard.'}
      </div>,
    );
    return;
  }

  const [{ App }, { AuthProvider }] = await Promise.all([
    import('./App'),
    import('./auth/AuthContext'),
  ]);

  root.render(
    <StrictMode>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </StrictMode>,
  );
}

root.render(<div className="splash">Loading…</div>);
void bootstrap(root);
