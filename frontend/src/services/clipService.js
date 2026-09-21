/**
 * Clip editing and processing service.
 *
 * Encapsulates all API operations that modify or produce video files:
 * subtitle burning, hook insertion, translation, auto-edit, EDL load/rerender,
 * and transcript fetching. Components call these functions instead of hitting
 * apiFetch directly for clip-related mutations.
 */

import { apiFetch, apiJson } from '../lib/api';

/**
 * Burns subtitles into a clip server-side via FFmpeg.
 *
 * @param {object} params - Full subtitle options object expected by /api/subtitle
 * @returns {Promise<object>} { new_video_url, ... }
 */
export async function applySubtitles(params) {
  const res = await apiFetch('/api/subtitle', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/**
 * Burns a hook overlay into a clip.
 *
 * @param {object} params - Hook options (job_id, clip_index, text, style, etc.)
 * @returns {Promise<object>} { new_video_url, ... }
 */
export async function applyHook(params) {
  const res = await apiFetch('/api/hook', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/**
 * Auto-edits a clip: tries Remotion effects endpoint first, falls back to
 * the legacy FFmpeg /api/edit endpoint.
 *
 * @param {object} params - { job_id, clip_index, input_filename, geminiHeaders }
 * @returns {Promise<{type: 'effects'|'edit', data: object}>}
 */
export async function autoEditClip({ job_id, clip_index, input_filename, geminiHeaders = {} }) {
  // Try Remotion effects first
  const effectsRes = await apiFetch('/api/effects/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...geminiHeaders },
    body: JSON.stringify({ job_id, clip_index, input_filename }),
  });

  if (effectsRes.ok) {
    const data = await effectsRes.json();
    if (data.effects?.segments) {
      return { type: 'effects', data };
    }
  }

  // Fallback: legacy FFmpeg edit
  const res = await apiFetch('/api/edit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...geminiHeaders },
    body: JSON.stringify({ job_id, clip_index, input_filename }),
  });

  if (!res.ok) {
    const errText = await res.text();
    try {
      const jsonErr = JSON.parse(errText);
      throw new Error(jsonErr.detail || errText);
    } catch {
      throw new Error(errText);
    }
  }

  const data = await res.json();
  return { type: 'edit', data };
}

/**
 * Re-renders a clip from an EDL recipe via the clip editor.
 *
 * @param {object} params - { jobId, clipIndex, segments, reapply_captions, framing }
 * @returns {Promise<object>} { new_video_url, start, end, recipe, ... }
 */
export async function rerenderClip({ jobId, clipIndex, segments, reapply_captions, framing }) {
  const res = await apiFetch('/api/clip/rerender', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      job_id: jobId,
      clip_index: clipIndex,
      segments,
      snap_to_words: false,
      reapply_captions,
      framing
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/**
 * Fetches the Edit Decision List (EDL) for a clip.
 *
 * @param {string} jobId
 * @param {number} clipIndex
 * @returns {Promise<object>} EDL data (segments, words, source, canonical_range, etc.)
 */
export async function fetchEDL(jobId, clipIndex) {
  return apiJson(`/api/clip/${jobId}/${clipIndex}/edl`);
}

/**
 * Fetches transcript metadata for a clip (used to read accurate duration).
 *
 * @param {string} jobId
 * @param {number} clipIndex
 * @returns {Promise<object|null>} { durationSec, ... } or null on failure
 */
export async function fetchClipTranscript(jobId, clipIndex) {
  const res = await apiFetch(`/api/clip/${jobId}/${clipIndex}/transcript`);
  if (!res.ok) return null;
  return res.json();
}

/**
 * Removes server-burned subtitles from a clip.
 *
 * @param {object} params - { job_id, clip_index }
 * @returns {Promise<object>} { new_video_url, ... }
 */
export async function removeSubtitles(params) {
  const res = await apiFetch('/api/subtitle/remove', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/**
 * Fetches detected scenes for a clip.
 *
 * @param {string} jobId
 * @param {number} clipIndex
 * @returns {Promise<object>} { scenes: [...] }
 */
export async function fetchScenes(jobId, clipIndex) {
  return apiJson(`/api/clip/${jobId}/${clipIndex}/scenes`);
}

/**
 * Applies smart or manual reframing to a clip.
 *
 * @param {object} payload - { job_id, clip_index, framing, manual_crop }
 * @returns {Promise<object>} { new_video_url: string, recipe: object }
 */
export async function reframeClip(payload) {
  return apiJson('/api/clip/reframe', {
    method: 'POST',
    body: payload,
  });
}
