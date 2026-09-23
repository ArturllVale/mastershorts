import React, { useState, useEffect, useMemo } from 'react';
import { Loader2, Download, Film, FolderOpen, Trash2 } from 'lucide-react';
import { apiJson } from '../lib/api';
import { deleteJob } from '../services/jobService';
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
      .catch(() => setError('Não foi possível carregar sua biblioteca.'));
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
      setReopenError('Não foi possível reabrir este projeto. Tente novamente.');
      setReopening(null);
    }
  };

  const [deletingId, setDeletingId] = useState(null);

  const handleDelete = async (jobId) => {
    if (!window.confirm('Tem certeza de que deseja excluir permanentemente este projeto da sua biblioteca?')) return;
    setDeletingId(jobId);
    try {
      await deleteJob(jobId);
      setVideos((prev) => (prev || []).filter((v) => (v.job_id || v.id) !== jobId));
      setProjects((prev) => {
        const next = { ...prev };
        delete next[jobId];
        return next;
      });
    } catch (e) {
      alert(`Falha ao excluir projeto: ${e.message}`);
    } finally {
      setDeletingId(null);
    }
  };

  const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '');

  if (videos === null && !error) {
    return <div className="flex justify-center py-20"><Loader2 className="animate-spin text-accent" /></div>;
  }

  return (
    <div className="h-full overflow-y-auto p-6 md:p-8 max-w-5xl mx-auto animate-fade">
      <p className="eyebrow mb-1.5">06 · HISTÓRICO</p>
      <h1 className="font-display text-2xl md:text-3xl text-text-primary tracking-tight mb-2">Sua Biblioteca</h1>
      <p className="text-text-secondary text-sm mb-8 leading-relaxed">
        Todos os shorts que você gerou, salvos enquanto seu plano estiver ativo. Mantidos por 7 dias após o término do plano. Reabra um projeto para continuar editando seus cortes.
      </p>

      {error && <p className="text-danger text-sm mb-4">{error}</p>}
      {reopenError && <p className="text-danger text-sm mb-4">{reopenError}</p>}

      {videos && videos.length === 0 && (
        <EmptyState
          icon={Film}
          title="Nenhum vídeo gerado ainda"
          description="Gere seu primeiro corte a partir do Gerador de Cortes para começar a construir sua biblioteca de vídeos."
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
                    {project?.title || vids[0]?.title || 'Projeto'}
                  </p>
                  <p className="font-mono text-xs text-text-tertiary mt-0.5">
                    {fmtDate(vids[0]?.created_at)} · {vids.length} corte{vids.length === 1 ? '' : 's'}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {project && onReopenProject && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleReopen(jobId)}
                      disabled={!!reopening}
                      isLoading={reopening === jobId}
                      leftIcon={!reopening && <FolderOpen size={14} />}
                      title="Restaura este projeto no Gerador de Cortes para continuar editando legendas, ganchos e efeitos"
                    >
                      {reopening === jobId ? 'Reabrindo…' : 'Reabrir Projeto'}
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-danger hover:bg-danger/10 hover:text-danger px-2.5"
                    onClick={() => handleDelete(jobId)}
                    disabled={deletingId === jobId}
                    isLoading={deletingId === jobId}
                    leftIcon={deletingId !== jobId && <Trash2 size={14} />}
                    title="Excluir este projeto permanentemente"
                  >
                    {deletingId === jobId ? 'Excluindo…' : 'Excluir'}
                  </Button>
                </div>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                {vids.map((v) => (
                  <div key={v.id} className="card card-hover overflow-hidden group flex flex-col">
                    <div className="aspect-[9/16] bg-surface-1">
                      <video src={v.view_url} controls preload="metadata" className="w-full h-full object-contain" />
                    </div>
                    <div className="p-3 flex-1 flex flex-col justify-between">
                      <p className="text-xs text-text-primary font-medium line-clamp-2 mb-2" title={v.title}>{v.title || 'Corte'}</p>
                      <div className="flex items-center justify-between pt-2 border-t border-border/50">
                        <span className="font-mono text-[10px] text-text-tertiary">{fmtDate(v.created_at)}</span>
                        <a
                          href={v.download_url}
                          className="font-mono text-[11px] text-accent hover:text-text-primary flex items-center gap-1 transition-colors"
                          title="Baixar"
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
