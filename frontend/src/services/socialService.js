/**
 * Social publishing service.
 *
 * Encapsulates all HTTP calls related to the social posting integration
 * (Upload-Post). Components call these functions instead of apiFetch directly.
 */

import { apiFetch } from '../lib/api';

/**
 * Fetches connected social profiles for the current user.
 *
 * @returns {Promise<object>} Profiles data from Upload-Post API
 */
export async function fetchUserProfiles() {
  const res = await apiFetch('/api/social/user', { headers: {} });
  if (!res.ok) throw new Error('Failed to fetch social profiles');
  return res.json();
}

/**
 * Posts a clip to one or more social platforms via Upload-Post.
 *
 * @param {object} params - { job_id, clip_index, platforms, title, description,
 *                           schedule_date, upload_post_key, user_id }
 * @returns {Promise<object>} Post result from the API
 */
export async function postToSocial(params) {
  const res = await apiFetch('/api/social/post', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
