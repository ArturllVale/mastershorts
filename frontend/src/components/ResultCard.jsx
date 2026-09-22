import React, { useState, useEffect } from 'react';
import { Download, Share2, Instagram, Youtube, Video, AlertCircle, Loader2, Copy, Check, Wand2, Type, Calendar, FileText, Link2, Scissors, Crosshair, TrendingUp } from 'lucide-react';
import { getApiUrl } from '../config';
import { apiFetch } from '../lib/api';
import SubtitleModal from './SubtitleModal';
import ReframeEditor from './ReframeEditor';
import ViralHUD from '../features/result-card/ViralHUD';
import ClipActionBar from '../features/result-card/ClipActionBar';
import SocialPostModal from '../features/result-card/SocialPostModal';

import HookModal from './HookModal';
import Modal from './ui/Modal';
import SegmentedControl from './ui/SegmentedControl';
import WatermarkModal, { watermarkNoticeDismissed } from './WatermarkModal';
import { useAuth } from '../contexts/AuthContext';
import { renderInBrowser } from '../lib/renderInBrowser';
import { applySubtitles, applyHook, autoEditClip, fetchClipTranscript, removeSubtitles } from '../services/clipService';
import { postToSocial } from '../services/socialService';
import { useStreamDownload } from '../hooks/useStreamDownload';
import { useSocialPost } from '../hooks/useSocialPost';
import { useDurableVideo } from '../hooks/useDurableVideo';

const QUIET_BTN = 'group flex flex-col items-center justify-center gap-1 py-2.5 sm:py-2 px-1 rounded-input border border-rule hover:bg-paper3 text-[11px] lowercase text-ink2 whitespace-nowrap transition-colors disabled:opacity-45 disabled:cursor-not-allowed';

const PLATFORM_OPTIONS = [
    { value: 'tiktok', label: 'tiktok', icon: <Video size={16} /> },
    { value: 'instagram', label: 'instagram', icon: <Instagram size={16} /> },
    { value: 'youtube', label: 'youtube', icon: <Youtube size={16} /> },
];

function clipDurationSeconds(clip) {
    // A recut clip's start/end are the covering source range (segments may be
    // non-contiguous or reordered); its real duration is the segment sum.
    const segments = clip.recipe?.segments;
    if (segments?.length) {
        return segments.reduce((acc, s) => acc + (s.end - s.start), 0);
    }
    return clip.end && clip.start ? clip.end - clip.start : NaN;
}

function formatDuration(clip) {
    const secs = Math.floor(clipDurationSeconds(clip));
    if (!Number.isFinite(secs) || secs < 0) return null;
    return `${String(Math.floor(secs / 60)).padStart(2, '0')}:${String(secs % 60).padStart(2, '0')}`;
}

export default function ResultCard({ clip, index, rankIndex, jobId, durable, uploadPostKey, uploadUserId, geminiApiKey, isManaged, onPlay, onPause, onBulkSubtitle, clipCount = 1, bulkProgress, initialState = null, onStateChange, connectedPlatforms = null, onConnectSocials, onEditClip = null, onReframeClip = null }) {
    const [showModal, setShowModal] = useState(false);
    const [showDescModal, setShowDescModal] = useState(false);
    const [showSubtitleModal, setShowSubtitleModal] = useState(false);
    const [showWatermarkModal, setShowWatermarkModal] = useState(false);
    const { plan } = useAuth();
    const videoRef = React.useRef(null);
    const {
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
    } = useDurableVideo({ clip, durable, initialState });

    const [resolution, setResolution] = useState(null);

    // A delivered clip is tens of MB, and on a slow link the old silent
    // fetch-then-save took minutes with nothing on screen, which reads as a dead
    // button. Stream it instead and report progress.
    const { downloadPct, downloadClip: streamDownloadClip } = useStreamDownload();

    const downloadClip = async () => {
        await streamDownloadClip(currentVideoUrl, `clip-${index + 1}.mp4`);
    };

    // When an external refresh changes this clip's server file (e.g. bulk
    // subtitles applied from another card), adopt it so the card shows the
    // freshly subtitled video instead of a stale one.
    useEffect(() => {
        const serverUrl = getApiUrl(clip.video_url);
        const serverName = (clip.video_url || '').split('/').pop();
        if (serverName && serverName !== serverVideoFile) {
            setServerVideoFile(serverName);
            setCurrentVideoUrl(serverUrl);
            setDurableFailed(false);
            setHasPlayed(false);
            if (videoRef.current) videoRef.current.load();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [clip.video_url]);

    const [platforms, setPlatforms] = useState({
        tiktok: true,
        instagram: true,
        youtube: true
    });
    const [postTitle, setPostTitle] = useState("");
    const [postDescription, setPostDescription] = useState("");
    const [isScheduling, setIsScheduling] = useState(false);
    const [scheduleDate, setScheduleDate] = useState("");
    const [copied, setCopied] = useState(null);

    const handleCopy = async (field, text) => {
        try {
            await navigator.clipboard.writeText(text || '');
            setCopied(field);
            setTimeout(() => setCopied(null), 2000);
        } catch {
            // clipboard unavailable — silent
        }
    };

    const [isEditing, setIsEditing] = useState(false);
    const [isSubtitling, setIsSubtitling] = useState(false);
    const [isHooking, setIsHooking] = useState(false);
    const [showHookModal, setShowHookModal] = useState(false);
    const [editError, setEditError] = useState(null);

    const [clipDuration, setClipDuration] = useState(() => {
        const secs = clipDurationSeconds(clip);
        return Number.isFinite(secs) ? secs : 30;
    });

    // Accumulate Remotion layers across operations. A reopened project restores
    // the layers persisted in its project state, so the next edit composes over
    // them instead of silently dropping previous browser-side work.
    const [activeLayers, setActiveLayers] = useState(initialState?.active_layers || { subtitles: null, hook: null, effects: null });

    // Report edit state upward (debounced sync to the project record). Skip the
    // mount run: only user-driven changes are worth persisting.
    const stateReported = React.useRef(false);
    useEffect(() => {
        if (!stateReported.current) { stateReported.current = true; return; }
        onStateChange?.(index, { activeLayers, serverVideoFile });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeLayers, serverVideoFile]);

    // True when the current server file already carries burned-in content.
    // Browser (Remotion) renders compose over the ORIGINAL clip, so using them
    // here would silently drop those burns — chain via server FFmpeg instead.
    const hasServerBurns = /(^|_)(subtitled|hook|hooked)_/.test(serverVideoFile || '');

    // The hook currently burned into the server file (auto-hook or a manual
    // one). /api/hook REPLACES it; tracked locally so the modal stays honest
    // after edits without refetching the job.
    const [burnedHook, setBurnedHook] = useState(clip.auto_hook?.text || null);

    // Fetch clip duration from transcript endpoint
    useEffect(() => {
        if (!jobId || index === undefined) return;
        fetchClipTranscript(jobId, index)
            .then(data => {
                if (data && data.durationSec) setClipDuration(data.durationSec);
            })
            .catch(() => {});
    }, [jobId, index]);

    // Which platforms the selected profile actually has linked. `null` means
    // unknown (profile list not loaded) — in that case nothing is gated.
    const knownConnections = Array.isArray(connectedPlatforms);
    const noAccountsConnected = knownConnections && connectedPlatforms.length === 0;
    const platformOptions = knownConnections
        ? PLATFORM_OPTIONS.map((o) => (connectedPlatforms.includes(o.value) ? o : { ...o, disabled: true, hint: 'not connected' }))
        : PLATFORM_OPTIONS;

    const handleConnectAccounts = () => {
        setShowModal(false);
        if (onConnectSocials) onConnectSocials();
        else window.open('https://app.upload-post.com', '_blank', 'noopener');
    };

    // Initialize/Reset form when modal opens
    useEffect(() => {
        if (showModal) {
            setPostTitle(clip.video_title_for_youtube_short || "Viral Short");
            setPostDescription(clip.video_description_for_instagram || clip.video_description_for_tiktok || "");
            setIsScheduling(false);
            setScheduleDate("");
            setPostResult(null);
            // Only preselect platforms the profile can actually publish to.
            if (knownConnections) {
                setPlatforms({
                    tiktok: connectedPlatforms.includes('tiktok'),
                    instagram: connectedPlatforms.includes('instagram'),
                    youtube: connectedPlatforms.includes('youtube'),
                });
            }
        }
        // Reset only when the modal opens for a clip; connection changes while
        // it is open must not wipe the user's selection.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [showModal, clip]);

    const handleAutoEdit = async () => {
        setIsEditing(true);
        setEditError(null);
        try {
            const apiKey = geminiApiKey || localStorage.getItem('gemini_key');

            // Managed (paid) users get the Gemini key resolved server-side;
            // only BYOK/self-host needs a local key.
            if (!apiKey && !isManaged) {
                throw new Error("Gemini API Key is missing. Please set it in Settings.");
            }
            const geminiHeaders = apiKey ? { 'X-Gemini-Key': apiKey } : {};

            // Try autoEditClip service
            if (!hasServerBurns) {
                try {
                    const result = await autoEditClip({
                        job_id: jobId,
                        clip_index: index,
                        input_filename: serverVideoFile,
                        geminiHeaders
                    });

                    if (result.type === 'effects') {
                        const newLayers = { ...activeLayers, effects: result.data.effects };
                        setActiveLayers(newLayers);
                        const blobUrl = await renderInBrowser({
                            videoUrl: originalVideoUrl,
                            durationInSeconds: clipDuration,
                            subtitles: newLayers.subtitles,
                            hook: newLayers.hook,
                            effects: newLayers.effects,
                        });
                        setCurrentVideoUrl(blobUrl);
                        if (videoRef.current) videoRef.current.load();
                        return;
                    } else if (result.type === 'edit') {
                        if (result.data.new_video_url) {
                            setCurrentVideoUrl(getApiUrl(result.data.new_video_url));
                            setServerVideoFile(result.data.new_video_url.split('/').pop());
                            if (videoRef.current) {
                                videoRef.current.load();
                            }
                        }
                    }
                } catch (e) {
                    throw e;
                }
            } else {
                // Legacy FFmpeg route (server-burned files can't use Remotion effects safely yet)
                const result = await autoEditClip({
                    job_id: jobId,
                    clip_index: index,
                    input_filename: serverVideoFile,
                    geminiHeaders
                });
                if (result.type === 'edit' && result.data.new_video_url) {
                    setCurrentVideoUrl(getApiUrl(result.data.new_video_url));
                    setServerVideoFile(result.data.new_video_url.split('/').pop());
                    if (videoRef.current) {
                        videoRef.current.load();
                    }
                }
            }

        } catch (e) {
            setEditError(e.message);
            setTimeout(() => setEditError(null), 5000);
        } finally {
            setIsEditing(false);
        }
    };

    // Clips are captioned by default, so "no captions" has to be reachable.
    // Nothing is re-encoded: the server still holds the clean file next to the
    // captioned one and just points this clip back at it.
    const handleRemoveSubtitles = async () => {
        setIsSubtitling(true);
        setEditError(null);
        try {
            const data = await removeSubtitles({
                job_id: jobId, clip_index: index, input_filename: serverVideoFile,
            });
            if (data.new_video_url) {
                const serverUrl = getApiUrl(data.new_video_url);
                setServerVideoFile(data.new_video_url.split('/').pop());
                const remaining = { ...activeLayers, subtitles: null };
                setActiveLayers(remaining);
                if (remaining.hook || remaining.effects) {
                    setCurrentVideoUrl(await renderInBrowser({
                        videoUrl: serverUrl,
                        durationInSeconds: clipDuration,
                        subtitles: null,
                        hook: remaining.hook,
                        effects: remaining.effects,
                    }));
                } else {
                    setCurrentVideoUrl(serverUrl);
                }
                if (videoRef.current) videoRef.current.load();
                setShowSubtitleModal(false);
            }
        } catch (e) {
            setEditError(e.message);
            setTimeout(() => setEditError(null), 5000);
        } finally {
            setIsSubtitling(false);
        }
    };

    const handleSubtitle = async (options) => {
        setIsSubtitling(true);
        setEditError(null);
        try {
            // Karaoke styles are burned server-side (ASS word-highlight render);
            // the in-browser Remotion path only handles classic styles, and only
            // when the server file has no burned-in content to preserve.
            if (options.remotion && options.style !== 'karaoke' && !hasServerBurns) {
                // Accumulate layer and render all layers together
                const newLayers = { ...activeLayers, subtitles: options.remotion };
                setActiveLayers(newLayers);
                const blobUrl = await renderInBrowser({
                    videoUrl: originalVideoUrl,
                    durationInSeconds: clipDuration,
                    subtitles: newLayers.subtitles,
                    hook: newLayers.hook,
                    effects: newLayers.effects,
                });
                setCurrentVideoUrl(blobUrl);
                if (videoRef.current) videoRef.current.load();
                setShowSubtitleModal(false);
                return;
            }

            // Fallback: legacy FFmpeg
            const data = await applySubtitles({
                job_id: jobId,
                clip_index: index,
                position: options.position,
                margin_v: options.margin_v ?? options.marginV ?? 43,
                max_chars: options.max_chars ?? 16,
                max_duration: options.max_duration ?? 1.4,
                font_size: options.fontSize,
                font_name: options.fontName,
                font_color: options.fontColor,
                border_color: options.borderColor,
                border_width: options.borderWidth,
                bg_color: options.bgColor,
                bg_opacity: options.bgOpacity,
                style: options.style || 'karaoke',
                highlight_color: options.highlightColor || '#FFE500',
                effect: options.effect || 'pop',
                base_opacity: options.baseOpacity ?? 1.0,
                uppercase: options.uppercase ?? true,
                input_filename: serverVideoFile,
                // Edited caption text (clip-relative ms); null = server
                // regenerates from the transcript as before.
                words: options.captions || null
            });
            if (data.new_video_url) {
                const serverUrl = getApiUrl(data.new_video_url);
                setServerVideoFile(data.new_video_url.split('/').pop());
                // Subtitles are burned into the server file now — drop the
                // browser subtitle layer and re-compose any remaining browser
                // layers (hook/effects) over the new file so they aren't lost.
                const remaining = { ...activeLayers, subtitles: null };
                setActiveLayers(remaining);
                if (remaining.hook || remaining.effects) {
                    const blobUrl = await renderInBrowser({
                        videoUrl: serverUrl,
                        durationInSeconds: clipDuration,
                        subtitles: null,
                        hook: remaining.hook,
                        effects: remaining.effects,
                    });
                    setCurrentVideoUrl(blobUrl);
                } else {
                    setCurrentVideoUrl(serverUrl);
                }
                if (videoRef.current) videoRef.current.load();
                setShowSubtitleModal(false);
            }
        } catch (e) {
            setEditError(e.message);
            setTimeout(() => setEditError(null), 5000);
        } finally {
            setIsSubtitling(false);
        }
    };

    const handleHook = async (hookData) => {
        setIsHooking(true);
        setEditError(null);
        try {
            if (hookData.remotion && !hasServerBurns) {
                // Accumulate layer and render all layers together
                const newLayers = { ...activeLayers, hook: hookData.remotion };
                setActiveLayers(newLayers);
                const blobUrl = await renderInBrowser({
                    videoUrl: originalVideoUrl,
                    durationInSeconds: clipDuration,
                    subtitles: newLayers.subtitles,
                    hook: newLayers.hook,
                    effects: newLayers.effects,
                });
                setCurrentVideoUrl(blobUrl);
                if (videoRef.current) videoRef.current.load();
                setShowHookModal(false);
                return;
            }

            // Fallback: legacy FFmpeg
            const payload = typeof hookData === 'string'
                ? { text: hookData, position: 'top', size: 'M' }
                : hookData;

            const data = await applyHook({
                job_id: jobId,
                clip_index: index,
                text: payload.text,
                position: payload.position,
                size: payload.size,
                style: payload.style || 'classic',
                duration_seconds: payload.remotion?.displayDurationSec ?? null,
                input_filename: serverVideoFile
            });

            if (data.new_video_url) {
                setCurrentVideoUrl(getApiUrl(data.new_video_url));
                setServerVideoFile(data.new_video_url.split('/').pop());
                setBurnedHook(data.burned_hook?.text ?? payload.text ?? null);
                if (videoRef.current) videoRef.current.load();
                setShowHookModal(false);
            }
        } catch (e) {
            setEditError(e.message);
            setTimeout(() => setEditError(null), 5000);
        } finally {
            setIsHooking(false);
        }
    };

    // Strip the burned hook (auto-hook or manual) off the server file.
    const handleRemoveHook = async () => {
        setIsHooking(true);
        setEditError(null);
        try {
            const data = await applyHook({
                job_id: jobId,
                clip_index: index,
                remove: true,
                input_filename: serverVideoFile,
            });
            if (data.new_video_url) {
                setCurrentVideoUrl(getApiUrl(data.new_video_url));
                setServerVideoFile(data.new_video_url.split('/').pop());
                setBurnedHook(null);
                if (videoRef.current) videoRef.current.load();
                setShowHookModal(false);
            }
        } catch (e) {
            setEditError(e.message);
            setTimeout(() => setEditError(null), 5000);
        } finally {
            setIsHooking(false);
        }
    };

    const { posting, postResult, setPostResult, canPost, handlePost } = useSocialPost({
        isManaged,
        uploadPostKey,
        uploadUserId,
        noAccountsConnected,
        jobId,
        index,
        setShowModal
    });

    const submitSocialPost = () => {
        handlePost({
            platforms,
            postTitle,
            postDescription,
            isScheduling,
            scheduleDate
        });
    };

    // Browser-rendered previews (Remotion) live in a blob: URL that exists only
    // in this tab, so they always win over the durable copy.
    const playbackUrl = (durableSrc && !durableFailed && !String(currentVideoUrl || '').startsWith('blob:'))
        ? durableSrc
        : currentVideoUrl;

    const durationReadout = formatDuration(clip);

    return (
        <div className="card overflow-hidden flex flex-col md:flex-row group hover:border-rule2 transition-colors animate-fade min-h-0 md:min-h-[390px] xl:min-h-[410px]" style={{ animationDelay: `${index * 0.1}s` }}>
            {/* Left: Video Preview — 9:16 column matching the card height */}
            <div className="w-full max-w-[calc(64vh*0.5625)] md:max-w-none mx-auto md:mx-0 md:w-[210px] xl:w-[224px] bg-black relative shrink-0 aspect-[9/16] md:aspect-auto group/video">
                <video
                    ref={videoRef}
                    src={playbackUrl}
                    controls
                    className="w-full h-full object-contain"
                    playsInline
                    onLoadedMetadata={(e) => {
                        if (e.target.videoWidth) setResolution(`${e.target.videoWidth}×${e.target.videoHeight}`);
                    }}
                    onError={() => {
                        // The durable copy is unreachable (signature expired after an
                        // hour on an idle tab, object purged) → serve from the API for
                        // the rest of this card's life.
                        if (playbackUrl === durableSrc) {
                            setDurableFailed(true);
                            return;
                        }
                        // Local /videos/ file gone (e.g. cleaned up after a reload) →
                        // fall back to the durable R2 copy for managed users. If the
                        // durable URL hasn't loaded yet, the effect above retries.
                        if (durable?.url && currentVideoUrl !== durable.url) setCurrentVideoUrl(durable.url);
                        else setVideoErrored(true);
                    }}
                    onPlay={() => {
                        setHasPlayed(true);
                        const currentTime = videoRef.current ? videoRef.current.currentTime : 0;
                        onPlay && onPlay(clip.start + currentTime);
                    }}
                    onPause={() => onPause && onPause()}
                    onEnded={() => {
                        if (videoRef.current) {
                            videoRef.current.currentTime = 0;
                            videoRef.current.play();
                        }
                    }}
                />
                <div className="absolute top-3 left-3 flex gap-2">
                    {/* Stays the clip's own number, not its rank: the cards are
                        ordered by score, but this is what the downloaded file
                        is called (clip-N.mp4) and what every api call indexes. */}
                    <span className="bg-black/70 text-ink font-mono text-micro uppercase px-2 py-1 rounded-full">
                        Corte {rankIndex !== undefined ? rankIndex + 1 : index + 1}
                    </span>

                </div>

                {/* Auto Edit Overlay if Processing */}
                {isEditing && (
                    <div className="absolute inset-0 bg-black/70 flex flex-col items-center justify-center z-10 p-4 text-center">
                        <Loader2 size={28} className="text-violet animate-spin mb-3" />
                        <span className="text-xs text-ink lowercase">mágica da IA em progresso…</span>
                        <span className="readout mt-1.5 text-violet font-semibold">APLICANDO CORTES VIRAIS · ZOOMS</span>
                    </div>
                )}
            </div>

            {/* Right: Content & Details */}
            <div className="flex-1 p-3.5 sm:p-4 md:p-4.5 xl:p-5 flex flex-col overflow-hidden min-w-0">
                <div className="mb-3">
                    <h3 className="text-sm sm:text-base font-semibold text-ink leading-snug line-clamp-2 mb-2 break-words" title={clip.video_title_for_youtube_short}>
                        {clip.video_title_for_youtube_short || "Clipe Viral Gerado"}
                    </h3>
                    
                    {/* Virality Score Explanation Box */}
                    <ViralHUD score={clip.predicted_score} explanation={clip.explanation} />

                    <div className="flex flex-wrap items-center gap-1.5 mb-1">
                        {durationReadout && <span className="readout bg-paper3 border border-rule px-2 py-0.5 rounded-full shrink-0 font-medium text-[10px]">{durationReadout}</span>}
                        {resolution && <span className="readout bg-paper3 border border-rule px-2 py-0.5 rounded-full shrink-0 text-[10px]">{resolution}</span>}
                        <span className="readout bg-paper3 border border-rule px-2 py-0.5 rounded-full shrink-0 text-[10px]">#shorts</span>
                        <span className="readout bg-paper3 border border-rule px-2 py-0.5 rounded-full shrink-0 text-[10px]">#viral</span>
                    </div>
                </div>

                {/* Descriptions (compact) — full text lives in the modal */}
                <div className="flex-1 min-h-0 space-y-2 mb-2.5">
                    <div className="bg-paper rounded-input px-2.5 sm:px-3 py-1.5 border border-rule flex items-center gap-2 min-w-0">
                        <span className="eyebrow shrink-0 text-[9px] sm:text-[10px] text-muted">TÍTULO YT</span>
                        <p className="text-xs text-ink2 truncate flex-1 min-w-0 font-medium">
                            {clip.video_title_for_youtube_short || "Vídeo Curto Viral"}
                        </p>
                        <button
                            onClick={() => handleCopy('youtube', clip.video_title_for_youtube_short || "Vídeo Curto Viral")}
                            aria-label="Copiar título do YouTube"
                            className="p-1 rounded-input text-muted hover:text-violet transition-colors shrink-0"
                            title="Copiar título"
                        >
                            {copied === 'youtube' ? <Check size={14} className="text-ok" /> : <Copy size={14} />}
                        </button>
                    </div>

                    <div className="bg-paper rounded-input px-2.5 sm:px-3 py-1.5 border border-rule flex items-center gap-2 min-w-0">
                        <span className="eyebrow shrink-0 text-[9px] sm:text-[10px] text-muted">LEGENDA</span>
                        <p className="text-xs text-ink2 truncate flex-1 min-w-0 font-medium">
                            {clip.video_description_for_tiktok || clip.video_description_for_instagram}
                        </p>
                        <button
                            onClick={() => handleCopy('caption', clip.video_description_for_tiktok || clip.video_description_for_instagram)}
                            aria-label="Copiar legenda"
                            className="p-1 rounded-input text-muted hover:text-violet transition-colors shrink-0"
                            title="Copiar legenda"
                        >
                            {copied === 'caption' ? <Check size={14} className="text-ok" /> : <Copy size={14} />}
                        </button>
                    </div>
                    
                    <button
                        onClick={() => setShowDescModal(true)}
                        className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-input border border-dashed border-rule text-xs text-muted hover:text-ink hover:border-rule2 hover:bg-paper3/40 transition-colors"
                    >
                        <FileText size={13} className="shrink-0" />
                        <span className="truncate">Ver Textos e Descrições</span>
                    </button>
                </div>

                {/* Error Message */}
                {editError && (
                    <div className="mb-3 px-3 py-2 rounded-input text-xs text-danger bg-danger/10 border border-danger/30 flex items-center gap-2">
                        <AlertCircle size={14} className="shrink-0" />
                        <span className="truncate">{editError}</span>
                    </div>
                )}

                {/* Actions Footer */}
                <ClipActionBar
                    onEditClip={onEditClip}
                    index={index}
                    onReframeClip={onReframeClip}
                    handleAutoEdit={handleAutoEdit}
                    isEditing={isEditing}
                    setShowSubtitleModal={setShowSubtitleModal}
                    isSubtitling={isSubtitling}
                    setShowHookModal={setShowHookModal}
                    isHooking={isHooking}
                    plan={plan}
                    setShowWatermarkModal={setShowWatermarkModal}
                    downloadClip={downloadClip}
                    downloadPct={downloadPct}
                    setShowModal={setShowModal}
                />
            </div>

            {/* Descriptions Modal */}
            <Modal
                isOpen={showDescModal}
                onClose={() => setShowDescModal(false)}
                eyebrow="TEXTOS GERADOS"
                title="Descrições & Títulos"
                size="md"
            >
                <div className="space-y-4">
                    <div>
                        <div className="flex items-center justify-between gap-2 mb-1.5">
                            <label className="eyebrow">TÍTULO DO YOUTUBE</label>
                            <button
                                onClick={() => handleCopy('youtube', clip.video_title_for_youtube_short || "Vídeo Curto Viral")}
                                aria-label="copiar título youtube"
                                className="p-1 rounded-full text-muted hover:text-violet transition-colors shrink-0"
                            >
                                {copied === 'youtube' ? <Check size={14} className="text-ok" /> : <Copy size={14} />}
                            </button>
                        </div>
                        <p className="text-sm text-ink2 select-all break-words bg-paper rounded-input p-3 border border-rule">
                            {clip.video_title_for_youtube_short || "Vídeo Curto Viral"}
                        </p>
                    </div>

                    <div>
                        <div className="flex items-center justify-between gap-2 mb-1.5">
                            <label className="eyebrow">LEGENDA TIKTOK · INSTAGRAM</label>
                            <button
                                onClick={() => handleCopy('caption', clip.video_description_for_tiktok || clip.video_description_for_instagram)}
                                aria-label="copiar legenda"
                                className="p-1 rounded-full text-muted hover:text-violet transition-colors shrink-0"
                            >
                                {copied === 'caption' ? <Check size={14} className="text-ok" /> : <Copy size={14} />}
                            </button>
                        </div>
                        <p className="text-sm text-ink2 select-all break-words bg-paper rounded-input p-3 border border-rule whitespace-pre-wrap">
                            {clip.video_description_for_tiktok || clip.video_description_for_instagram}
                        </p>
                    </div>
                </div>
            </Modal>

            {/* Post Modal */}
            <SocialPostModal
                isOpen={showModal}
                onClose={() => setShowModal(false)}
                noAccountsConnected={noAccountsConnected}
                handleConnectAccounts={handleConnectAccounts}
                submitSocialPost={submitSocialPost}
                posting={posting}
                canPost={canPost}
                isScheduling={isScheduling}
                setIsScheduling={setIsScheduling}
                postTitle={postTitle}
                setPostTitle={setPostTitle}
                postDescription={postDescription}
                setPostDescription={setPostDescription}
                scheduleDate={scheduleDate}
                setScheduleDate={setScheduleDate}
                platforms={platforms}
                setPlatforms={setPlatforms}
                platformOptions={platformOptions}
            />

            <SubtitleModal
                isOpen={showSubtitleModal}
                onClose={() => setShowSubtitleModal(false)}
                onGenerate={handleSubtitle}
                onApplyAll={onBulkSubtitle ? async (options) => {
                    await onBulkSubtitle(options);
                    setShowSubtitleModal(false);
                } : undefined}
                onRemove={handleRemoveSubtitles}
                bulkCount={clipCount}
                bulkProgress={bulkProgress}
                isProcessing={isSubtitling || (bulkProgress?.running ?? false)}
                videoUrl={originalVideoUrl}
                jobId={jobId}
                clipIndex={index}
                existingHook={activeLayers.hook}
            />

            <HookModal
                isOpen={showHookModal}
                onClose={() => setShowHookModal(false)}
                onGenerate={handleHook}
                isProcessing={isHooking}
                videoUrl={originalVideoUrl}
                initialText={clip.viral_hook_text}
                durationInSeconds={clip.end && clip.start ? clip.end - clip.start : 30}
                existingSubtitles={activeLayers.subtitles}
                hasCaptions={!!activeLayers.subtitles || /(^|_)subtitled_/.test(serverVideoFile || '')}
                serverRender={hasServerBurns}
                burnedHook={burnedHook}
                onRemove={burnedHook ? handleRemoveHook : null}
            />

            {showWatermarkModal && (
                <WatermarkModal
                    onClose={() => setShowWatermarkModal(false)}
                    onContinue={downloadClip}
                />
            )}

        </div>
    );
}
