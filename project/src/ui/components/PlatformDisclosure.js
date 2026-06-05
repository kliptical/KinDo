import React, { useState, useEffect } from 'react';
import { html } from 'htm/react';

export const PLATFORM_DISCLOSURE_TEXT = 'Background reminders require notification permissions. Reliability when the app is closed depends on your device and browser.';

const STORAGE_KEY = 'ftm.platformDisclosureShown';

export function hasShownPlatformDisclosure() {
  if (typeof localStorage === 'undefined') return false;
  return localStorage.getItem(STORAGE_KEY) === 'true';
}

export function markPlatformDisclosureShown() {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(STORAGE_KEY, 'true');
}

export default function PlatformDisclosure({ onAcknowledge }) {
  const [shown, setShown] = useState(() => hasShownPlatformDisclosure());
  if (shown) return null;
  return html`
    <div className="ftm-platform-disclosure" role="alertdialog">
      <p>${PLATFORM_DISCLOSURE_TEXT}</p>
      <button onClick=${() => { markPlatformDisclosureShown(); setShown(true); onAcknowledge && onAcknowledge(); }}>OK</button>
    </div>
  `;
}

// AC §5.2: PLATFORM_DISCLOSURE_TEXT is a named constant (not inlined), exact string from SPEC §7.2.
// First permission request shows the disclosure; subsequent requests in same session do not re-display (state guards).
