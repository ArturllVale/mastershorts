import React from 'react';
import { fmt } from '../../../lib/clipUtils';

const COVERAGE_EPSILON = 0.02;

export default function PreviewColumn({
    sourceOpen,
    dirty,
    missingSeconds,
    previewUrl,
    videoRef,
    onClipTimeUpdate,
    onClipSeeked,
    onClipPlay,
    stopPlayLoop,
    clipTrackNode,
    sourceAvailable,
    sourceTrackNode
}) {
    return (
        <div className={`flex flex-col min-h-0 gap-2 ${sourceOpen ? 'xl:w-[26rem] 2xl:w-[30rem] xl:shrink-0' : 'flex-1'}`}>
            <div className="flex items-center justify-between gap-2 shrink-0">
                <p className="eyebrow">Prévia do Corte</p>
                {dirty && (
                    <span className="badge-warn">
                        {missingSeconds > COVERAGE_EPSILON
                            ? `${fmt(missingSeconds)} precisa ser renderizado`
                            : 'prévia da edição · renderize para salvar'}
                    </span>
                )}
            </div>
            <div className="flex-1 min-h-0 flex items-center justify-center">
                <div className="h-full max-h-full aspect-[9/16] bg-black rounded-card border border-rule overflow-hidden">
                    <video
                        ref={videoRef}
                        src={previewUrl}
                        controls
                        playsInline
                        className="w-full h-full object-contain"
                        onTimeUpdate={onClipTimeUpdate}
                        onSeeked={onClipSeeked}
                        onPlay={onClipPlay}
                        onPause={stopPlayLoop}
                    />
                </div>
            </div>

            {clipTrackNode}

            {!sourceAvailable && sourceTrackNode}
        </div>
    );
}
