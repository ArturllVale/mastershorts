import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Upload, Sparkles, Youtube, Instagram, Share2, ChevronDown, Check, Activity, LayoutDashboard, Settings, Plus, History, X, Terminal, Shield, Image, Globe, RotateCcw, AlertTriangle, KeyRound, Bot, Users, Smartphone, ExternalLink, Copy, CheckCircle2, Mail, Loader2, Download, Menu, Lock } from 'lucide-react';
import KeyInput from './components/KeyInput';
import MediaInput from './components/MediaInput';
import ResultCard from './components/ResultCard';
import ProcessingAnimation from './components/ProcessingAnimation';
// import Gallery from './components/Gallery';
import ThumbnailStudio from './components/ThumbnailStudio';

import ClipEditor from './components/ClipEditor';
import ReframeEditor from './components/ReframeEditor';
import UsageMeter from './components/UsageMeter';
import TopUpModal from './components/TopUpModal';
import StarBanner from './components/StarBanner';
import PlanChoiceModal from './components/PlanChoiceModal';
import ClipTutorial from './components/ClipTutorial';
import TrialUpgradeModal from './components/TrialUpgradeModal';
import LoginModal from './components/LoginModal';
import TrialGate from './components/TrialGate';
import HistoryTab from './components/HistoryTab';
import ProfileMenu from './components/ProfileMenu';
import Modal from './components/ui/Modal';
import { useAuth } from './contexts/AuthContext';
import { apiFetch, apiJson, QuotaError } from './lib/api';
import { track } from './lib/analytics';
import { encrypt, decrypt } from './lib/crypto';
import { submitJob, pollJobStatus, downloadAllClips } from './services/jobService';
import { restoreProject as restoreProjectApi, saveProjectState, fetchDurableMap } from './services/projectService';
import { applySubtitles } from './services/clipService';
import { fetchUserProfiles as fetchUserProfilesService } from './services/socialService';
import { useApiKeys } from './hooks/useApiKeys';
import { useBilling } from './hooks/useBilling';
import UserProfileSelector from './components/UserProfileSelector';
import Sidebar from './layout/Sidebar';
import MobileNavDrawer from './layout/MobileNavDrawer';
import MobileTabBar from './layout/MobileTabBar';
import AppHeader from './layout/AppHeader';
import SettingsView from './features/settings/SettingsView';
import DashboardView from './features/clip-generator/DashboardView';
import { useAppController } from './hooks/useAppController';

const SESSION_KEY = 'Master Shorts_session';
// Matches the self-host JOB_RETENTION_SECONDS default. A restore whose job was
// already purged server-side fails gracefully and clears the saved session.
const SESSION_MAX_AGE = 86400000; // 24 hours

function App() {
  // Cloud auth/billing session (inert when billing is disabled).
  const { billingEnabled, isManaged, isSignedIn, me, plan, refreshMe, localLlm } = useAuth();
  const { showLogin, setShowLogin, showTopUp, setShowTopUp, showPlanChoice, setShowPlanChoice, showTrialUpgrade, setShowTrialUpgrade, topUpInfo, setTopUpInfo } = useBilling();
  const {
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
    uploadPostKey, setUploadPostKey, saveUploadPostKey,
    elevenLabsKey, setElevenLabsKey, saveElevenLabsKey,
    falKey, setFalKey, saveFalKey,
    handleClipStateChange, handleClipRerendered, flushClipState
  } = useAppController();

  // Clip editor overlay: index of the clip being edited, or null.
  const [editingClip, setEditingClip] = useState(null);
  const [reframingClip, setReframingClip] = useState(null);

  // Included in the plan (fully managed, no keys): Clip Generator + YouTube Studio.
  const INCLUDED_TOOL_TABS = ['dashboard', 'thumbnails'];
  const TOOL_NAMES = { dashboard: 'o Gerador de Clipes', thumbnails: 'o Estúdio YouTube' };
  const needsPlan = billingEnabled && !isManaged;   // hosted, signed-out or no active plan/trial
  const gateThisTab = needsPlan && INCLUDED_TOOL_TABS.includes(activeTab);      // included tool, no plan yet

  // --- UI Components ---

  // One nav definition drives all three surfaces: the desktop rail, the mobile
  // drawer, and the bottom tab bar.
  const navItems = [
    { id: 'dashboard', ord: '01', icon: LayoutDashboard, label: 'Gerador de Clipes', short: 'Clipes', primary: true },
    { id: 'thumbnails', ord: '02', icon: Image, label: 'Estúdio YouTube', short: 'Estúdio', primary: true },
    ...(billingEnabled && isSignedIn ? [{ id: 'history', ord: '03', icon: History, label: 'Histórico', short: 'Histórico' }] : []),
    { id: 'settings', ord: billingEnabled && isSignedIn ? '04' : '03', icon: Settings, label: 'Configurações', short: 'Ajustes' },
  ];
  const activeNav = navItems.find((n) => n.id === activeTab);

  // Escape closes the mobile drawer.
  useEffect(() => {
    if (!navOpen) return;
    const onKey = (e) => { if (e.key === 'Escape') setNavOpen(false); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [navOpen]);

  const goToTab = (id) => {
    if (tutorialLock && id !== 'dashboard') return;
    setActiveTab(id);
    setNavOpen(false);
  };
  const tabLocked = (id) => tutorialLock && id !== 'dashboard';

  // Desktop rail
  return (
    <div className="flex h-screen supports-[height:100dvh]:h-[100dvh] bg-paper overflow-hidden">
      <Sidebar
        navItems={navItems}
        activeTab={activeTab}
        goToTab={goToTab}
        tabLocked={tabLocked}
        billingEnabled={billingEnabled}
      />
      <MobileNavDrawer
        navItems={navItems}
        activeTab={activeTab}
        goToTab={goToTab}
        tabLocked={tabLocked}
        navOpen={navOpen}
        setNavOpen={setNavOpen}
        billingEnabled={billingEnabled}
      />

      <main className="flex-1 min-w-0 flex flex-col h-full overflow-hidden relative">
        <AppHeader
          setNavOpen={setNavOpen}
          activeNav={activeNav}
          status={status}
          handleReset={handleReset}
          billingEnabled={billingEnabled}
          isManaged={isManaged}
          plan={plan}
          setTopUpInfo={setTopUpInfo}
          setShowTopUp={setShowTopUp}
          setShowPlanChoice={setShowPlanChoice}
          setShowLogin={setShowLogin}
          isSignedIn={isSignedIn}
          keysMissing={keysMissing}
          goToTab={goToTab}
        />

        {/* Persistent Missing Keys Banner */}
        {keysMissing && activeTab !== 'settings' && (
          <div className="mx-3 sm:mx-6 mt-3 px-3.5 sm:px-4 py-2.5 bg-paper2 border border-rule rounded-card flex flex-wrap items-center justify-between gap-2.5 sm:gap-4 shrink-0 animate-fade">
            <div className="flex items-start sm:items-center gap-2.5 sm:gap-3 text-xs text-ink2 min-w-0 flex-1">
              <KeyRound size={16} className="shrink-0 text-warn mt-0.5 sm:mt-0" />
              <div className="min-w-0">
                <span className="font-semibold text-ink">AI Provider Configuration Required.</span>{' '}
                <span className="text-muted">
                  {llmProvider === 'openai'
                    ? 'Configure your OpenAI-compatible endpoint in Settings to process videos.'
                    : 'Set your free Google Gemini API key to enable video analysis and clipping.'}
                </span>
              </div>
            </div>
            <button
              onClick={() => goToTab('settings')}
              className="btn-secondary px-3 py-1 text-xs shrink-0 w-full sm:w-auto"
            >
              Configure in Settings
            </button>
          </div>
        )}

        {/* Session Recovery Banner */}
        {sessionRecovered && (
          <div className="mx-3 sm:mx-6 mt-2 px-3.5 sm:px-4 py-3 bg-paper2 border border-rule rounded-card flex items-start justify-between gap-3 animate-fade shrink-0">
            <div className="flex items-start sm:items-center gap-2 text-sm text-ink2 flex-wrap min-w-0">
              <RotateCcw size={16} className="text-brass shrink-0 mt-0.5 sm:mt-0" />
              <span className="font-medium">Session recovered</span>
              <span className="text-muted text-xs">Your previous work has been restored.</span>
            </div>
            <button
              onClick={() => setSessionRecovered(false)}
              aria-label="dismiss"
              className="text-muted hover:text-ink transition-colors shrink-0 -m-1 p-1"
            >
              <X size={16} />
            </button>
          </div>
        )}

        {/* Included tools (Clip Generator, YouTube Studio): non-blocking trial prompt. */}
        {gateThisTab && <TrialGate toolName={TOOL_NAMES[activeTab] || 'this'} />}

        {/* Main Workspace */}
        <div className="flex-1 overflow-hidden relative">

          {activeTab === 'settings' && (
            <SettingsView
              isManaged={isManaged}
              billingEnabled={billingEnabled}
              setShowPlanChoice={setShowPlanChoice}
              setApiKey={setApiKey}
              apiKey={apiKey}
              llmProvider={llmProvider}
              setLlmProvider={setLlmProvider}
              llmBaseUrl={llmBaseUrl}
              setLlmBaseUrl={setLlmBaseUrl}
              llmModel={llmModel}
              setLlmModel={setLlmModel}
              llmApiKey={llmApiKey}
              setLlmApiKey={setLlmApiKey}
              llmFallbackModels={llmFallbackModels}
              setLlmFallbackModels={setLlmFallbackModels}
            />
          )}

          {/* View: History */}
          {activeTab === 'history' && (
            <div className="h-full overflow-y-auto custom-scrollbar animate-fade">
              <div className="max-w-6xl mx-auto p-4 sm:p-6 md:p-8">
                <HistoryTab onReopenProject={restoreProject} />
              </div>
            </div>
          )}

          {activeTab === 'thumbnails' && (
            <ThumbnailStudio
              geminiApiKey={apiKey}
              
              
              managed={isManaged}
              onCreateClips={(sessionId) => {
                setActiveTab('dashboard');
                // The Studio source is the user's own upload, published to their
                // own channel; the handover carries that same attestation.
                handleProcess({ type: 'thumbnail_session', payload: sessionId, acknowledged: true });
              }}
            />
          )}

          {/* View: Gallery */}
          {/* {activeTab === 'gallery' && (
            <Gallery />
          )} */}

          <DashboardView
            activeTab={activeTab}
            status={status}
            tutorialLock={tutorialLock}
            billingEnabled={billingEnabled}
            goToTab={goToTab}
            handleProcess={handleProcess}
            processingMedia={processingMedia}
            syncedTime={syncedTime}
            isSyncedPlaying={isSyncedPlaying}
            syncTrigger={syncTrigger}
            logs={logs}
            logsVisible={logsVisible}
            setLogsVisible={setLogsVisible}
            results={results}
            isManaged={isManaged}
            handleDownloadAll={handleDownloadAll}
            downloadingAll={downloadingAll}
            partialJob={partialJob}
            plan={plan}
            setTopUpInfo={setTopUpInfo}
            setShowTopUp={setShowTopUp}
            rankedClips={rankedClips}
            jobId={jobId}
            setEditingClip={setEditingClip}
            setReframingClip={setReframingClip}
            projectState={projectState}
            handleClipStateChange={handleClipStateChange}
            durableClips={durableClips}
            apiKey={apiKey}
            elevenLabsKey={elevenLabsKey}
            handleClipPlay={handleClipPlay}
            handleClipPause={handleClipPause}
            handleBulkSubtitles={handleBulkSubtitles}
            bulkSub={bulkSub}
            handleReset={handleReset}
          />

        </div>

        {/* Phone navigation. A flex sibling of the scrolling pane, not a fixed
            overlay, so content is never trapped behind it. */}
        <MobileTabBar
          navItems={navItems}
          activeTab={activeTab}
          goToTab={goToTab}
          tabLocked={tabLocked}
          navOpen={navOpen}
          setNavOpen={setNavOpen}
        />

      </main>

      {/* Missing API Key Modal */}
      <Modal
        isOpen={showKeyModal}
        onClose={() => setShowKeyModal(false)}
        eyebrow="SETUP"
        title="AI Engine Configuration Required"
        footer={
          <div className="flex gap-3">
            <button
              onClick={() => setShowKeyModal(false)}
              className="btn-ghost flex-1 px-4 py-2 text-sm"
            >
              Cancel
            </button>
            <button
              onClick={() => { setShowKeyModal(false); goToTab('settings'); }}
              className="btn-primary flex-1 px-4 py-2 text-sm"
            >
              Go to Settings
            </button>
          </div>
        }
      >
        <div className="space-y-4">
          <p className="text-sm text-muted">
            OpenShorts requires an AI engine to analyze video transcripts and locate viral moments.
          </p>

          {llmProvider === 'openai' ? (
            <div className="rounded-input p-4 space-y-2 border border-rule2 bg-paper3/40">
              <p className="text-xs font-medium text-ink flex items-center gap-2">
                <AlertTriangle size={12} className="text-warn" />
                OpenAI Endpoint Required
              </p>
              <p className="text-xs text-muted leading-relaxed">
                Configure your OpenAI-compatible endpoint URL (such as Ollama, LM Studio, vLLM, or OpenAI) in Settings to start clipping videos.
              </p>
            </div>
          ) : (
            <div className={`rounded-input p-4 space-y-2 border ${!apiKey ? 'border-rule2' : 'border-rule opacity-70'}`}>
              <p className="text-xs font-medium text-ink flex items-center gap-2">
                {apiKey ? <Check size={12} className="text-ok" /> : <AlertTriangle size={12} className="text-warn" />}
                Gemini API Key {apiKey && <span className="text-ok">— set</span>}
              </p>
              {!apiKey && (
                <>
                  <ol className="text-xs text-muted space-y-1 list-decimal list-inside">
                    <li>Go to <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener noreferrer" className="text-brass underline">aistudio.google.com/app/apikey</a></li>
                    <li>Sign in with your Google account</li>
                    <li>Click "Create API Key"</li>
                    <li>Paste your key below or configure in Settings</li>
                  </ol>
                  <input
                    type="text"
                    placeholder="Paste your Gemini API key here..."
                    className="input-field"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && e.target.value.trim()) {
                        setApiKey(e.target.value.trim());
                      }
                    }}
                  />
                </>
              )}
            </div>
          )}
        </div>
      </Modal>

      

      {/* Pre-flight quality gate */}
      {qualityGate && (
        <Modal isOpen={true} onClose={() => setQualityGate(null)} size="md" eyebrow="HEADS UP" title="baixa qualidade da fonte">
          <div className="space-y-4">
            <p className="text-sm text-ink2">
              O YouTube sÃ³ oferece <span className="text-brass font-semibold">{qualityGate.info.max_height}p</span> para este vÃ­deo
              (below the {qualityGate.info.min_height}p we recommend). Processar mesmo assim produzirÃ¡ clipes de baixa qualidade.
            </p>
            {qualityGate.info.cookies_invalid && (
              <p className="text-xs text-muted">
                Your YouTube cookies look expired â€” refreshing them (export again from an incognito window) often unlocks HD.
              </p>
            )}
            <div className="flex gap-2 justify-end pt-2">
              <button onClick={() => setQualityGate(null)} className="btn-ghost">cancel</button>
              <button
                onClick={() => { const d = qualityGate.data; setQualityGate(null); handleProcess(d, true); }}
                className="btn-primary"
              >
                process anyway
              </button>
            </div>
          </div>
        </Modal>
      )}


      {editingClip !== null && results?.clips?.[editingClip] && (
        <ClipEditor
          jobId={jobId}
          clipIndex={editingClip}
          clipTitle={results.clips[editingClip].video_title_for_youtube_short || ''}
          onClose={() => setEditingClip(null)}
          onRerendered={handleClipRerendered}
        />
      )}
      {reframingClip !== null && results?.clips?.[reframingClip] && (
        <ReframeEditor
          jobId={jobId}
          clipIndex={reframingClip}
          clipTitle={results.clips[reframingClip].video_title_for_youtube_short || ''}
          onClose={() => setReframingClip(null)}
          onReframed={handleClipRerendered}
        />
      )}
      {showLogin && <LoginModal onClose={() => setShowLogin(false)} queued={typeof peekPendingJob()?.data?.payload === 'string'} />}
      {tutorialPhase && (
        <ClipTutorial
          phase={tutorialPhase}
          jobStatus={status}
          onStart={startTutorial}
          onSkip={skipTutorial}
          onDismissCelebrate={finishTutorial}
        />
      )}
      {showPlanChoice && <PlanChoiceModal onClose={() => setShowPlanChoice(false)} />}
      {showTopUp && (
        <TopUpModal
          onClose={() => setShowTopUp(false)}
          required={topUpInfo.required}
          remaining={topUpInfo.remaining}
          partialMinutes={topUpInfo.partialMinutes}
          onPartial={topUpInfo.onPartial}
          context={topUpInfo.context || 'wall'}
        />
      )}
      {showTrialUpgrade && (
        <TrialUpgradeModal
          plan={plan}
          onActivated={refreshMe}
          onClose={() => setShowTrialUpgrade(false)}
        />
      )}
    </div>
  );
}

export default App;

