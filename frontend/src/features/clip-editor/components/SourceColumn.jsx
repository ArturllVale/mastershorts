import React from 'react';
import ThreePointControls from './ThreePointControls';
import TranscriptPanel from './TranscriptPanel';
import { getApiUrl } from '../../../config';

export default function SourceColumn({
    edl,
    sourceRef,
    applySeek,
    setSourceTime,
    sourceTrackNode,
    markIn,
    markOut,
    markRange,
    minSeg,
    markHere,
    clearMarks,
    sendToClip,
    selected,
    segmentsLength,
    maxSegments,
    words,
    segments,
    sourceTime,
    seekSource,
    setSegment
}) {
    return (
        <div className="flex-1 min-w-0 flex flex-col min-h-0 gap-2">
            <p className="eyebrow shrink-0">Vídeo Original</p>
            {/* The black hugs the picture instead of the column: a wide
                box around a short 16:9 frame is exactly the dead space
                this layout set out to remove. */}
            <div className="flex-1 min-h-0 min-w-0 flex items-center justify-center">
                <video
                    ref={sourceRef}
                    src={getApiUrl(edl.source.url)}
                    controls
                    playsInline
                    preload="metadata"
                    onLoadedMetadata={applySeek}
                    onTimeUpdate={(e) => setSourceTime(e.target.currentTime)}
                    className="h-full w-auto max-w-full max-h-full bg-black rounded-card border border-rule"
                />
            </div>

            {sourceTrackNode}

            <ThreePointControls
                markIn={markIn}
                markOut={markOut}
                markRange={markRange}
                minSeg={minSeg}
                markHere={markHere}
                clearMarks={clearMarks}
                sendToClip={sendToClip}
                selected={selected}
                segmentsLength={segmentsLength}
                maxSegments={maxSegments}
            />

            <TranscriptPanel
                words={words}
                segments={segments}
                selected={selected}
                sourceTime={sourceTime}
                seekSource={seekSource}
                setSegment={setSegment}
            />
        </div>
    );
}
