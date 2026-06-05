import React from 'react';
import { html } from 'htm/react';

export default function AlertModal({ payload, onDismiss }) {
  if (!payload) return null;
  // payload shape: { recipientUserId, title, body, deepLinkUri, requestForegroundDisplay }
  return html`
    <div className="ftm-alert-modal" role="dialog" aria-modal="true">
      <div className="ftm-alert-modal-content">
        <h2>${payload.title}</h2>
        <p>${payload.body}</p>
        <a href=${payload.deepLinkUri.replace('ftm://', '#/')}>Open task</a>
        <button onClick=${onDismiss}>Dismiss</button>
      </div>
    </div>
  `;
}

// Modal renders only when payload non-null (parent component controls visibility via state).
// AC: remains visible until explicitly dismissed (no auto-timeout). The button's onClick triggers onDismiss.
// The deep-link <a> rewrites ftm://instance/<id> to #/instance/<id> for hash-router navigation.
