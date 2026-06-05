import React, { useEffect, useState } from 'react';
import { html } from 'htm/react';
import { parentDashboard } from '../../flows/parentDashboard.js';
import { parentCompletesOnBehalf } from '../../flows/parentCompletesOnBehalf.js';

export default function ParentDashboard({ ftm, identity }) {
  const [pending, setPending] = useState([]);
  const [completed, setCompleted] = useState([]);
  const [error, setError] = useState(null);

  async function refresh() {
    try {
      const result = await parentDashboard({ stateAdapter: ftm.stateAdapter });
      setPending(result.pending); setCompleted(result.completed); setError(null);
    } catch (e) { setError(e.message); }
  }

  useEffect(() => { refresh(); }, []);

  // Subscribe to ftm:taskCompleted to refresh reactively
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const handler = () => refresh();
    window.addEventListener('ftm:taskCompleted', handler);
    return () => window.removeEventListener('ftm:taskCompleted', handler);
  }, []);

  async function overrideComplete(instanceId) {
    await parentCompletesOnBehalf({ stateAdapter: ftm.stateAdapter, orchestrationAdapter: ftm.orchestrationAdapter, instanceId, parentId: identity.userId, currentTime: new Date().toISOString() });
    refresh();
  }

  function renderInstance(inst) {
    const byRole = inst['ftm:completionState']['ftm:completedByRole'];
    return html`
      <li key=${inst['@id']}>
        <a href="#/parent/instance/${inst['@id'].split(':').pop()}">${inst['@id'].split(':').pop()}</a>
        \u2014 due ${inst['ftm:dueAt']['@value']}
        ${byRole === 'parent' ? html`<span className="badge">Parent Override</span>` : null}
        ${inst['ftm:completionState']['ftm:status'] === 'pending' ? html`<button onClick=${() => overrideComplete(inst['@id'])}>Mark Complete (Override)</button>` : null}
      </li>
    `;
  }

  return html`
    <div className="parent-dashboard">
      <h2>Dashboard</h2>
      ${error ? html`<p className="error">${error}</p>` : null}
      <section><h3>Pending (${pending.length})</h3><ul>${pending.map(renderInstance)}</ul></section>
      <section><h3>Completed (${completed.length})</h3><ul>${completed.map(renderInstance)}</ul></section>
      <p><a href="#/parent/create">+ Create Task</a></p>
    </div>
  `;
}
