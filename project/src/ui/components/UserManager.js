import React, { useEffect, useState } from 'react';
import { html } from 'htm/react';
import { createUser } from '../../entities/user.js';

// UserManager — parent-only view to create family members and copy
// their @id for use in TaskCreator. Backed by the existing Phase 3
// StateAdapter.saveUser / listUsers methods.
export default function UserManager({ ftm }) {
  const [users, setUsers] = useState([]);
  const [role, setRole] = useState('child');
  const [displayName, setDisplayName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(null);

  async function refresh() {
    const all = await ftm.stateAdapter.listUsers();
    setUsers(all);
  }

  useEffect(() => { refresh(); }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!displayName.trim()) { setError('Display name required'); return; }
    setSubmitting(true); setError(null);
    try {
      const user = createUser({ role, displayName: displayName.trim() });
      await ftm.stateAdapter.saveUser(user);
      setDisplayName('');
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function copyId(id) {
    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(id);
        setCopied(id);
        setTimeout(() => setCopied(prev => prev === id ? null : prev), 1500);
      }
    } catch {
      // ignore — copy is best-effort
    }
  }

  return html`
    <div className="user-manager">
      <h2>Family Members</h2>
      <form onSubmit=${handleSubmit}>
        <h3>Add a member</h3>
        ${error ? html`<p className="error">${error}</p>` : null}
        <label>Role
          <select value=${role} onChange=${e => setRole(e.target.value)}>
            <option value="child">Child</option>
            <option value="parent">Parent</option>
          </select>
        </label>
        <label>Display name
          <input value=${displayName} onChange=${e => setDisplayName(e.target.value)} placeholder="e.g. Alex" required />
        </label>
        <button type="submit" disabled=${submitting}>${submitting ? 'Adding...' : 'Add member'}</button>
      </form>
      <h3>Existing (${users.length})</h3>
      ${users.length === 0
        ? html`<p>No family members yet. Add one above.</p>`
        : html`<ul className="user-list">${users.map(u => html`
          <li key=${u['@id']}>
            <span className="user-name">${u['ftm:displayName']}</span>
            <span className="badge">${u['ftm:role']}</span>
            <code className="user-id">${u['@id']}</code>
            <button type="button" onClick=${() => copyId(u['@id'])}>${copied === u['@id'] ? 'Copied!' : 'Copy ID'}</button>
          </li>
        `)}</ul>`
      }
      <p><a href="#/parent/dashboard">← Back to dashboard</a></p>
    </div>
  `;
}
