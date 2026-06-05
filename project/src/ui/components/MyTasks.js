import React, { useEffect, useState } from 'react';
import { html } from 'htm/react';
import { taskListComputer } from '../../modules/taskListComputer.js';

export default function MyTasks({ ftm, identity }) {
  const [pending, setPending] = useState([]);
  const [loaded, setLoaded] = useState(false);

  async function refresh() {
    const instances = await ftm.stateAdapter.listTaskInstances({ assignedTo: identity.userId });
    setPending(taskListComputer(instances, { status: 'pending' }));
    setLoaded(true);
  }

  useEffect(() => { refresh(); }, [identity.userId]);
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const handler = () => refresh();
    window.addEventListener('ftm:taskCompleted', handler);
    return () => window.removeEventListener('ftm:taskCompleted', handler);
  }, []);

  if (!loaded) return html`<p>Loading...</p>`;

  return html`
    <div className="my-tasks">
      <h2>My Tasks</h2>
      ${pending.length === 0 ? html`<p>No pending tasks. Nice work!</p>` : html`<ul>${pending.map(inst => html`<li key=${inst['@id']}><a href="#/child/instance/${inst['@id'].split(':').pop()}">${inst['@id'].split(':').pop()}</a> — due ${inst['ftm:dueAt']['@value']}</li>`)}</ul>`}
    </div>
  `;
}
