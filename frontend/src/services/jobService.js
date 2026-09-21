/**
 * Job submission and polling service.
 *
 * Encapsulates all HTTP operations related to creating and monitoring
 * processing jobs via the OpenShorts API. Components call these functions
 * instead of calling apiFetch directly for job-related operations.
 */

import { apiFetch } from '../lib/api';

/**
 * Submits a processing job to the API.
 *
 * @param {object} params
 * @param {object} params.body  - The request body (FormData or JSON string)
 * @param {object} params.headers - Additional headers (e.g. X-Gemini-Key, Content-Type)
 * @returns {Promise<Response>}
 */
export async function submitJob({ body, headers = {} }) {
  return apiFetch('/api/process', { method: 'POST', headers, body });
}

/**
 * Polls the status of an existing job.
 *
 * @param {string} jobId
 * @returns {Promise<object>} Parsed JSON response with status, logs, result, etc.
 */
export async function pollJobStatus(jobId) {
  const res = await apiFetch(`/api/status/${jobId}`);
  if (!res.ok) throw new Error('Status check failed');
  return res.json();
}

/**
 * Downloads all clips for a job as a ZIP archive.
 * Returns the raw Response so the caller can stream/blob it.
 *
 * @param {string} jobId
 * @returns {Promise<Response>}
 */
export async function downloadAllClips(jobId) {
  const res = await apiFetch(`/api/jobs/${jobId}/download-all`);
  return res;
}

/**
 * Fetches the source video URL for a processing job.
 * 
 * @param {string} jobId 
 * @returns {Promise<object>} { url: string }
 */
export async function fetchSourceUrl(jobId) {
  const res = await apiFetch(`/api/source-url/${jobId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
