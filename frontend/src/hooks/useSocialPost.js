import { useState } from 'react';
import { postToSocial } from '../services/socialService';

export function useSocialPost({
  isManaged,
  uploadPostKey,
  uploadUserId,
  noAccountsConnected,
  jobId,
  index,
  setShowModal
}) {
  const [posting, setPosting] = useState(false);
  const [postResult, setPostResult] = useState(null);

  const canPost = isManaged || (uploadPostKey && uploadUserId);

  const handlePost = async ({
    platforms,
    postTitle,
    postDescription,
    isScheduling,
    scheduleDate
  }) => {
    if (!canPost) {
      setPostResult({ success: false, msg: "Missing API Key or User ID." });
      return;
    }

    if (noAccountsConnected) {
      setPostResult({ success: false, msg: "Connect a social account first." });
      return;
    }

    const selectedPlatforms = Object.keys(platforms).filter(k => platforms[k]);
    if (selectedPlatforms.length === 0) {
      setPostResult({ success: false, msg: "Select at least one platform." });
      return;
    }

    if (isScheduling && !scheduleDate) {
      setPostResult({ success: false, msg: "Please select a date and time." });
      return;
    }

    setPosting(true);
    setPostResult(null);

    try {
      const payload = {
        job_id: jobId,
        clip_index: index,
        api_key: uploadPostKey,
        user_id: uploadUserId,
        platforms: selectedPlatforms,
        title: postTitle,
        description: postDescription
      };

      if (isScheduling && scheduleDate) {
        payload.scheduled_date = new Date(scheduleDate).toISOString();
        payload.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      }

      await postToSocial(payload);

      setPostResult({ success: true, msg: isScheduling ? "Scheduled successfully!" : "Posted successfully!" });
      setTimeout(() => {
        setShowModal(false);
        setPostResult(null);
      }, 3000);

    } catch (e) {
      setPostResult({ success: false, msg: `Failed: ${e.message}` });
    } finally {
      setPosting(false);
    }
  };

  return { posting, postResult, setPostResult, canPost, handlePost };
}
