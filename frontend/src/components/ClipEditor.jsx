import React, { useState, useEffect, useReducer, useRef, useCallback, useMemo, useDeferredValue } from 'react';
import {
    X, Loader2, Plus, Trash2, ChevronUp, ChevronDown, Scissors,
    AlertCircle, Undo2, Redo2, ChevronsRight, ChevronsLeft,
    PanelLeft, PanelLeftClose, Film,
} from 'lucide-react';
import { getApiUrl } from '../config';
import { QuotaError } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import { fmt, totalOf } from '../lib/clipUtils';
import { fetchEDL, rerenderClip } from '../services/clipService';

// Full-screen clip editor: shows WHICH source segments a clip was cut from,
// lets the user trim/extend/split/reorder them (word-snapped), and re-renders
// through POST /api/clip/rerender. The recipe (EDL) comes from GET .../edl.

const MIN_SEGMENT_SECONDS = 0.5;
const SNAP_WINDOW_SECONDS = 0.35;

// Hiding the source is a working preference, not a per-clip one, so it sticks.
const HIDE_SOURCE_KEY = 'os_editor_hide_source';

// Words per memoised transcript slice. See TranscriptChunk for why this exists.
const CHUNK_WORDS = 50;

// Segment edges round-trip through 3 decimals, so coverage arithmetic needs a
// hair of tolerance before it calls a millisecond sliver "not rendered".
const COVERAGE_EPSILON = 0.02;

const SEGMENT_COLORS = [
    'oklch(76% .17 50)',   // brass
    'oklch(70% .12 200)',
    'oklch(72% .13 140)',
    'oklch(70% .14 300)',
    'oklch(74% .13 90)',
    'oklch(68% .13 250)',
];

import { useEditorShortcuts } from '../hooks/useEditorShortcuts';
import { useVideoSeek } from '../hooks/useVideoSeek';
import { useDragSegment } from '../hooks/useDragSegment';
import { useEditorTimeline } from '../features/clip-editor/hooks/useEditorTimeline';
import { useSegmentMutations } from '../features/clip-editor/hooks/useSegmentMutations';
import { useClipScrub } from '../features/clip-editor/hooks/useClipScrub';
import { useThreePointEditing } from '../features/clip-editor/hooks/useThreePointEditing';
import { useClipData } from '../features/clip-editor/hooks/useClipData';
import TranscriptChunk from '../features/clip-editor/TranscriptChunk';
import SegmentRow from '../features/clip-editor/SegmentRow';
import EditorHeader from '../features/clip-editor/components/EditorHeader';
import EditorFooter from '../features/clip-editor/components/EditorFooter';
import SidebarControls from '../features/clip-editor/components/SidebarControls';
import SourceColumn from '../features/clip-editor/components/SourceColumn';
import PreviewColumn from '../features/clip-editor/components/PreviewColumn';
import SourceTrack from '../features/clip-editor/components/SourceTrack';
import ClipTrack from '../features/clip-editor/components/ClipTrack';

import editorReducer from '../features/clip-editor/editorReducer';

export default function ClipEditor({ jobId, clipIndex, clipTitle, onClose, onRerendered }) {
    const { refreshMe } = useAuth();
    const [state, dispatch] = useReducer(editorReducer, { segments: [], selected: 0, past: [], future: [], pendingBase: null });
    const { segments, selected } = state;

    const [snapToWords, setSnapToWords] = useState(true);
    const [reapplyCaptions, setReapplyCaptions] = useState(true);
    // Framing override: 'auto' (classifier) | 'full' (whole frame) | 'track'.
    const [framing, setFraming] = useState('auto');

    const {
        edl,
        loadError,
        renderedFraming,
        renderedSegments,
        previewUrl,
        rendering,
        renderSeconds,
        renderError,
        doRender: doRenderApi
    } = useClipData({
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
    });
    const [confirmClose, setConfirmClose] = useState(false);
    const [playhead, setPlayhead] = useState(0);
    const [showSource, setShowSource] = useState(() => {
        try { return localStorage.getItem(HIDE_SOURCE_KEY) !== '1'; } catch { return true; }
    });
    // Where the source monitor's playhead is, for the transcript to follow.
    const [sourceTime, setSourceTime] = useState(0);
    // Three-point editing, like a Premiere source monitor: mark IN and OUT on
    // the source, then send that range to the clip. Kept as two independent
    // numbers rather than a range so either end can be re-marked on its own.


    const videoRef = useRef(null);
    const sourceRef = useRef(null);
    const clipTrackRef = useRef(null);
    const sourceTrackRef = useRef(null);
    const dragRef = useRef(null);
    const [ghost, setGhost] = useState(null); // in-progress new segment on the source track

    useEffect(() => {
        try { localStorage.setItem(HIDE_SOURCE_KEY, showSource ? '0' : '1'); } catch { /* private mode */ }
    }, [showSource]);

    // ---- scrubbing the source monitor ---------------------------------------
    // Dragging on the source track drives this <video>, so the cut is chosen
    // against the picture instead of against numbers. rAF-throttled: a drag
    // fires dozens of pointermoves a second and assigning currentTime on each
    // one makes the element stutter. `pending` also survives a seek issued
    // before the metadata is in, which onLoadedMetadata then applies.
    const seekRef = useRef({ pending: null, raf: 0, timer: 0 });

    const applySeek = useCallback(() => {
        if (seekRef.current.raf) cancelAnimationFrame(seekRef.current.raf);
        if (seekRef.current.timer) clearTimeout(seekRef.current.timer);
        seekRef.current.raf = 0;
        seekRef.current.timer = 0;
        const v = sourceRef.current;
        const t = seekRef.current.pending;
        if (!v || t === null) return;
        if (v.readyState === 0) return;          // retried from onLoadedMetadata
        if (!v.paused) v.pause();                // a moving picture cannot be aimed
        try { v.currentTime = Math.max(0, t); } catch { /* seek refused, keep pending */ }
        seekRef.current.pending = null;
    }, []);

    const seekSource = useCallback((t) => {
        if (!Number.isFinite(t)) return;
        seekRef.current.pending = t;
        if (seekRef.current.raf || seekRef.current.timer) return;   // one per frame
        seekRef.current.raf = requestAnimationFrame(applySeek);
        // The timer is the recovery path, not a second throttle: a hidden or
        // occluded tab never runs a rAF callback, so a latch waiting only on
        // rAF would deadlock the scrub for the rest of the session. Whichever
        // fires first cancels the other.
        seekRef.current.timer = setTimeout(applySeek, 120);
    }, [applySeek]);

    useEffect(() => () => {
        if (seekRef.current.raf) cancelAnimationFrame(seekRef.current.raf);
        if (seekRef.current.timer) clearTimeout(seekRef.current.timer);
    }, []);



    const words = useMemo(() => (edl?.words || []), [edl]);
    const sourceAvailable = !!edl?.source?.available;
    const sourceDuration = edl?.source?.duration || 0;
    const canonical = useMemo(() => edl?.canonical_range || { start: 0, end: 0 }, [edl]);
    const limits = edl?.limits || { max_segments: 12, min_segment_seconds: MIN_SEGMENT_SECONDS, max_total_seconds: 180 };
    const minSeg = limits.min_segment_seconds || MIN_SEGMENT_SECONDS;

    // The source panel is on screen only when there IS a source and the user
    // has not put it away. An expired source forces the same two-column layout
    // the hide button asks for, so both cases share one code path.
    const sourceOpen = sourceAvailable && showSource;

    const total = totalOf(segments);
    const dirty = useMemo(() => {
        if (!renderedSegments) return false;
        return JSON.stringify(segments) !== JSON.stringify(renderedSegments)
            || framing !== renderedFraming;
    }, [segments, renderedSegments, framing, renderedFraming]);

    // Trim bounds: with the source gone, cuts must stay inside the range the
    // canonical file was rendered from.
    const bounds = sourceAvailable
        ? { lo: 0, hi: sourceDuration || Infinity }
        : { lo: canonical.start, hi: canonical.end };

    const outOfRange = useCallback(
        (seg) => !sourceAvailable && (seg.start < canonical.start - 0.05 || seg.end > canonical.end + 0.05),
        [sourceAvailable, canonical],
    );
    const needsSourcePath = framing !== 'auto'
        || segments.some((s) => s.start < canonical.start - 0.05 || s.end > canonical.end + 0.05);
    const invalidSegments = segments.some(outOfRange);
    const overCaps = segments.length > limits.max_segments || total > limits.max_total_seconds;
    const canRender = !rendering && segments.length > 0 && !invalidSegments && !overCaps
        && segments.every((s) => s.end - s.start >= minSeg)
        && (framing === 'auto' || sourceAvailable);

    const doRender = useCallback(() => {
        if (canRender) doRenderApi();
    }, [canRender, doRenderApi]);

    // ---- helpers ------------------------------------------------------------
    const {
        snapEdge,
        clampSeg,
        setSegment,
        addSegment,
        deleteSegment,
        moveSegment,
        splitSegment
    } = useSegmentMutations({
        segments,
        dispatch,
        bounds,
        minSeg,
        limits,
        words,
        snapToWords,
        playhead
    });



    const { startTrimDrag, startGhostDrag } = useDragSegment({
        dragRef,
        segments,
        dispatch,
        bounds,
        minSeg,
        snapEdge,
        seekSource,
        setGhost,
        setMarkIn,
        setMarkOut,
        sourceAvailable,
        sourceDuration,
        sourceTrackRef
    });

    // ---- what of this edit the rendered file can already show ---------------
    // The rendered file IS renderedSegments cut and concatenated in order (see
    // perform_recut), so any instant of source still inside one of those ranges
    // exists in the file and can be played straight from it. That is why a cut
    // that only REMOVES material stays previewable: every frame it keeps was
    // already rendered. Only material the last render never saw is missing, and
    // that is what turns red.
    const {
        coverage,
        missingSeconds,
        spanIndexAt,
        clipToRendered,
        renderedToClip,
        hasCovered,
        clampToCovered,
        clipToSource
    } = useEditorTimeline({
        segments,
        renderedSegments,
        framing,
        renderedFraming
    });

    // An edit can leave the handle standing where the file no longer reaches.
    useEffect(() => {
        setPlayhead((t) => {
            const clamped = clampToCovered(t, t);
            return clamped === t ? t : clamped;
        });
    }, [clampToCovered]);

    const {
        playSpanRef,
        onClipTimeUpdate,
        stopPlayLoop,
        onClipSeeked,
        onClipPlay
    } = useVideoSeek({
        coverage,
        dirty,
        segments,
        setPlayhead,
        videoRef,
        totalOf,
        renderedToClip,
        spanIndexAt
    });

    const { startClipScrub } = useClipScrub({
        dragRef,
        clipTrackRef,
        clipTrackSeconds,
        total,
        playhead,
        clampToCovered,
        setPlayhead,
        clipToRendered,
        spanIndexAt,
        playSpanRef,
        videoRef,
        seekSource,
        clipToSource,
        sourceOpen
    });

    const {
        markIn,
        setMarkIn,
        markOut,
        setMarkOut,
        markHere,
        clearMarks,
        markRange,
        sendToClip
    } = useThreePointEditing({
        sourceRef,
        minSeg,
        selected,
        segments,
        limits,
        dispatch
    });

    // ---- keyboard -----------------------------------------------------------
    useEditorShortcuts({
        onClose,
        rendering,
        dirty,
        setConfirmClose,
        dispatch,
        videoRef,
        deleteSegment,
        selected,
        splitSegment,
        sourceOpen,
        markHere,
        sendToClip
    });





    // ---- render -------------------------------------------------------------
    if (loadError) {
        return (
            <div className="fixed inset-0 z-[110] bg-black/70 flex items-center justify-center p-4 animate-fade" onMouseDown={onClose}>
                <div className="card p-6 max-w-md" onMouseDown={(e) => e.stopPropagation()}>
                    <p className="eyebrow mb-2">EDITOR · CLIP {clipIndex + 1}</p>
                    <div className="flex items-center gap-2 text-danger text-sm"><AlertCircle size={16} /> {loadError}</div>
                    <button className="btn-ghost mt-5" onClick={onClose}>close</button>
                </div>
            </div>
        );
    }

    if (!edl) {
        return (
            <div className="fixed inset-0 z-[110] bg-paper/90 flex items-center justify-center animate-fade">
                <div className="flex items-center gap-3 text-muted text-sm lowercase">
                    <Loader2 size={18} className="animate-spin text-brass" /> loading clip recipe…
                </div>
            </div>
        );
    }

    // The track's scale is the RENDERED length (or the current total, whichever
    // is longer), not the current total: normalising to the total made a
    // single-segment clip fill 100% of the track no matter how it was trimmed,
    // so dragging its handle visibly moved nothing (issue #73). Against the
    // rendered length, shortening the clip shortens the bar.
    const clipTrackSeconds = Math.max(total, totalOf(renderedSegments || []), 0.001);
    let runningOffset = 0;
    const blocks = segments.map((s, i) => {
        const left = (runningOffset / clipTrackSeconds) * 100;
        const width = ((s.end - s.start) / clipTrackSeconds) * 100;
        runningOffset += s.end - s.start;
        return { seg: s, i, left, width };
    });

    // The source track lives under the source monitor. With no source at all
    // there is no monitor to sit under, so it moves below the clip track: it
    // still explains why trims are pinned to the original range.
    const sourceTrack = (
        <SourceTrack
            sourceDuration={sourceDuration}
            edl={edl}
            sourceAvailable={sourceAvailable}
            sourceTrackRef={sourceTrackRef}
            startGhostDrag={startGhostDrag}
            canonical={canonical}
            segments={segments}
            selected={selected}
            startTrimDrag={startTrimDrag}
            markRange={markRange}
            ghost={ghost}
            markIn={markIn}
            markOut={markOut}
            sourceOpen={sourceOpen}
            sourceTime={sourceTime}
        />
    );

    return (
        <div className="fixed inset-0 z-[110] bg-paper flex flex-col animate-fade">
            {/* header */}
            <EditorHeader
                clipIndex={clipIndex}
                clipTitle={clipTitle}
                total={total}
                needsSourcePath={needsSourcePath}
                edl={edl}
                sourceAvailable={sourceAvailable}
                showSource={showSource}
                setShowSource={setShowSource}
                confirmClose={confirmClose}
                setConfirmClose={setConfirmClose}
                rendering={rendering}
                dirty={dirty}
                onClose={onClose}
            />

            {/* main — three columns above xl, stacked below. select-none/touch-none
                keep the browser from turning a drag on a track into a text
                selection or a page pan. */}
            <div className="flex-1 min-h-0 flex flex-col xl:flex-row gap-4 px-4 sm:px-6 py-4 overflow-y-auto xl:overflow-hidden select-none">

                {/* ---- column 1 · source ---- */}
                {sourceOpen && (
                    <SourceColumn
                        edl={edl}
                        sourceRef={sourceRef}
                        applySeek={applySeek}
                        setSourceTime={setSourceTime}
                        sourceTrackNode={sourceTrack}
                        markIn={markIn}
                        markOut={markOut}
                        markRange={markRange}
                        minSeg={minSeg}
                        markHere={markHere}
                        clearMarks={clearMarks}
                        sendToClip={sendToClip}
                        selected={selected}
                        segmentsLength={segments.length}
                        maxSegments={limits.max_segments}
                        words={words}
                        segments={segments}
                        sourceTime={sourceTime}
                        seekSource={seekSource}
                        setSegment={setSegment}
                    />
                )}

                {/* ---- column 2 · program ---- */}
                <PreviewColumn
                    sourceOpen={sourceOpen}
                    dirty={dirty}
                    missingSeconds={missingSeconds}
                    previewUrl={previewUrl}
                    videoRef={videoRef}
                    onClipTimeUpdate={onClipTimeUpdate}
                    onClipSeeked={onClipSeeked}
                    onClipPlay={onClipPlay}
                    stopPlayLoop={stopPlayLoop}
                    sourceAvailable={sourceAvailable}
                    sourceTrackNode={sourceTrack}
                    clipTrackNode={
                        <ClipTrack
                            total={total}
                            dirty={dirty}
                            missingSeconds={missingSeconds}
                            clipTrackRef={clipTrackRef}
                            startClipScrub={startClipScrub}
                            blocks={blocks}
                            dispatch={dispatch}
                            selected={selected}
                            outOfRange={outOfRange}
                            startTrimDrag={startTrimDrag}
                            clipTrackSeconds={clipTrackSeconds}
                            coverage={coverage}
                            playhead={playhead}
                        />
                    }
                />

                {/* ---- column 3 · controls ---- */}
                <SidebarControls
                    segments={segments}
                    selected={selected}
                    statePastLength={state.past.length}
                    stateFutureLength={state.future.length}
                    limits={limits}
                    dispatch={dispatch}
                    setSegment={setSegment}
                    sourceOpen={sourceOpen}
                    seekSource={seekSource}
                    moveSegment={moveSegment}
                    splitSegment={splitSegment}
                    deleteSegment={deleteSegment}
                    minSeg={minSeg}
                    addSegment={addSegment}
                    sourceAvailable={sourceAvailable}
                    framing={framing}
                    setFraming={setFraming}
                    renderedFraming={renderedFraming}
                    snapToWords={snapToWords}
                    setSnapToWords={setSnapToWords}
                    reapplyCaptions={reapplyCaptions}
                    setReapplyCaptions={setReapplyCaptions}
                    outOfRange={outOfRange}
                    footerNode={
                        <EditorFooter
                            renderError={renderError}
                            overCaps={overCaps}
                            total={total}
                            limits={limits}
                            canRender={canRender}
                            dirty={dirty}
                            doRender={doRender}
                            rendering={rendering}
                            renderSeconds={renderSeconds}
                            needsSourcePath={needsSourcePath}
                            onClose={onClose}
                            setConfirmClose={setConfirmClose}
                        />
                    }
                />
            </div>
        </div>
    );
}
