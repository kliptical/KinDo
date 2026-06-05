import React, { useEffect, useState } from 'react';
import { html } from 'htm/react';
import { resolveDeepLink } from '../../routing/deepLink.js';
import { childCompletes } from '../../flows/childCompletes.js';

export default function TaskDetailChild({ ftm, identity, instanceId }) {
  const [instance, setInstance] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const inst = await resolveDeepLink('ftm://instance/' + instanceId, { stateAdapter: ftm.stateAdapter });
    setInstance(inst); setLoading(false);
  }

  useEffect(() => { refresh(); }, [instanceId]);

  async function markComplete() {
    if (!instance || instance['ftm:completionState']['ftm:status'] === 'completed') {
      return;
    }
    setBusy(true);
    await childCompletes({ stateAdapter: ftm.stateAdapter, orchestrationAdapter: ftm.orchestrationAdapter, instanceId: instance['@id'], childId: identity.userId, currentTime: new Date().toISOString() });
    await refresh();
    setBusy(false);
  }

  if (loading) return html`<p>Loading...</p>`;
  if (!instance) return html`<p>Task not found.</p>`;

  const isCompleted = instance['ftm:completionState']['ftm:status'] === 'completed';

  return html`
    <div className="task-detail-child">
      <h2>${instance['@id'].split(':').pop()}</h2>
      <p><strong>Due:</strong> ${instance['ftm:dueAt']['@value']}</p>
      <p><strong>Status:</strong> ${isCompleted ? 'Completed' : 'Pending'}</p>
      ${isCompleted ? null : html`<button onClick=${markComplete} disabled=${busy}>${busy ? 'Saving...' : 'Mark Complete'}</button>`}
      <p><a href="#/child/tasks">Back to my tasks</a></p>
    </div>
  `;
}
