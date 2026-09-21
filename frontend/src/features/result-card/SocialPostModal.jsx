import React from 'react';
import { Share2, Link2, AlertCircle, Loader2, Calendar } from 'lucide-react';
import Modal from '../../components/ui/Modal';
import SegmentedControl from '../../components/ui/SegmentedControl';

export default function SocialPostModal({
    isOpen,
    onClose,
    noAccountsConnected,
    handleConnectAccounts,
    submitSocialPost,
    posting,
    canPost,
    isScheduling,
    setIsScheduling,
    postTitle,
    setPostTitle,
    postDescription,
    setPostDescription,
    scheduleDate,
    setScheduleDate,
    platforms,
    setPlatforms,
    platformOptions
}) {
    return (
        <Modal
            isOpen={isOpen}
            onClose={onClose}
            eyebrow="PUBLICAR"
            title="publicar corte"
            size="md"
            footer={
                noAccountsConnected ? (
                    <button onClick={handleConnectAccounts} className="btn-primary w-full">
                        <Link2 size={16} /> conectar contas
                    </button>
                ) : (
                    <button
                        onClick={submitSocialPost}
                        disabled={posting || !canPost}
                        className="btn-primary w-full"
                    >
                        {posting ? <><Loader2 size={16} className="animate-spin" /> {isScheduling ? 'agendando…' : 'publicando…'}</> : <><Share2 size={16} /> {isScheduling ? 'agendar publicação' : 'publicar agora'}</>}
                    </button>
                )
            }
        >
            {!canPost && (
                <div className="mb-4 px-3 py-2 rounded-input text-xs text-warn bg-[color-mix(in_oklab,var(--color-warn)_10%,transparent)] flex items-start gap-2">
                    <AlertCircle size={14} className="mt-0.5 shrink-0" />
                    <div className="lowercase">configure a chave de api nas configurações primeiro.</div>
                </div>
            )}

            {noAccountsConnected && (
                <div className="mb-4 px-3 py-2 rounded-input text-xs text-warn bg-[color-mix(in_oklab,var(--color-warn)_10%,transparent)] flex items-start gap-2">
                    <AlertCircle size={14} className="mt-0.5 shrink-0" />
                    <div className="lowercase">nenhuma conta social conectada — vincule tiktok, instagram ou youtube para publicar este corte.</div>
                </div>
            )}

            <div className="space-y-4">
                {/* Title & Description */}
                <div>
                    <label className="eyebrow block mb-1.5">TÍTULO</label>
                    <input
                        type="text"
                        value={postTitle}
                        onChange={(e) => setPostTitle(e.target.value)}
                        className="input-field"
                        placeholder="digite um título chamativo…"
                    />
                </div>

                <div>
                    <label className="eyebrow block mb-1.5">LEGENDA / DESCRIÇÃO</label>
                    <textarea
                        value={postDescription}
                        onChange={(e) => setPostDescription(e.target.value)}
                        rows={4}
                        className="input-field resize-none"
                        placeholder="escreva uma legenda para o seu post…"
                    />
                </div>

                {/* Scheduling */}
                <div className="p-3 bg-paper rounded-input border border-rule">
                    <label className="flex items-center justify-between cursor-pointer">
                        <span className="flex items-center gap-2 text-sm text-ink2 lowercase">
                            <Calendar size={16} className={isScheduling ? 'text-brass' : 'text-muted'} /> agendar publicação
                        </span>
                        <input
                            type="checkbox"
                            checked={isScheduling}
                            onChange={(e) => setIsScheduling(e.target.checked)}
                            className="w-4 h-4 accent-brass cursor-pointer"
                        />
                    </label>

                    {isScheduling && (
                        <div className="mt-3 animate-fade">
                            <label className="eyebrow block mb-1.5">DATA · HORA</label>
                            <input
                                type="datetime-local"
                                value={scheduleDate}
                                onChange={(e) => setScheduleDate(e.target.value)}
                                className="input-field [color-scheme:dark]"
                            />
                        </div>
                    )}
                </div>

                {/* Platforms */}
                <div>
                    <label className="eyebrow block mb-1.5">REDES SOCIAIS</label>
                    <SegmentedControl
                        options={platformOptions}
                        value={
                            Object.keys(platforms).filter((k) => platforms[k]).length === 3 ? 'all' :
                            Object.keys(platforms).filter((k) => platforms[k]).length === 1 ? Object.keys(platforms).find((k) => platforms[k]) :
                            'custom'
                        }
                        onChange={(val) => {
                            if (val === 'all') setPlatforms({ tiktok: true, instagram: true, youtube: true });
                            else {
                                setPlatforms({
                                    tiktok: val === 'tiktok',
                                    instagram: val === 'instagram',
                                    youtube: val === 'youtube'
                                });
                            }
                        }}
                    />
                </div>
            </div>
        </Modal>
    );
}
