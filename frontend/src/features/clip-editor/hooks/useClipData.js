import { useState, useEffect } from 'react';
import { fetchEDL, rerenderClip } from '../../../services/clipService';
import { QuotaError } from '../../../lib/api';
import { getApiUrl } from '../../../config';

export function useClipData({
    jobId,
    clipIndex,
    dispatch,
    refreshMe,
    onRerendered,
    segments,
    framing,
    reapplyCaptions,
    setFraming,
    setReapplyCaptions
}) {
    const [edl, setEdl] = useState(null);
    const [loadError, setLoadError] = useState(null);
    const [renderedFraming, setRenderedFraming] = useState('auto');
    const [renderedSegments, setRenderedSegments] = useState(null);
    const [previewUrl, setPreviewUrl] = useState(null);
    const [rendering, setRendering] = useState(false);
    const [renderSeconds, setRenderSeconds] = useState(0);
    const [renderError, setRenderError] = useState(null);

    // ---- load the EDL -------------------------------------------------------
    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const data = await fetchEDL(jobId, clipIndex);
                if (cancelled) return;
                setEdl(data);
                dispatch({ type: 'init', segments: data.segments.map((s) => ({ ...s })) });
                setRenderedSegments(data.segments.map((s) => ({ ...s })));
                setFraming(data.framing || 'auto');
                setRenderedFraming(data.framing || 'auto');
                setReapplyCaptions(true);
                setPreviewUrl(getApiUrl(`/videos/${jobId}/${data.current_file}`));
            } catch (e) {
                if (!cancelled) setLoadError(e.detail || e.message || 'could not load the clip recipe');
            }
        })();
        return () => { cancelled = true; };
    }, [jobId, clipIndex, dispatch, setFraming, setReapplyCaptions]);

    // ---- re-render timer ----------------------------------------------------
    useEffect(() => {
        if (!rendering) return undefined;
        setRenderSeconds(0);
        const t = setInterval(() => setRenderSeconds((s) => s + 1), 1000);
        return () => clearInterval(t);
    }, [rendering]);

    const doRender = async () => {
        setRendering(true);
        setRenderError(null);
        try {
            const data = await rerenderClip({
                jobId,
                clipIndex,
                segments: segments.map((s) => ({ start: s.start, end: s.end })),
                reapply_captions: reapplyCaptions,
                framing,
            });
            setRenderedSegments(data.recipe.segments.map((s) => ({ ...s })));
            setRenderedFraming(data.framing || 'auto');
            setFraming(data.framing || 'auto');
            dispatch({ type: 'init', segments: data.recipe.segments.map((s) => ({ ...s })) });
            setPreviewUrl(`${getApiUrl(data.new_video_url)}?t=${Date.now()}`);
            onRerendered?.(clipIndex, data);
            refreshMe();
        } catch (e) {
            if (e instanceof QuotaError) {
                refreshMe();
                setRenderError(`not enough minutes left (needs ${e.minutesRequired ?? '?'}, ${e.minutesRemaining ?? 0} remaining)`);
            } else {
                setRenderError(e.message || 're-render failed');
            }
        } finally {
            setRendering(false);
        }
    };

    return {
        edl,
        loadError,
        renderedFraming,
        renderedSegments,
        previewUrl,
        rendering,
        renderSeconds,
        renderError,
        doRender
    };
}
