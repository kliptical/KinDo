import React, { useEffect, useState } from 'react';
import { html } from 'htm/react';
import { resolveDeepLink } from '../../routing/deepLink.js';

export default function TaskDetailParent({ ftm, instanceId }) {
  const [instance, setInstance] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    resolveDeepLink('ftm://instance/' + instanceId, { stateAdapter: ftm.stateAdapter }).then(inst => {
      if (cancelled) return; setInstance(inst); setLoading(false);
    });
    return () => { cancelled = true; };
  }, [instanceId]);

  if (loading) return html`<p>Loading...</p>`;
  if (!instance) return html`<p>Task not found.</p>`;

  const summary = instance['ftm:reminderSummary'];
  const events = summary['ftm:recentEvents'] || [];

  return html`
    <div className="task-detail-parent">
      <h2>${instance['@id'].split(':').pop()}</h2>
      <p><strong>Assigned to:</strong> ${instance['ftm:assignedTo']}</p>
      <p><strong>Due:</strong> ${instance['ftm:dueAt']['@value']}</p>
      <p><strong>Status:</strong> ${instance['ftm:completionState']['ftm:status']}</p>
      ${instance['ftm:completionState']['ftm:completedByRole'] ? html`<p><strong>Completed by:</strong> ${instance['ftm:completionState']['ftm:completedByRole']}</p>` : null}
      <h3>Reminder summary</h3>
      <p>Reminders sent: ${summary['ftm:totalSent']}</p>
      <p>Last delivery status: ${summary['ftm:lastDeliveryStatus'] ?? 'none'}</p>
      <h4>Recent events (last 3)</h4>
      ${events.length === 0 ? html`<p>No reminders sent yet.</p>` : html`<ul>${events.map((e, i) => html`<li key=${i}>${e['ftm:sentAt']['@value']} — ${e['ftm:deliveryStatus']}</li>`)}</ul>`}
      <p><a href="#/parent/dashboard">Back to dashboard</a></p>
    </div>
  `;
}
