/**
 * Thumbnail Studio service.
 *
 * Encapsulates all API calls for the AI Thumbnail generation workflow:
 * background pre-upload, video analysis, title refinement via chat,
 * thumbnail generation, and description generation.
 */

import { apiFetch } from '../lib/api';

/**
 * Pre-uploads a video file and starts Whisper transcription in the background.
 * Called as soon as the user drops a file, before they click Analyze.
 *
 * @param {File} file
 * @returns {Promise<{session_id: string}>}
 */
export async function preUploadVideo(file) {
  const formData = new FormData();
  formData.append('file', file);
  const res = await apiFetch('/api/thumbnail/upload', {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/**
 * Analyzes an uploaded video and returns 10 viral title suggestions.
 *
 * @param {FormData} formData - Contains file or session_id plus optional headers
 * @param {object} keyHeader - { 'X-Gemini-Key': key } or {}
 * @returns {Promise<{session_id, titles, thumbnail_texts, recommended}>}
 */
export async function analyzeVideo(formData, keyHeader = {}) {
  const res = await apiFetch('/api/thumbnail/analyze', {
    method: 'POST',
    headers: keyHeader,
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/**
 * Refines title suggestions via a chat message or creates a manual session.
 *
 * @param {object} params - { session_id, message?, title? }
 * @param {object} keyHeader - { 'X-Gemini-Key': key } or {}
 * @returns {Promise<{titles, thumbnail_texts}>}
 */
export async function refineTitles(params, keyHeader = {}) {
  const res = await apiFetch('/api/thumbnail/titles', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...keyHeader },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/**
 * Generates AI thumbnail images.
 *
 * @param {FormData} formData - Contains session_id, title, extra_prompt, count, etc.
 * @param {object} keyHeader - { 'X-Gemini-Key': key } or {}
 * @returns {Promise<{thumbnails: string[]}>}
 */
export async function generateThumbnails(formData, keyHeader = {}) {
  const res = await apiFetch('/api/thumbnail/generate', {
    method: 'POST',
    headers: keyHeader,
    body: formData,
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    throw new Error(errData?.detail || `Server error ${res.status}`);
  }
  return res.json();
}

/**
 * Generates a video description from the thumbnail/session context.
 *
 * @param {object} params - { session_id, title }
 * @param {object} keyHeader - { 'X-Gemini-Key': key } or {}
 * @returns {Promise<{description: string}>}
 */
export async function generateDescription(params, keyHeader = {}) {
  const res = await apiFetch('/api/thumbnail/describe', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...keyHeader },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/**
 * Fetches extracted video frames for the thumbnail wizard.
 *
 * @param {string} sessionId
 * @returns {Promise<{frames: string[]}>}
 */
export async function fetchFrames(sessionId) {
  const res = await apiFetch(`/api/thumbnail/frames/${sessionId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/**
 * Publishes the thumbnail session (saves final selections).
 *
 * @param {object} params - { session_id, title, thumbnail_url, description }
 * @returns {Promise<{job_id: string}>}
 */
export async function publishThumbnail(params) {
  const formData = new FormData();
  for (const [key, value] of Object.entries(params)) {
    if (value != null) formData.append(key, value);
  }
  const res = await apiFetch('/api/thumbnail/publish', {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
