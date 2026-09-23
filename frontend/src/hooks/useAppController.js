import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { track } from '../lib/analytics';
import { submitJob, pollJobStatus, downloadAllClips, retryJob, deleteJob } from '../services/jobService';
import { restoreProject as restoreProjectApi, fetchDurableMap } from '../services/projectService';
import { applySubtitles } from '../services/clipService';
import { useAuth } from '../contexts/AuthContext';
import { useBilling } from '../hooks/useBilling';
import { useProjectSync } from '../hooks/useProjectSync';
import { usePendingJob } from '../hooks/usePendingJob';
import { useDurableClips } from '../hooks/useDurableClips';
import { useJobPolling } from '../hooks/useJobPolling';
import { useClipTutorial } from '../hooks/useClipTutorial';
import { QuotaError } from '../lib/api';
import { fetchUserProfiles as fetchUserProfilesService } from '../services/socialService';
import { useApiKeys } from '../hooks/useApiKeys';

const SESSION_KEY = 'Master Shorts_session';
const SESSION_MAX_AGE = 86400000; // 24 hours

export function useAppController() {
  const { billingEnabled, isManaged, isSignedIn, me, plan, refreshMe, localLlm } = useAuth();
  const { setShowLogin, setShowTopUp, setShowPlanChoice, setShowTrialUpgrade, setTopUpInfo } = useBilling();
  const [tutorialPhase, setTutorialPhase] = useState(null); 
  const [partialJob, setPartialJob] = useState(null);
  const [durableClips, setDurableClips] = useState({});

  const {
    apiKey, setApiKey,
    llmProvider, setLlmProvider,
    llmBaseUrl, setLlmBaseUrl,
    llmModel, setLlmModel,
    llmApiKey, setLlmApiKey,
    llmFallbackModels, setLlmFallbackModels,
    openrouterApiKey, setOpenrouterApiKey,
    mistralApiKey, setMistralApiKey,
    uploadPostKey, setUploadPostKey, saveUploadPostKey,
    falKey, setFalKey, saveFalKey
  } = useApiKeys();
  const { stashPendingJob, peekPendingJob, popPendingJob } = usePendingJob();

  const [showKeyModal, setShowKeyModal] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState('idle'); 
  const [results, setResults] = useState(null);

  const rankedClips = useMemo(() => {
    const clips = results?.clips;
    if (!Array.isArray(clips)) return [];
    return clips
      .map((clip, index) => ({ clip, index }))
      .sort((a, b) => {
        const sa = Number.isFinite(a.clip?.predicted_score) ? a.clip.predicted_score : -1;
        const sb = Number.isFinite(b.clip?.predicted_score) ? b.clip.predicted_score : -1;
        return sb - sa || a.index - b.index;
      });
  }, [results]);

  const [bulkSub, setBulkSub] = useState({ running: false, current: 0, total: 0, errors: 0 });
  const [downloadingAll, setDownloadingAll] = useState(false);
  const [qualityGate, setQualityGate] = useState(null);
  const [logs, setLogs] = useState([]);
  const [logsVisible, setLogsVisible] = useState(() => {
    try { return window.innerWidth >= 768; } catch { return true; }
  });
  const [processingMedia, setProcessingMedia] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [navOpen, setNavOpen] = useState(false);
  const [projectState, setProjectState] = useState(null);
  const [noSource, setNoSource] = useState(false);
  const [sessionRecovered, setSessionRecovered] = useState(false);

  // Sync state for original video playback
  const [syncedTime, setSyncedTime] = useState(0);
  const [isSyncedPlaying, setIsSyncedPlaying] = useState(false);
  const [syncTrigger, setSyncTrigger] = useState(0);

  const handleClipPlay = (startTime) => {
    setSyncedTime(startTime);
    setIsSyncedPlaying(true);
    setSyncTrigger(prev => prev + 1);
  };

  const handleClipPause = () => setIsSyncedPlaying(false);

  const fetchCurrentDurableMap = useCallback(async () => fetchDurableMap(jobId), [jobId]);

  const { flushClipState, handleClipStateChange, handleClipRerendered } = useProjectSync({
    jobId,
    isManaged,
    fetchCurrentDurableMap,
    setDurableClips,
    setResults,
    setProjectState,
  });

  const restoreProject = async (projectJobId) => {
    const data = await restoreProjectApi(projectJobId);
    flushClipState();
    setProjectState(data.project_state || null);
    setNoSource(true);
    setJobId(data.job_id);
    setResults(data.result || null);
    setLogs(['♻️ Project restored from your library.']);
    setProcessingMedia(null);
    setQualityGate(null);
    setStatus('complete');
    setActiveTab('dashboard');
  };

  const handleBulkSubtitles = async (options) => {
    const clips = results?.clips || [];
    const total = clips.length;
    if (!total) return;
    setBulkSub({ running: true, current: 0, total, errors: 0 });
    let errors = 0;
    for (let i = 0; i < total; i++) {
      setBulkSub({ running: true, current: i + 1, total, errors });
      try {
        await applySubtitles({
          job_id: jobId,
          clip_index: i,
          position: options.position,
          font_size: options.fontSize,
          font_name: options.fontName,
          font_color: options.fontColor,
          border_color: options.borderColor,
          border_width: options.borderWidth,
          bg_color: options.bgColor,
          bg_opacity: options.bgOpacity,
          style: options.style || 'classic',
          highlight_color: options.highlightColor || '#FFD700',
          effect: options.effect || 'none',
          base_opacity: options.baseOpacity ?? 1.0,
          uppercase: options.uppercase || false,
          input_filename: (clips[i].video_url || '').split('/').pop(),
        });
      } catch { errors++; }
    }
    setBulkSub({ running: false, current: total, total, errors });
    refreshMe();
    try {
      const data = await pollJobStatus(jobId);
      if (data.result) setResults(data.result);
    } catch { }
  };

  const handleDownloadAll = async () => {
    if (!jobId) return;
    setDownloadingAll(true);
    try {
      const res = await downloadAllClips(jobId);
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `mastershorts_clips_${(jobId || '').slice(0, 8)}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert(`Download failed: ${e.message}`);
    } finally {
      setDownloadingAll(false);
    }
  };

  useEffect(() => {
    try {
      const saved = localStorage.getItem(SESSION_KEY);
      if (!saved) return;
      const session = JSON.parse(saved);
      if (Date.now() - session.timestamp > SESSION_MAX_AGE) {
        localStorage.removeItem(SESSION_KEY);
        return;
      }
      if (session.jobId && session.status && session.status !== 'idle') {
        setJobId(session.jobId);
        setResults(session.results || null);
        if (session.processingMedia) setProcessingMedia(session.processingMedia);
        else if (!session.noSource) setProcessingMedia({ type: 'server', payload: `/api/source/${session.jobId}` });
        if (session.noSource) setNoSource(true);
        if (session.projectState) setProjectState(session.projectState);
        if (session.activeTab) setActiveTab(session.activeTab);
        setStatus(session.status === 'processing' ? 'processing' : session.status);
        setSessionRecovered(true);
        setTimeout(() => setSessionRecovered(false), 5000);
      }
    } catch (e) { localStorage.removeItem(SESSION_KEY); }
  }, []);

  useEffect(() => {
    if (status === 'idle') {
      localStorage.removeItem(SESSION_KEY);
      return;
    }
    try {
      let persistMedia = null;
      if (processingMedia?.type === 'url') persistMedia = processingMedia;
      else if (processingMedia && jobId) persistMedia = { type: 'server', payload: `/api/source/${jobId}` };
      const sessionData = {
        jobId, status, results, processingMedia: persistMedia,
        activeTab, noSource, projectState, timestamp: Date.now()
      };
      localStorage.setItem(SESSION_KEY, JSON.stringify(sessionData));
    } catch (e) { }
  }, [jobId, status, results, activeTab, noSource, projectState]);

  useEffect(() => {
    if (!isManaged || !jobId || !(results?.clips?.length)) { setDurableClips({}); return; }
    let cancelled = false;
    fetchCurrentDurableMap().then((map) => { if (!cancelled) setDurableClips(map); }).catch(() => {});
    return () => { cancelled = true; };
  }, [isManaged, jobId, results?.clips?.length, fetchCurrentDurableMap]);

  useDurableClips({ isManaged, jobId, status, resultsCount: results?.clips?.length, fetchCurrentDurableMap, setDurableClips });

  useJobPolling({ jobId, status, setStatus, setResults, setPartialJob, setLogs, refreshMe });

  const loadUserProfiles = async ({ silent = false } = {}) => {
    if (!uploadPostKey && !isManaged) return;
    try {
      await fetchUserProfilesService();
    } catch (e) {
      if (!silent) alert("Error fetching User Profiles. Please check key.");
      console.error(e);
    }
  };

  const llmOk = (
    llmProvider === 'openai' ? !!llmBaseUrl :
    llmProvider === 'combo' ? (!!apiKey || !!openrouterApiKey || !!mistralApiKey) :
    !!apiKey
  ) || !!localLlm;
  const keysMissing = !billingEnabled && !llmOk;

  const { tutorialLock, finishTutorial, startTutorial } = useClipTutorial({
    tutorialPhase, setTutorialPhase, billingEnabled, isSignedIn, setShowPlanChoice, activeTab, setActiveTab, status, results, peekPendingJob
  });

  const skipTutorial = () => {
    track('ClipTutorialSkipped', { props: { phase: tutorialPhase } });
    finishTutorial();
  };

  const handleProcess = async (data, forceLowQuality = false) => {
    if (billingEnabled) {
      if (!isSignedIn) { stashPendingJob(data); setShowLogin(true); return; }
      if (!isManaged) { window.location.hash = '#/pricing'; return; }
    } else if (keysMissing) {
      setShowKeyModal(true); return;
    }
    popPendingJob();
    setStatus('processing');
    setLogs(["Starting process..."]);
    setResults(null);
    setProcessingMedia(data.type === 'thumbnail_session' ? null : data);
    setQualityGate(null);
    setProjectState(null);
    setNoSource(false);
    setPartialJob(null);

    try {
      let body;
      const headers = {};
      if (llmProvider === 'combo') {
        headers['X-LLM-Provider'] = 'combo';
        if (apiKey) headers['X-Gemini-Key'] = apiKey;
        if (openrouterApiKey) headers['X-OpenRouter-Key'] = openrouterApiKey;
        if (mistralApiKey) headers['X-Mistral-Key'] = mistralApiKey;
      } else if (llmProvider === 'openai' && llmBaseUrl) {
        headers['X-LLM-Base-URL'] = llmBaseUrl;
        headers['X-LLM-Model'] = llmModel || 'llama3.1:8b';
        if (llmApiKey) {
          headers['X-LLM-API-Key'] = llmApiKey;
        }
        if (llmFallbackModels) {
          headers['X-LLM-Fallback-Models'] = llmFallbackModels;
        }
      } else if (apiKey) {
        headers['X-Gemini-Key'] = apiKey;
      }
      const advanced = {
        target_clips: data.targetClips || null,
        clip_min_seconds: data.clipMinSeconds || null,
        clip_max_seconds: data.clipMaxSeconds || null,
        auto_hook: data.autoHook ? '1' : '0',
        auto_hook_style: data.autoHook ? (data.autoHookStyle || 'classic') : null,
        layouts: data.layout && data.layout !== 'auto' ? data.layout : null,
        max_minutes: data.maxMinutes || null,
        llm_provider: llmProvider,
        force_rerun: data.forceRerun ? 'true' : null,
        openrouter_key: (llmProvider === 'combo' && openrouterApiKey) ? openrouterApiKey : null,
        mistral_key: (llmProvider === 'combo' && mistralApiKey) ? mistralApiKey : null,
        llm_fallback_models: (llmProvider === 'openai' && llmFallbackModels) ? llmFallbackModels : null,
      };

      if (data.type === 'url') {
        headers['Content-Type'] = 'application/json';
        body = JSON.stringify({
          url: data.payload,
          acknowledged: !!data.acknowledged,
          output_format: data.outputFormat || 'auto',
          force_low_quality: forceLowQuality,
          ...Object.fromEntries(Object.entries(advanced).filter(([, v]) => v != null)),
        });
      } else if (data.type === 'thumbnail_session') {
        headers['Content-Type'] = 'application/json';
        body = JSON.stringify({
          thumbnail_session_id: data.payload,
          acknowledged: !!data.acknowledged,
          output_format: data.outputFormat || 'auto',
          ...Object.fromEntries(Object.entries(advanced).filter(([, v]) => v != null)),
        });
      } else {
        const formData = new FormData();
        formData.append('file', data.payload);
        formData.append('acknowledged', data.acknowledged ? 'true' : 'false');
        formData.append('output_format', data.outputFormat || 'auto');
        for (const [k, v] of Object.entries(advanced)) {
          if (v != null) formData.append(k, v);
        }
        body = formData;
      }

      const res = await submitJob({ headers, body });
      if (!res.ok) throw new Error(await res.text());
      const resData = await res.json();

      if (resData.needs_confirmation) {
        setStatus('idle');
        setQualityGate({ info: resData.quality_check, data });
        return;
      }

      setJobId(resData.job_id);
      setPartialJob(resData.partial || null);
      if (data.type === 'thumbnail_session') {
        setProcessingMedia({ type: 'server', payload: `/api/source/${resData.job_id}` });
      }
      refreshMe();

    } catch (e) {
      if (e instanceof QuotaError) {
        setStatus('idle');
        refreshMe();
        if (me?.status === 'trialing') {
          setShowTrialUpgrade(true);
        } else {
          const partial = e.partialMinutes || 0;
          setTopUpInfo({
            required: e.minutesRequired,
            remaining: e.minutesRemaining,
            partialMinutes: partial,
            onPartial: partial
              ? () => {
                  track('PartialClipChosen', { props: { required: e.minutesRequired, partial } });
                  setShowTopUp(false);
                  handleProcess({ ...data, maxMinutes: partial }, forceLowQuality);
                }
              : null,
          });
          setShowTopUp(true);
        }
        return;
      }
      setStatus('error');
      setLogs(l => [...l, `Error starting job: ${e.message}`]);
    }
  };

  const handleProcessRef = useRef(null);
  const resumedStampRef = useRef(0);
  useEffect(() => { handleProcessRef.current = handleProcess; });
  useEffect(() => {
    if (!billingEnabled || !isSignedIn) return;
    const pending = peekPendingJob();
    if (!pending || pending.stamp === resumedStampRef.current) return;
    resumedStampRef.current = pending.stamp;
    track('JobResumedAfterSignin', { props: { type: pending.data?.type || 'unknown' } });
    handleProcessRef.current(pending.data);
  }, [billingEnabled, isSignedIn]);

  const [isRetrying, setIsRetrying] = useState(false);

  const handleRetry = async () => {
    if (!jobId) return;
    setIsRetrying(true);
    try {
      const overrides = {};
      if (llmProvider === 'openai') {
        if (llmBaseUrl) overrides.llm_base_url = llmBaseUrl;
        if (llmModel) overrides.llm_model = llmModel;
        if (llmApiKey) overrides.llm_api_key = llmApiKey;
      } else if (apiKey) {
        overrides.gemini_api_key = apiKey;
      }
      await retryJob(jobId, overrides);
      setStatus('processing');
      setLogs(prev => [...prev, "🔄 Retomando processamento do vídeo..."]);
    } catch (e) {
      alert(`Falha ao tentar novamente: ${e.message}`);
    } finally {
      setIsRetrying(false);
    }
  };

  const handleReset = () => {
    flushClipState();
    setStatus('idle');
    setJobId(null);
    setResults(null);
    setLogs([]);
    setProcessingMedia(null);
    setProjectState(null);
    setNoSource(false);
    setPartialJob(null);
    localStorage.removeItem(SESSION_KEY);
  };

  const [isDeleting, setIsDeleting] = useState(false);

  const handleDeleteProject = async (idToDelete = jobId) => {
    const target = idToDelete || jobId;
    if (!target) return;
    if (!window.confirm("Deseja excluir permanentemente este projeto e todos os seus cortes para refazer do zero?")) {
      return;
    }
    setIsDeleting(true);
    try {
      if (processingMedia?.type === 'url' && processingMedia.payload) {
        try { localStorage.setItem('os_pending_url', processingMedia.payload); } catch (_) {}
      }
      await deleteJob(target);
      handleReset();
    } catch (e) {
      alert(`Falha ao excluir o projeto: ${e.message}`);
    } finally {
      setIsDeleting(false);
    }
  };

  return {
    isDeleting,
    handleDeleteProject,
    isRetrying,
    handleRetry,
    tutorialPhase, setTutorialPhase,
    partialJob, setPartialJob,
    durableClips, setDurableClips,
    showKeyModal, setShowKeyModal,
    jobId, setJobId,
    status, setStatus,
    results, setResults,
    rankedClips,
    bulkSub, setBulkSub,
    downloadingAll, setDownloadingAll,
    qualityGate, setQualityGate,
    logs, setLogs,
    logsVisible, setLogsVisible,
    processingMedia, setProcessingMedia,
    activeTab, setActiveTab,
    navOpen, setNavOpen,
    projectState, setProjectState,
    noSource, setNoSource,
    sessionRecovered, setSessionRecovered,
    syncedTime, setSyncedTime,
    isSyncedPlaying, setIsSyncedPlaying,
    syncTrigger, setSyncTrigger,
    handleClipPlay, handleClipPause,
    fetchCurrentDurableMap,
    restoreProject,
    handleBulkSubtitles,
    handleDownloadAll,
    keysMissing,
    tutorialLock, finishTutorial, startTutorial, skipTutorial,
    handleProcess,
    handleReset,
    loadUserProfiles,
    apiKey, setApiKey,
    llmProvider, setLlmProvider,
    llmBaseUrl, setLlmBaseUrl,
    llmModel, setLlmModel,
    llmApiKey, setLlmApiKey,
    llmFallbackModels, setLlmFallbackModels,
    openrouterApiKey, setOpenrouterApiKey,
    mistralApiKey, setMistralApiKey,
    uploadPostKey, setUploadPostKey, saveUploadPostKey,
    falKey, setFalKey, saveFalKey,
    handleClipStateChange, handleClipRerendered, flushClipState
  };
}
