/**
 * Runtime configuration, read from environment variables (see .env.example).
 * Everything is validated at startup so the service fails loudly on a bad
 * config rather than halfway through serving a request.
 */
import fs from 'node:fs';
import path from 'node:path';

function required(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(
      `Missing required environment variable ${name}. See server/.env.example.`,
    );
  }
  return value;
}

function optional(name: string, fallback: string): string {
  const value = process.env[name]?.trim();
  return value && value.length > 0 ? value : fallback;
}

/** Loads a KEY=value file into process.env without overwriting real env vars. */
export function loadEnvFile(filePath: string): void {
  if (!fs.existsSync(filePath)) {
    return;
  }
  for (const rawLine of fs.readFileSync(filePath, 'utf8').split('\n')) {
    const line = rawLine.trim();
    if (line.length === 0 || line.startsWith('#')) {
      continue;
    }
    const separator = line.indexOf('=');
    if (separator === -1) {
      continue;
    }
    const key = line.slice(0, separator).trim();
    let value = line.slice(separator + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (process.env[key] === undefined) {
      process.env[key] = value;
    }
  }
}

/** True when pointed at the local Firebase emulators instead of the real project. */
export function usingEmulators(): boolean {
  return Boolean(process.env.FIRESTORE_EMULATOR_HOST);
}

export interface AppConfig {
  port: number;
  host: string;
  projectId: string;
  /** Null only when running against the emulators, which need no credentials. */
  serviceAccountPath: string | null;
  /** Firebase web SDK config, handed to the dashboard at runtime. */
  webConfig: {
    apiKey: string;
    authDomain: string;
    projectId: string;
    storageBucket: string;
    messagingSenderId: string;
    appId: string;
  };
  /** Absolute path to the built dashboard (web/dist). */
  staticDir: string;
}

export function loadConfig(): AppConfig {
  const projectId = required('FIREBASE_PROJECT_ID');

  let serviceAccountPath: string | null = null;
  if (usingEmulators()) {
    console.log('[config] emulator mode: skipping the service account key');
  } else {
    serviceAccountPath = path.resolve(required('GOOGLE_APPLICATION_CREDENTIALS'));
    if (!fs.existsSync(serviceAccountPath)) {
      throw new Error(`Service account key not found at ${serviceAccountPath}`);
    }
  }

  return {
    port: Number(optional('PORT', '8080')),
    // Bind to loopback by default: the reverse proxy is what faces the internet.
    host: optional('HOST', '127.0.0.1'),
    projectId,
    serviceAccountPath,
    webConfig: {
      apiKey: required('FIREBASE_API_KEY'),
      authDomain: optional('FIREBASE_AUTH_DOMAIN', `${projectId}.firebaseapp.com`),
      projectId,
      storageBucket: optional('FIREBASE_STORAGE_BUCKET', `${projectId}.appspot.com`),
      messagingSenderId: required('FIREBASE_MESSAGING_SENDER_ID'),
      appId: required('FIREBASE_APP_ID'),
    },
    staticDir: path.resolve(
      optional('STATIC_DIR', path.join(__dirname, '..', '..', 'web', 'dist')),
    ),
  };
}
