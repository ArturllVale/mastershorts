/**
 * Project persistence service.
 *
 * Encapsulates REST operations for the library / history feature:
 * restoring archived projects from R2, syncing per-clip edit state,
 * and reading the history feed to build the durable URL map.
 */

import { apiFetch, apiJson } from '../lib/api';

/**
 * Restores an archived project from R2 back into the server's working dir.
 *
 * @param {string} jobId
 * @returns {Promise<object>} { job_id, result, project_state }
 */
export async function restoreProject(jobId) {
  return apiJson(`/api/projects/${jobId}/restore`, { method: 'POST' });
}

/**
 * Persists per-clip editor state (Remotion layers + current server file)
 * to the backend so a reopened project resumes intact.
 *
 * @param {string} jobId
 * @param {Array<{index: number, active_layers: object, server_file: string}>} clips
 * @returns {Promise<void>}
 */
export async function saveProjectState(jobId, clips) {
  await apiFetch(`/api/projects/${jobId}/state`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ clips }),
  });
}

/**
 * Reads the full history feed and reduces it to a {clipIndex → {url, filename}}
 * map for a specific job. Used to build the durable R2 fallback map.
 *
 * @param {string} jobId
 * @returns {Promise<Record<number, {url: string, filename: string}>>}
 */
export async function fetchDurableMap(jobId) {
  const d = await apiJson('/api/history');
  const map = {};
  for (const v of d.videos || []) {
    if (v.job_id === jobId && v.clip_index != null) {
      map[v.clip_index] = { url: v.view_url, filename: v.filename };
    }
  }
  return map;
}
