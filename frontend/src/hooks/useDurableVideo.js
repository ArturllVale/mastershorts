import { useState, useEffect } from 'react';
import { getApiUrl } from '../config';

export function useDurableVideo({ clip, durable, initialState }) {
  // Pristine base clip (no burned subtitles/hook), stable regardless of how
  // clip.video_url mutates after server edits. Used as the compositing base
  // for the Remotion preview so it never stacks subtitles over an already-
  // subtitled file (double-subtitle bug).
  const stripBurns = (filename) => {
    let f = filename || '', prev;
    do { prev = f; f = f.replace(/^subtitled_\d+_/, '').replace(/^hooked_\d+_/, '').replace(/^hook_/, ''); } while (f !== prev);
    return f;
  };
  
  const originalVideoUrl = getApiUrl((clip.video_url || '').replace(/[^/]+$/, stripBurns((clip.video_url || '').split('/').pop())));
  const [currentVideoUrl, setCurrentVideoUrl] = useState(getApiUrl(clip.video_url));
  const [durableSrc, setDurableSrc] = useState(null);
  const [durableFailed, setDurableFailed] = useState(false);
  const [hasPlayed, setHasPlayed] = useState(false);
  
  const [serverVideoFile, setServerVideoFile] = useState(initialState?.server_file || (clip.video_url || '').split('/').pop());
  const [videoErrored, setVideoErrored] = useState(false);

  useEffect(() => {
    if (durable?.url && durable.filename && durable.filename === serverVideoFile && !hasPlayed) {
      setDurableSrc((prev) => prev || durable.url);
    } else {
      setDurableSrc(null);
    }
  }, [durable?.url, durable?.filename, serverVideoFile, hasPlayed]);

  useEffect(() => {
    if (videoErrored && durable?.url && currentVideoUrl !== durable.url) {
      setCurrentVideoUrl(durable.url);
      setVideoErrored(false);
    }
  }, [videoErrored, durable, currentVideoUrl]);

  return {
    originalVideoUrl,
    currentVideoUrl,
    setCurrentVideoUrl,
    durableSrc,
    durableFailed,
    setDurableFailed,
    hasPlayed,
    setHasPlayed,
    serverVideoFile,
    setServerVideoFile,
    videoErrored,
    setVideoErrored
  };
}
