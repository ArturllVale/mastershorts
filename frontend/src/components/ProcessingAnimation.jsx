import React, { useEffect, useState, useRef } from 'react';
import { Scan, Scissors, Activity, Radio, CheckCircle } from 'lucide-react';
import { getApiUrl } from '../config';
import { apiFetch } from '../lib/api';
import { fetchSourceUrl } from '../services/jobService';

const ProcessingAnimation = ({ media, isComplete, syncedTime, isSyncedPlaying, syncTrigger }) => {
  const [videoSrc, setVideoSrc] = useState(null);
  const [isYouTube, setIsYouTube] = useState(false);
  const videoRef = useRef(null);
  const iframeRef = useRef(null);

  useEffect(() => {
    if (!media) return;

    if (media.type === 'file') {
      const url = URL.createObjectURL(media.payload);
      setIsYouTube(false);
      setVideoSrc(url);
      return () => URL.revokeObjectURL(url);
    } else if (media.type === 'server') {
      // Uploaded source served from the backend (survives a page reload).
      // The payload is the plain /api/source/<job> path, because that is what
      // gets persisted; the signed URL is minted here, at render, so a stored
      // session never carries a token that has since expired. A <video> tag
      // cannot send the bearer header itself, hence the round trip.
      setIsYouTube(false);
      let cancelled = false;
      const jobId = media.payload.split('/').pop();
      (async () => {
        try {
          const data = await fetchSourceUrl(jobId);
          if (!cancelled && data.url) setVideoSrc(getApiUrl(data.url));
        } catch (e) {
          // Self-host, or a backend without the endpoint: the open path still
          // works there, and losing the preview is worse than an unsigned URL.
          if (!cancelled) setVideoSrc(getApiUrl(media.payload));
        }
      })();
      return () => { cancelled = true; };
    } else if (media.type === 'url') {
      setIsYouTube(true);
      const videoId = getYouTubeId(media.payload);
      setVideoSrc(videoId);
    }
  }, [media]);

  // Handle Sync Playback for Local Video
  useEffect(() => {
    if (!isYouTube && videoRef.current) {
      if (isSyncedPlaying) {
        // Sync Mode: Seek to time and Play. A non-finite time (a clip with no
        // start yet) would throw and take the whole tree down — skip the seek.
        if (Number.isFinite(syncedTime)) videoRef.current.currentTime = syncedTime;
        videoRef.current.play().catch(e => console.log("Auto-play prevented", e));
        videoRef.current.loop = false;
        videoRef.current.muted = true; // Keep muted to avoid double audio with clip
      } else {
        // Stop Sync: Pause. Once analysis is complete, resume the ambient loop.
        videoRef.current.pause();

        if (isComplete) {
             videoRef.current.loop = true;
             videoRef.current.play().catch(e => console.log("Ambient play prevented", e));
        }
      }
    }
  }, [syncedTime, isSyncedPlaying, isYouTube, isComplete, syncTrigger]);

  // Handle Sync Playback for YouTube (Basic Iframe Control via PostMessage)
  useEffect(() => {
    if (isYouTube && iframeRef.current && videoSrc) {
        const iframeWindow = iframeRef.current.contentWindow;
        if (isSyncedPlaying) {
             // Seek and Play
             iframeWindow.postMessage(JSON.stringify({ event: 'command', func: 'seekTo', args: [syncedTime, true] }), '*');
             iframeWindow.postMessage(JSON.stringify({ event: 'command', func: 'playVideo', args: [] }), '*');
        } else {
             // Pause
             iframeWindow.postMessage(JSON.stringify({ event: 'command', func: 'pauseVideo', args: [] }), '*');
        }
    }
  }, [syncedTime, isSyncedPlaying, isYouTube, videoSrc, syncTrigger]);


  const getYouTubeId = (url) => {
    const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/;
    const match = url.match(regExp);
    return (match && match[2].length === 11) ? match[2] : null;
  };

  const containerClasses = `relative w-full shrink-0 aspect-video min-h-[180px] sm:min-h-[220px] max-h-[300px] xl:max-h-[340px] rounded-xl overflow-hidden bg-surface-1 border border-border mb-3 sm:mb-4 group animate-fade transition-all duration-500 shadow-2xl
    ${isComplete && !isSyncedPlaying ? 'grayscale brightness-50' : ''}
    ${isSyncedPlaying ? 'ring-2 ring-accent ring-offset-2 ring-offset-canvas' : ''}`;

  const getVideoOpacityClass = () => {
    if (isSyncedPlaying) return 'opacity-100'; // Playing: Full visibility
    if (isComplete) return 'opacity-30';       // Idle Result: Darker
    return 'opacity-40 grayscale group-hover:grayscale-0'; // Processing: Dark + Grayscale effect
  };

  return (
    <div className={containerClasses}>
      {/* Video Layer */}
      <div className={`absolute inset-0 transition-all duration-700 ${getVideoOpacityClass()}`}>
        {isYouTube && videoSrc ? (
            <iframe
            ref={iframeRef}
            className={`w-full h-full ${isSyncedPlaying ? '' : 'pointer-events-none scale-110'}`}
            // Add enablejsapi=1 for postMessage control
            src={`https://www.youtube.com/embed/${videoSrc}?autoplay=1&mute=1&controls=0&loop=1&playlist=${videoSrc}&modestbranding=1&showinfo=0&rel=0&enablejsapi=1`}
            title="Processing Video"
            frameBorder="0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          />
        ) : videoSrc ? (
          <video
            ref={videoRef}
            src={videoSrc}
            className="w-full h-full object-cover"
            autoPlay
            muted
            loop
            playsInline
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-surface-1">
             <div className="w-12 h-12 border-2 border-border border-t-accent rounded-full animate-spin"></div>
          </div>
        )}
      </div>

      {/* Overlays - Hide when synced playing so user sees clean video */}
      {!isSyncedPlaying && !isComplete && (
        <>
            <div className="hidden sm:block absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:40px_40px] z-10 pointer-events-none"></div>
            <div className="absolute left-0 w-full h-[2px] bg-accent shadow-[0_0_15px_2px_var(--color-glow)] animate-[scan_2.5s_linear_infinite] z-20 pointer-events-none"></div>
            <div className="absolute left-0 w-full h-[15%] bg-accent/5 animate-[scan-overlay_2.5s_linear_infinite] z-10 pointer-events-none"></div>
        </>
      )}

      {/* Top HUD bar */}
      {!isSyncedPlaying && (
          <div className="absolute top-2 left-2 right-2 sm:top-2.5 sm:left-2.5 sm:right-2.5 z-30 flex items-center justify-between gap-2 pointer-events-none">
            <div className={`flex items-center gap-1.5 sm:gap-2 px-2.5 py-1 sm:px-3 sm:py-1.5 rounded-full bg-surface-1/90 backdrop-blur-md border border-border font-mono text-[11px] sm:text-xs tracking-wide min-w-0 transition-colors duration-500 ${isComplete ? 'text-success border-success/30' : 'text-accent border-accent/30 animate-pulse'}`}>
              {isComplete
                ? <CheckCircle size={13} className="shrink-0" />
                : <Scan size={13} className="shrink-0" />}
              <span className="truncate">{isComplete ? 'ANÁLISE CONCLUÍDA' : 'ANALISANDO VÍDEO...'}</span>
            </div>
            {!isComplete && (
              <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 sm:px-3 sm:py-1.5 bg-surface-1/90 backdrop-blur-md border border-border rounded-full font-mono text-[10px] sm:text-xs tracking-wide text-text-tertiary shrink-0">
                <span className="w-1.5 h-1.5 rounded-full bg-accent animate-ping" />
                <span className="truncate">DETECÇÃO DE VIRAIS: ATIVA</span>
              </div>
            )}
          </div>
      )}

      {/* Visual Flair */}
      {!isSyncedPlaying && !isComplete && (
          <div className="hidden md:block absolute inset-0 pointer-events-none z-20 overflow-hidden">
             <div className="absolute top-0 bottom-0 left-[35%] w-px border-r border-dashed border-accent/25"></div>
             <div className="absolute top-0 bottom-0 right-[35%] w-px border-l border-dashed border-accent/25"></div>
             <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-10 h-10 border border-border/80 rounded-full flex items-center justify-center">
                <div className="w-1.5 h-1.5 bg-accent rounded-full animate-ping"></div>
             </div>
             <div className="absolute bottom-1/4 left-1/2 -translate-x-1/2 flex flex-col items-center justify-center gap-1 opacity-50">
                 <Scissors size={16} className="text-white/30" />
             </div>
          </div>
      )}

       {/* Synced Playing Indicator */}
       {isSyncedPlaying && (
           <div className="absolute top-2.5 right-2.5 sm:top-4 sm:right-4 z-30 badge-brass bg-surface-1/90 backdrop-blur-md animate-pulse shadow-lg">
               <Activity size={12} /> Sincronização ao Vivo
           </div>
       )}

       {/* Bottom Info Bar */}
      {!isSyncedPlaying && !isComplete && (
          <div className="hidden sm:flex absolute bottom-0 left-0 right-0 px-3 py-1.5 sm:px-3.5 sm:py-2 bg-surface-1/95 backdrop-blur-md z-30 justify-between items-center border-t border-border">
              <div className="font-mono text-[10px] sm:text-[11px] text-accent space-y-0.5 min-w-0">
                 <div className="flex items-center gap-1.5 truncate"><Activity size={10} className="animate-pulse shrink-0" /> <span>{'>'} ANÁLISE_IA: EM ANDAMENTO</span></div>
                 <div className="flex items-center gap-1.5 truncate"><Radio size={10} className="shrink-0" /> <span>{'>'} TRANSCRIÇÃO_DE_ÁUDIO: EM ANDAMENTO</span></div>
              </div>
              <div className="flex gap-1 items-end h-3.5 shrink-0 ml-2">
                 <div className="w-1 h-2 bg-accent opacity-40 animate-[pulse_0.5s_infinite]"></div>
                 <div className="w-1 h-3.5 bg-accent opacity-70 animate-[pulse_0.7s_infinite]"></div>
                 <div className="w-1 h-1.5 bg-accent opacity-30 animate-[pulse_0.4s_infinite]"></div>
                 <div className="w-1 h-3 bg-accent opacity-90 animate-[pulse_0.6s_infinite]"></div>
                 <div className="w-1 h-2 bg-accent opacity-50 animate-[pulse_0.5s_infinite]"></div>
              </div>
          </div>
      )}
    </div>
  );
};

export default ProcessingAnimation;
