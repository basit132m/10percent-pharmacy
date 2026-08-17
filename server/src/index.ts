/**
 * 10% Discount Pharmacy — self-hosted backend.
 *
 * One Node process does everything the Cloud Functions did, plus serving the
 * admin dashboard:
 *   - POST/PATCH /api/stores...     store owner accounts (Admin SDK)
 *   - POST /api/offers/refresh-status
 *   - GET  /api/config              Firebase web config for the dashboard
 *   - a Firestore listener that pushes FCM the moment an offer is published
 *   - a daily pass that flips offer statuses at 00:05 Asia/Karachi
 *
 * It listens on loopback; the reverse proxy in front of it terminates TLS.
 */
import path from 'node:path';

import express from 'express';

import { loadConfig, loadEnvFile } from './config';
import { initFirebase } from './firebase';
import { scheduleDailyStatusPass, offersRouter, refreshOfferStatuses, watchOfferEdits } from './offers';
import { storesRouter } from './stores';
import { watchForNewOffers } from './notifications';
import { ApiError } from './validation';

loadEnvFile(path.join(__dirname, '..', '.env'));

const config = loadConfig();
initFirebase(config);

const app = express();
app.disable('x-powered-by');
app.use(express.json({ limit: '64kb' }));

/**
 * The dashboard fetches its Firebase config from here instead of baking it in
 * at build time, so the same build works against any project. These values are
 * public by design — they identify the project, they do not grant access.
 */
app.get('/api/config', (_req, res) => {
  res.json(config.webConfig);
});

app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', time: new Date().toISOString() });
});

app.use('/api/stores', storesRouter);
app.use('/api/offers', offersRouter);

// Built dashboard, with SPA fallback so deep links resolve to index.html.
app.use(express.static(config.staticDir, { index: 'index.html' }));
app.get(/^(?!\/api\/).*/, (_req, res) => {
  res.sendFile(path.join(config.staticDir, 'index.html'));
});

app.use(
  (
    error: unknown,
    _req: express.Request,
    res: express.Response,
    _next: express.NextFunction,
  ) => {
    if (error instanceof ApiError) {
      res.status(error.status).json({ error: error.message });
      return;
    }
    console.error('[api] unhandled error:', error);
    res.status(500).json({ error: 'Something went wrong. Try again.' });
  },
);

const server = app.listen(config.port, config.host, () => {
  console.log(
    `[server] listening on http://${config.host}:${config.port} (project ${config.projectId})`,
  );
});

const stopOfferWatch = watchForNewOffers();
const stopEditWatch = watchOfferEdits();
const stopDailyPass = scheduleDailyStatusPass();

// Catch up on anything that expired while the service was down.
refreshOfferStatuses().catch((error) =>
  console.error('[offers] startup status pass failed:', error),
);

function shutdown(signal: string) {
  console.log(`[server] ${signal} received, shutting down`);
  stopOfferWatch();
  stopEditWatch();
  stopDailyPass();
  server.close(() => process.exit(0));
  // Do not hang forever if a connection refuses to close.
  setTimeout(() => process.exit(0), 5000).unref();
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
