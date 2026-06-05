import React, { useEffect, useMemo, useState } from 'react';
import { html } from 'htm/react';
import { parentDashboard } from '../../flows/parentDashboard.js';
import { parentCompletesOnBehalf } from '../../flows/parentCompletesOnBehalf.js';

export default function ParentDashboard({ ftm, identity }) {
  const [pending, setPending] = useState([]);
  const [completed, setCompleted] = useState([]);
  const [users, setUsers] = useState([]);
  const [defs, setDefs] = useState([]);
  const [selectedChildId, setSelectedChildId] = useState('');
  const [error, setError] = useState(null);

  async function refresh() {
    try {
      const [dashResult, allUsers, allDefs] = await Promise.all([
        parentDashboard({ stateAdapter: ftm.stateAdapter, childId: selectedChildId || undefined }),
        ftm.stateAdapter.listUsers(),
        ftm.stateAdapter.listTaskDefinitions(),
      ]);
      setPending(dashResult.pending);
      setCompleted(dashResult.completed);
      setUsers(allUsers);
      setDefs(allDefs);
      setError(null);
    } catch (e) { setError(e.message); }
  }

  // Refresh when child filter changes
  useEffect(() => { refresh(); }, [selectedChildId]);

  // Reactively refresh on task completion events
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const handler = () => refresh();
    window.addEventListener('ftm:taskCompleted', handler);
    return () => window.removeEventListener('ftm:taskCompleted', handler);
  }, [selectedChildId]);

  async function overrideComplete(instanceId) {
    await parentCompletesOnBehalf({ stateAdapter: ftm.stateAdapter, orchestrationAdapter: ftm.orchestrationAdapter, instanceId, parentId: identity.userId, currentTime: new Date().toISOString() });
    refresh();
  }

  const children = useMemo(() => users.filter(u => u['ftm:role'] === 'child'), [users]);
  const userById = useMemo(() => new Map(users.map(u => [u['@id'], u])), [users]);
  const defById = useMemo(() => new Map(defs.map(d => [d['@id'], d])), [defs]);

  function formatDueAt(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString();
  }

  function renderInstance(inst) {
    const byRole = inst['ftm:completionState']['ftm:completedByRole'];
    const def = defById.get(inst['ftm:taskDefinition']);
    const child = userById.get(inst['ftm:assignedTo']);
    const title = def ? def['ftm:title'] : '(unknown task)';
    const childName = child ? child['ftm:displayName'] : inst['ftm:assignedTo'].split(':').pop();
    const isPending = inst['ftm:completionState']['ftm:status'] === 'pending';
    return html`
      <li key=${inst['@id']}>
        <div className="task-line">
          <a href=${'#/parent/instance/' + inst['@id'].split(':').pop()} className="task-title">${title}</a>
          <span className="task-assignee">→ ${childName}</span>
          <span className="task-due">due ${formatDueAt(inst['ftm:dueAt']['@value'])}</span>
        </div>
        <div className="task-actions">
          ${byRole === 'parent' ? html`<span className="badge">Parent Override</span>` : null}
          ${isPending ? html`<button onClick=${() => overrideComplete(inst['@id'])}>Mark Complete (Override)</button>` : null}
        </div>
      </li>
    `;
  }

  return html`
    <div className="parent-dashboard">
      <h2>Dashboard</h2>
      ${error ? html`<p className="error">${error}</p>` : null}
      ${children.length > 0 ? html`
        <div className="dashboard-filter">
          <label>Show tasks for
            <select value=${selectedChildId} onChange=${e => setSelectedChildId(e.target.value)}>
              <option value="">All children</option>
              ${children.map(c => html`<option key=${c['@id']} value=${c['@id']}>${c['ftm:displayName']}</option>`)}
            </select>
          </label>
        </div>
      ` : null}
      <section>
        <h3>Pending (${pending.length})</h3>
        ${pending.length === 0 ? html`<p className="empty">Nothing pending.</p>` : html`<ul>${pending.map(renderInstance)}</ul>`}
      </section>
      <section>
        <h3>Completed (${completed.length})</h3>
        ${completed.length === 0 ? html`<p className="empty">No completed tasks yet.</p>` : html`<ul>${completed.map(renderInstance)}</ul>`}
      </section>
      <p className="dashboard-actions"><a href="#/parent/create">+ Create Task</a> · <a href="#/parent/users">Manage family members</a></p>
    </div>
  `;
}
