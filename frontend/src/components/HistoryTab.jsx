import React, { useState, useEffect, useMemo } from 'react';
import { Loader2, Download, Film, FolderOpen } from 'lucide-react';
import { apiJson } from '../lib/api';
import EmptyState from './ui/EmptyState';
import Button from './ui/Button';

// The signed-in user's saved video library (stored in R2). Private, signed links.
// Videos are grouped by project (job); re-openable projects get a "reopen"
// action that restores the whole job for further editing in the Clip Generator.
export default function HistoryTab({ onReopenProject }) {
  const [videos, setVideos] = useState(null);
  const [projects, setProjects] = useState({});
  const [reopening, setReopening] = useState(null);
  const [reopenError, setReopenError] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    apiJson('/api/history')
      .then((d) => setVideos(d.videos || []))
      .catch(() => setError('Could not load your library.'));
    apiJson('/api/projects')
      .then((d) => {
        const map = {};
        for (const p of d.projects || []) map[p.job_id] = p;
        setProjects(map);
      })
      .catch(() => {});
  }, []);

  // Group videos by job, preserving the newest-first order of /api/history.
  const groups = useMemo(() => {
    const byJob = new Map();
    for (const v of videos || []) {
      const key = v.job_id || v.id;
      if (!byJob.has(key)) byJob.set(key, []);
      byJob.get(key).push(v);
    }
    return [...byJob.entries()];
  }, [videos]);

  const handleReopen = async (jobId) => {
    if (!onReopenProject || reopening) return;
    setReopening(jobId);
    setReopenError('');
    try {
      await onReopenProject(jobId);
    } catch (e) {
      setReopenError('Could not reopen this project. Please try again.');
      setReopening(null);
    }
  };

  const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '');

  if (videos === null && !error) {
    return <div className="flex justify-center py-20"><Loader2 className="animate-spin text-accent" /></div>;
  }

  return (
    <div className="h-full overflow-y-auto p-6 md:p-8 max-w-5xl mx-auto animate-fade">
      <p className="eyebrow mb-1.5">06 · HISTORY</p>
      <h1 className="font-display text-2xl md:text-3xl text-text-primary tracking-tight mb-2">Your Library</h1>
      <p className="text-text-secondary text-sm mb-8 leading-relaxed">
        All the shorts you've generated, saved while your plan is active. Kept for 7 days after your plan ends. Reopen a project to keep editing its clips.
      </p>

      {error && <p className="text-danger text-sm mb-4">{error}</p>}
      {reopenError && <p className="text-danger text-sm mb-4">{reopenError}</p>}

      {videos && videos.length === 0 && (
        <EmptyState
          icon={Film}
          title="No videos generated yet"
          description="Generate your first short from the Clip Generator to start building your video library."
        />
      )}

      <div className="space-y-10">
        {groups.map(([jobId, vids]) => {
          const project = projects[jobId];
          return (
            <section key={jobId} className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-border">
                <div className="min-w-0">
                  <p className="text-sm text-text-primary font-medium truncate" title={project?.title || vids[0]?.title}>
                    {project?.title || vids[0]?.title || 'Project'}
                  </p>
                  <p className="font-mono text-xs text-text-tertiary mt-0.5">
                    {fmtDate(vids[0]?.created_at)} · {vids.length} clip{vids.length === 1 ? '' : 's'}
                  </p>
                </div>
                {project && onReopenProject && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleReopen(jobId)}
                    disabled={!!reopening}
                    isLoading={reopening === jobId}
                    leftIcon={!reopening && <FolderOpen size={14} />}
                    title="Restore this project in the Clip Generator to keep editing subtitles, hooks, effects and dubbing"
                  >
                    {reopening === jobId ? 'Reopening…' : 'Reopen Project'}
                  </Button>
                )}
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                {vids.map((v) => (
                  <div key={v.id} className="card card-hover overflow-hidden group flex flex-col">
                    <div className="aspect-[9/16] bg-surface-1">
                      <video src={v.view_url} controls preload="metadata" className="w-full h-full object-contain" />
                    </div>
                    <div className="p-3 flex-1 flex flex-col justify-between">
                      <p className="text-xs text-text-primary font-medium line-clamp-2 mb-2" title={v.title}>{v.title || 'Short'}</p>
                      <div className="flex items-center justify-between pt-2 border-t border-border/50">
                        <span className="font-mono text-[10px] text-text-tertiary">{fmtDate(v.created_at)}</span>
                        <a
                          href={v.download_url}
                          className="font-mono text-[11px] text-accent hover:text-text-primary flex items-center gap-1 transition-colors"
                          title="Download"
                        >
                          <Download size={12} /> MP4
                        </a>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
