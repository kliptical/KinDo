import React, { useState } from 'react';
import { html } from 'htm/react';
import { parentCreatesTask } from '../../flows/parentCreatesTask.js';
import { validateTaskDefinition } from '../../validation/validateTaskDefinition.js';
import { createTaskDefinition } from '../../entities/taskDefinition.js';

// Coerce any stored datetime value to the yyyy-MM-ddTHH:mm format that
// <input type="datetime-local"> accepts. Handles: native picker output
// (already yyyy-MM-ddTHH:mm), ISO-with-Z strings (parses + formats local),
// and empty/null.
function toDatetimeLocal(v) {
  if (!v) return '';
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(v)) {
    // already datetime-local-compatible; truncate any seconds the browser added
    return v.slice(0, 16);
  }
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return '';
  // Format to local timezone yyyy-MM-ddTHH:mm
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function TaskCreator({ ftm, identity, onCreated }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [assignedTo, setAssignedTo] = useState('');
  const [dueAt, setDueAt] = useState('');
  const [scheduleType, setScheduleType] = useState('one-time');
  const [recurrenceRule, setRecurrenceRule] = useState('');
  const [recurrenceStart, setRecurrenceStart] = useState('');
  const [reminderMode, setReminderMode] = useState('once');
  const [intervalSeconds, setIntervalSeconds] = useState(1800);
  const [persistUntilSeconds, setPersistUntilSeconds] = useState(86400); // default per SPEC §10
  const [errors, setErrors] = useState([]);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    // dueAt and recurrenceStart hold the raw datetime-local input string (yyyy-MM-ddTHH:mm).
    // Convert to canonical ISO-8601 UTC here at submit time only.
    const dueAtIso = dueAt ? new Date(dueAt).toISOString() : '';
    const recurrenceStartIso = recurrenceStart ? new Date(recurrenceStart).toISOString() : null;
    // Construct a candidate TaskDefinition object for §11 validation (factory generates the @id/timestamps).
    const params = { title, description, assignedTo, createdBy: identity.userId, dueAt: dueAtIso, scheduleType, recurrenceRule: scheduleType === 'recurring' ? recurrenceRule : null, recurrenceStart: scheduleType === 'recurring' ? recurrenceStartIso : null, reminderMode, intervalSeconds: reminderMode === 'persistent' ? Number(intervalSeconds) : null, persistUntilSeconds: reminderMode === 'persistent' ? Number(persistUntilSeconds) : null };
    const candidate = createTaskDefinition(params);
    const result = validateTaskDefinition(candidate);
    if (!result.valid) { setErrors(result.errors); return; }
    setErrors([]); setSubmitting(true);
    try {
      const { taskDef, instances } = await parentCreatesTask({ stateAdapter: ftm.stateAdapter, orchestrationAdapter: ftm.orchestrationAdapter, params });
      onCreated && onCreated({ taskDef, instances });
      setTitle(''); setDescription(''); setDueAt('');
    } finally { setSubmitting(false); }
  }

  return html`
    <form className="task-creator" onSubmit=${handleSubmit}>
      <h2>Create Task</h2>
      ${errors.length > 0 ? html`<ul className="errors">${errors.map(e => html`<li key=${e}>${e}</li>`)}</ul>` : null}
      <label>Title<input value=${title} onChange=${e => setTitle(e.target.value)} required /></label>
      <label>Description<textarea value=${description} onChange=${e => setDescription(e.target.value)} /></label>
      <label>Assigned to (child userId)<input value=${assignedTo} onChange=${e => setAssignedTo(e.target.value)} placeholder="urn:ftm:child:..." required /></label>
      <label>Due at<input type="datetime-local" value=${toDatetimeLocal(dueAt)} onChange=${e => setDueAt(e.target.value)} required /></label>
      <label>Schedule<select value=${scheduleType} onChange=${e => setScheduleType(e.target.value)}><option value="one-time">One-time</option><option value="recurring">Recurring</option></select></label>
      ${scheduleType === 'recurring' ? html`
        <label>Recurrence rule (RRULE)<input value=${recurrenceRule} onChange=${e => setRecurrenceRule(e.target.value)} placeholder="FREQ=DAILY" /></label>
        <label>Recurrence start<input type="datetime-local" value=${toDatetimeLocal(recurrenceStart)} onChange=${e => setRecurrenceStart(e.target.value)} /></label>
      ` : null}
      <label>Reminder mode<select value=${reminderMode} onChange=${e => setReminderMode(e.target.value)}><option value="once">Once</option><option value="persistent">Persistent</option></select></label>
      ${reminderMode === 'persistent' ? html`
        <label>Interval seconds<input type="number" value=${intervalSeconds} onChange=${e => setIntervalSeconds(e.target.value)} min="60" /></label>
        <label>Persist until seconds (default 86400)<input type="number" value=${persistUntilSeconds} onChange=${e => setPersistUntilSeconds(e.target.value)} /></label>
      ` : null}
      <button type="submit" disabled=${submitting}>${submitting ? 'Creating...' : 'Create'}</button>
    </form>
  `;
}
