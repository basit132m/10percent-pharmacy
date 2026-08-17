/**
 * Generates the Android launcher icons from design/pharmacy-logo.png.
 *
 *   npm install sharp
 *   node tools/generate-launcher-icons.mjs
 *
 * Run this again whenever the logo artwork changes.
 *
 * What it writes:
 *   mipmap-<density>/ic_launcher.png             legacy icon (API 24-25)
 *   mipmap-<density>/ic_launcher_round.png       legacy round icon
 *   mipmap-<density>/ic_launcher_foreground.png  adaptive foreground (API 26+)
 *
 * The adaptive foreground sits on a 108dp canvas of which only the middle 72dp
 * is ever shown, and only the middle 66dp is guaranteed. The logo is a circular
 * badge, so it is scaled to 68dp: it fills a circular mask almost exactly while
 * keeping the gold ring clear of any mask that crops tighter.
 */
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

import sharp from 'sharp';

const SOURCE = 'design/pharmacy-logo.png';
const RES_DIR = 'android/app/src/main/res';

/** Baseline pixel sizes at mdpi, scaled per density bucket. */
const DENSITIES = {
  mdpi: 1,
  hdpi: 1.5,
  xhdpi: 2,
  xxhdpi: 3,
  xxxhdpi: 4,
};

const LEGACY_DP = 48;
const ADAPTIVE_CANVAS_DP = 108;
/** Diameter the logo occupies inside the adaptive canvas. */
const ADAPTIVE_LOGO_DP = 68;
/** Legacy icons have no mask, so the logo can nearly fill them. */
const LEGACY_LOGO_FRACTION = 0.96;

async function renderCentred(logoSize, canvasSize) {
  const logo = await sharp(SOURCE)
    .resize(logoSize, logoSize, {
      fit: 'contain',
      background: { r: 0, g: 0, b: 0, alpha: 0 },
    })
    .toBuffer();

  const offset = Math.round((canvasSize - logoSize) / 2);
  return sharp({
    create: {
      width: canvasSize,
      height: canvasSize,
      channels: 4,
      background: { r: 0, g: 0, b: 0, alpha: 0 },
    },
  })
    .composite([{ input: logo, top: offset, left: offset }])
    .png({ compressionLevel: 9 })
    .toBuffer();
}

const written = [];

for (const [density, scale] of Object.entries(DENSITIES)) {
  const dir = path.join(RES_DIR, `mipmap-${density}`);
  await mkdir(dir, { recursive: true });

  // Legacy icon, used on API 24-25 and as the fallback everywhere else.
  const legacyCanvas = Math.round(LEGACY_DP * scale);
  const legacyLogo = Math.round(legacyCanvas * LEGACY_LOGO_FRACTION);
  const legacy = await renderCentred(legacyLogo, legacyCanvas);
  await writeFile(path.join(dir, 'ic_launcher.png'), legacy);
  // The artwork is already a circle, so the round variant is the same image.
  await writeFile(path.join(dir, 'ic_launcher_round.png'), legacy);

  // Adaptive foreground layer.
  const adaptiveCanvas = Math.round(ADAPTIVE_CANVAS_DP * scale);
  const adaptiveLogo = Math.round(ADAPTIVE_LOGO_DP * scale);
  const foreground = await renderCentred(adaptiveLogo, adaptiveCanvas);
  await writeFile(path.join(dir, 'ic_launcher_foreground.png'), foreground);

  written.push(
    `${density}: legacy ${legacyCanvas}px (${legacy.length} B), foreground ${adaptiveCanvas}px (${foreground.length} B)`,
  );
}

console.log(written.join('\n'));
