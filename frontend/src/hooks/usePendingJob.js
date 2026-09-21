/**
 * Manages saving a job that a guest user tried to start before logging in,
 * so it can be automatically resumed once they authenticate.
 */

const PENDING_JOB_KEY = 'os_pending_job';
const PENDING_JOB_TTL_MS = 60 * 60 * 1000;

// The browser extension has no local storage shared with the main site, so it
// bridges the gap by passing the job as a URL parameter. We grab it here and
// treat it identically to a stashed local job.
let pendingJobInMemory = null;
if (typeof window !== 'undefined') {
  const params = new URLSearchParams(window.location.search);
  const extJob = params.get('ext_job');
  if (extJob) {
    try {
      pendingJobInMemory = {
        data: JSON.parse(decodeURIComponent(extJob)),
        stamp: Date.now()
      };
      // Clean up the URL so it doesn't get bookmarked or shared
      window.history.replaceState({}, document.title, window.location.pathname);
    } catch (e) {
      console.error("Failed to parse extension job", e);
    }
  }
}

export function usePendingJob() {
  const stashPendingJob = (data) => {
    try {
      const entry = { data, stamp: Date.now() };
      localStorage.setItem(PENDING_JOB_KEY, JSON.stringify(entry));
      pendingJobInMemory = null;
    } catch (e) { }
  };

  const peekPendingJob = () => {
    try {
      const raw = localStorage.getItem(PENDING_JOB_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed?.data?.payload && Date.now() - (parsed.stamp || 0) < PENDING_JOB_TTL_MS) {
          return parsed.data;
        }
        localStorage.removeItem(PENDING_JOB_KEY);
      }
    } catch (e) { }

    if (pendingJobInMemory && Date.now() - pendingJobInMemory.stamp < PENDING_JOB_TTL_MS) {
      return pendingJobInMemory.data;
    }
    return null;
  };

  const popPendingJob = () => {
    const job = peekPendingJob();
    if (job) {
      localStorage.removeItem(PENDING_JOB_KEY);
      pendingJobInMemory = null;
    }
    return job;
  };

  return { stashPendingJob, peekPendingJob, popPendingJob };
}
