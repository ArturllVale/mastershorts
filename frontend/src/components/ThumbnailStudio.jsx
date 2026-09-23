import { useState, useRef, useEffect } from 'react';
import { Upload, Image, Loader2, Send, Check, Download, ArrowRight, ArrowLeft, Sparkles, Video, Type, X, Plus, MessageSquare, FileText, Youtube, AlertCircle, Settings } from 'lucide-react';
import { getApiUrl } from '../config';
import StepIndicator from './ui/StepIndicator';
import SegmentedControl from './ui/SegmentedControl';
import {
  preUploadVideo,
  analyzeVideo,
  refineTitles,
  generateThumbnails,
  generateDescription,
  fetchFrames,
} from '../services/thumbnailService';

const STEPS = ['Entrada', 'Títulos', 'Miniatura', 'Descrição'];

import DragDropZone from '../features/thumbnail-studio/DragDropZone';
import StepInput from '../features/thumbnail-studio/StepInput';

export default function ThumbnailStudio({ geminiApiKey, managed = false, _onCreateClips = null }) {
  // Managed (hosted plan): Gemini runs server-side via the bearer token, no BYOK key.
  // Only send X-Gemini-Key for self-host BYOK. apiFetch attaches the bearer token.
  const keyHeader = geminiApiKey ? { 'X-Gemini-Key': geminiApiKey } : {};
  const needsKey = !geminiApiKey && !managed;
  // Step management
  const [step, setStep] = useState(0);
  const [mode, setMode] = useState(null); // 'video' or 'manual'

  // Step 1 state
  const [videoFile, setVideoFile] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // Step 2 state
  const [sessionId, setSessionId] = useState(null);
  const [titles, setTitles] = useState([]);
  const [selectedTitle, setSelectedTitle] = useState('');
  const [manualTitle, setManualTitle] = useState('');
  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [isRefining, setIsRefining] = useState(false);
  const [recommended, setRecommended] = useState([]); // [{index, reason}]
  const [thumbnailTexts, setThumbnailTexts] = useState([]); // hook text paired with each title

  // Step 3 state
  const [faceImage, setFaceImage] = useState(null);
  const [bgImage, setBgImage] = useState(null);
  const [extraPrompt, setExtraPrompt] = useState('');
  const [thumbnailCount, setThumbnailCount] = useState(3);
  const [burnText, setBurnText] = useState(true); // crisp PIL text vs model-rendered text
  const [frames, setFrames] = useState(null); // null = not fetched yet
  const [framesLoading, setFramesLoading] = useState(false);
  const [selectedFrame, setSelectedFrame] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedThumbnails, setGeneratedThumbnails] = useState([]);

  // Description state
  const [description, setDescription] = useState('');
  const [isDescribing, setIsDescribing] = useState(false);

  // Step 4 (Publish) state
  const [selectedThumbnail, setSelectedThumbnail] = useState(null);
    
  // Background preprocessing state
  const [preprocessSessionId, setPreprocessSessionId] = useState(null);
  const [isPreprocessing, setIsPreprocessing] = useState(false);

  const chatEndRef = useRef(null);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // --- Background Pre-upload (starts Whisper immediately) ---
  const handlePreUpload = async (file) => {
    setPreprocessSessionId(null);
    setIsPreprocessing(true);
    try {
      const data = await preUploadVideo(file);
      setPreprocessSessionId(data.session_id);
      console.log(`🎙️ Background Whisper started: ${data.session_id}`);
    } catch (e) {
      console.error('Pre-upload failed:', e);
    } finally {
      setIsPreprocessing(false);
    }
  };

  // --- Step 1: Analyze Video ---
  const handleAnalyze = async () => {
    if (needsKey) return alert('Configure sua chave de API do Gemini nas Configurações primeiro.');
    setIsAnalyzing(true);

    try {
      const formData = new FormData();

      if (preprocessSessionId) {
        // Use pre-uploaded session (Whisper already running/done in background)
        formData.append('session_id', preprocessSessionId);
      } else if (videoFile) {
        formData.append('file', videoFile);
      } else {
        return alert('Por favor, envie um arquivo de vídeo.');
      }

      const data = await analyzeVideo(formData, keyHeader);
      setSessionId(data.session_id);
      setTitles(data.titles || []);
      setThumbnailTexts(data.thumbnail_texts || []);
      setRecommended(data.recommended || []);
      setChatHistory([{
        role: 'assistant',
        content: `Aqui estão 10 sugestões de títulos virais baseados no seu vídeo. Os títulos marcados como RECOMENDADO são os meus favoritos. Clique em um para selecionar ou diga como deseja refiná-los.`
      }]);
      setStep(1);
    } catch (e) {
      alert(`Falha na análise: ${e.message}`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleManualMode = () => {
    setMode('manual');
    setStep(1);
  };

  // --- Step 2: Title Selection / Refinement ---
  const handleSelectTitle = (title) => {
    setSelectedTitle(title);
  };

  const handleConfirmTitle = () => {
    if (mode === 'manual' && manualTitle) {
      setSelectedTitle(manualTitle);
      // Create session for manual mode
      const newSessionId = sessionId || crypto.randomUUID();
      setSessionId(newSessionId);
      refineTitles({ title: manualTitle, session_id: newSessionId }, keyHeader).catch(() => { });
    }
    if (selectedTitle || (mode === 'manual' && manualTitle)) {
      setStep(2);
    }
  };

  const handleRefine = async () => {
    if (!chatInput.trim() || !sessionId) return;
    setIsRefining(true);

    const userMsg = chatInput.trim();
    setChatInput('');
    setChatHistory(prev => [...prev, { role: 'user', content: userMsg }]);

    try {
      const data = await refineTitles({ session_id: sessionId, message: userMsg }, keyHeader);
      setTitles(data.titles || []);
      setThumbnailTexts(data.thumbnail_texts || []);
      setRecommended([]);
      setChatHistory(prev => [...prev, {
        role: 'assistant',
        content: `Aqui estão os títulos refinados com base no seu feedback. Clique em um para selecionar.`
      }]);
      setTimeout(scrollToBottom, 100);
    } catch (e) {
      setChatHistory(prev => [...prev, {
        role: 'assistant',
        content: `Falha ao refinar títulos: ${e.message}`
      }]);
    } finally {
      setIsRefining(false);
    }
  };

  // --- Step 3: Generate Thumbnails ---
  const handleGenerate = async () => {
    if (needsKey) return alert('Configure sua chave de API do Gemini nas Configurações primeiro.');
    const finalTitle = selectedTitle || manualTitle;
    if (!finalTitle) return alert('Por favor, selecione ou digite um título primeiro.');

    setIsGenerating(true);
    setGeneratedThumbnails([]);

    try {
      const formData = new FormData();
      formData.append('session_id', sessionId || 'manual');
      formData.append('title', finalTitle);
      formData.append('extra_prompt', extraPrompt);
      formData.append('count', thumbnailCount);
      formData.append('burn_text', burnText ? 'true' : 'false');
      if (selectedFrame && !faceImage) formData.append('frame', selectedFrame);
      if (faceImage) formData.append('face', faceImage);
      if (bgImage) formData.append('background', bgImage);

      const data = await generateThumbnails(formData, keyHeader);
      if (!data.thumbnails || data.thumbnails.length === 0) {
        throw new Error('Nenhuma miniatura foi gerada. Sua chave da API do Gemini pode não ter acesso à geração de imagens.');
      }
      setGeneratedThumbnails(data.thumbnails);
    } catch (e) {
      alert(`Falha na geração: ${e.message}`);
    } finally {
      setIsGenerating(false);
    }
  };

  // Frames with a big, sharp face from the uploaded video: one click replaces
  // the face upload nobody makes. Fetched once when the generate step opens.
  // `frames` is deliberately not a dependency: setting it inside the effect
  // would re-run it and the cleanup would discard the response in flight.
  const framesRequestedFor = useRef(null);
  useEffect(() => {
    if (step !== 2 || mode !== 'video' || !sessionId) return;
    if (framesRequestedFor.current === sessionId) return;
    framesRequestedFor.current = sessionId;
    setFrames([]);
    setFramesLoading(true);
    fetchFrames(sessionId)
      .then(data => setFrames(data.frames || []))
      .catch(() => setFrames([]))
      .finally(() => setFramesLoading(false));
  }, [step, mode, sessionId]);

  const handleDownload = async (url) => {
    try {
      const response = await fetch(getApiUrl(url));
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = url.split('/').pop() || 'thumbnail.png';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(blobUrl);
    } catch {
      // Fallback: open in new tab if fetch fails
      window.open(getApiUrl(url), '_blank');
    }
  };

  // --- Description Generation ---
  const handleGenerateDescription = async () => {
    if (needsKey) return alert('Configure sua chave de API do Gemini nas Configurações primeiro.');
    const finalTitle = selectedTitle || manualTitle;
    if (!finalTitle) return alert('Por favor, selecione um título primeiro.');
    if (!sessionId) return alert('Nenhuma sessão disponível.');

    setIsDescribing(true);
    try {
      const data = await generateDescription({ session_id: sessionId, title: finalTitle }, keyHeader);
      setDescription(data.description || '');
    } catch (e) {
      alert(`Falha ao gerar descrição: ${e.message}`);
    } finally {
      setIsDescribing(false);
    }
  };

  const handleReset = () => {
    setStep(0);
    setMode(null);
    setVideoFile(null);
    setSessionId(null);
    setTitles([]);
    setSelectedTitle('');
    setManualTitle('');
    setChatInput('');
    setChatHistory([]);
    setFaceImage(null);
    setFrames(null);
    framesRequestedFor.current = null;
    setSelectedFrame(null);
    setThumbnailTexts([]);
    setBgImage(null);
    setExtraPrompt('');
    setGeneratedThumbnails([]);
    setDescription('');
    setIsDescribing(false);
    setSelectedThumbnail(null);
            setPreprocessSessionId(null);
    setIsPreprocessing(false);
    setRecommended([]);
  };

  return (
    <div className="h-full overflow-y-auto custom-scrollbar p-4 sm:p-6 md:p-8 animate-fade">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-end justify-between mb-2">
          <div>
            <p className="eyebrow mb-2">05 · YOUTUBE STUDIO</p>
            <h1 className="font-display text-2xl text-text-primary flex items-center gap-3">
              <span className="w-10 h-10 rounded-xl bg-surface-2 border border-border flex items-center justify-center">
                <Image size={18} className="text-accent" />
              </span>
              YouTube Studio
            </h1>
          </div>
          {step > 0 && (
            <button onClick={handleReset} className="text-xs text-text-tertiary hover:text-text-primary transition-colors flex items-center gap-1">
              <Plus size={12} /> Novo Projeto
            </button>
          )}
        </div>
        <p className="text-sm text-text-secondary mb-6">Gere títulos virais, miniaturas com IA e descrições</p>

        <div className="mb-8">
          <StepIndicator steps={STEPS} current={step} />
        </div>

        {/* Gemini API Key Warning */}
        {needsKey && (
          <div className="mb-6 p-5 bg-warn/10 border border-warn/30 rounded-xl flex items-start gap-3">
            <AlertCircle size={18} className="text-warn shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-warn">Chave de API do Gemini Necessária</p>
              <p className="text-xs text-text-secondary mt-1">O YouTube Studio precisa de uma chave de API do Google Gemini para funcionar. Configure-a na aba <strong>Configurações</strong> antes de usar este recurso. O plano gratuito do Gemini inclui 1.500 requisições por dia.</p>
            </div>
          </div>
        )}

        {/* ===== STEP 0: Input Mode Selection ===== */}
        {step === 0 && (
          <StepInput
            needsKey={needsKey}
            videoFile={videoFile}
            setVideoFile={setVideoFile}
            setMode={setMode}
            handlePreUpload={handlePreUpload}
            setPreprocessSessionId={setPreprocessSessionId}
            isPreprocessing={isPreprocessing}
            preprocessSessionId={preprocessSessionId}
            handleAnalyze={handleAnalyze}
            isAnalyzing={isAnalyzing}
            manualTitle={manualTitle}
            setManualTitle={setManualTitle}
            handleManualNext={handleManualMode}
          />
        )}

        {/* ===== STEP 1: Title Selection ===== */}
        {step === 1 && (
          <div className="grid md:grid-cols-5 gap-6">
            {/* Left: Chat / Controls */}
            <div className="md:col-span-2 flex flex-col gap-4">
              {mode === 'manual' ? (
                <div className="card p-6 space-y-4">
                  <p className="eyebrow">SEU TÍTULO</p>
                  <input
                    type="text"
                    value={manualTitle}
                    onChange={(e) => setManualTitle(e.target.value)}
                    className="input-field text-sm"
                    maxLength={70}
                  />
                  <p className="font-mono text-xs text-text-tertiary">{manualTitle.length} / 70</p>
                  <button
                    onClick={handleConfirmTitle}
                    disabled={!manualTitle.trim()}
                    className="w-full btn-primary"
                  >
                    <ArrowRight size={16} />
                    Continuar para Miniaturas
                  </button>
                </div>
              ) : (
                <div className="card p-4 flex flex-col h-[500px]">
                  <div className="flex items-center gap-2 mb-3 pb-3 border-b border-border">
                    <MessageSquare size={14} className="text-accent" />
                    <span className="eyebrow">CHAT DE REFINAMENTO DE TÍTULOS</span>
                  </div>

                  {/* Chat messages */}
                  <div className="flex-1 overflow-y-auto space-y-3 custom-scrollbar mb-3">
                    {chatHistory.map((msg, i) => (
                      <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[90%] px-3.5 py-2.5 rounded-xl text-xs leading-relaxed ${msg.role === 'user'
                          ? 'bg-accent/15 border border-accent/30 text-text-primary'
                          : 'bg-surface-2 border border-border text-text-secondary'
                          }`}>
                          {msg.content}
                        </div>
                      </div>
                    ))}
                    <div ref={chatEndRef} />
                  </div>

                  {/* Chat input */}
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleRefine()}
                      placeholder="Torne os títulos mais chamativos..."
                      className="input-field text-xs flex-1"
                      disabled={isRefining}
                    />
                    <button
                      onClick={handleRefine}
                      disabled={isRefining || !chatInput.trim()}
                      className="btn-quiet px-3 disabled:opacity-45 disabled:cursor-not-allowed"
                    >
                      {isRefining ? <Loader2 size={14} className="animate-spin text-accent" /> : <Send size={14} />}
                    </button>
                  </div>
                </div>
              )}

              {mode !== 'manual' && selectedTitle && (
                <button
                  onClick={handleConfirmTitle}
                  className="w-full btn-primary"
                >
                  <ArrowRight size={16} />
                  Usar Título Selecionado
                </button>
              )}
            </div>

            {/* Right: Title Cards */}
            <div className="md:col-span-3 space-y-3">
              {selectedTitle && (
                <div className="p-3 bg-success/10 border border-success/30 rounded-xl flex items-center gap-2 text-sm">
                  <Check size={14} className="text-success shrink-0" />
                  <span className="text-success font-medium truncate">Selecionado: {selectedTitle}</span>
                </div>
              )}

              {titles.length > 0 && (
                <div className="space-y-2">
                  {titles.map((title, i) => {
                    const rec = recommended.find(r => r.index === i);
                    const recRank = recommended.findIndex(r => r.index === i);
                    return (
                      <button
                        key={i}
                        onClick={() => handleSelectTitle(title)}
                        className={`w-full text-left p-4 rounded-xl border transition-all duration-200 text-sm ${selectedTitle === title
                          ? 'bg-surface-2 border-accent text-text-primary shadow-sm'
                          : 'border-border bg-surface-1 text-text-secondary hover:bg-surface-2/50 hover:border-border-hover'
                          }`}
                      >
                        <div className="flex items-start gap-3">
                          <span className={`w-6 h-6 rounded-full border flex items-center justify-center font-mono text-[10px] shrink-0 mt-0.5 ${selectedTitle === title ? 'bg-accent border-accent text-canvas font-bold' :
                            rec ? 'border-accent/40 text-accent' :
                              'border-border text-text-tertiary'
                            }`}>
                            {selectedTitle === title ? <Check size={10} /> : rec ? '★' : i + 1}
                          </span>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="leading-relaxed font-medium text-text-primary">{title}</span>
                              {rec && (
                                <span className="badge-accent shrink-0">
                                  {recRank === 0 ? 'RECOMENDADO' : '2ª OPÇÃO'}
                                </span>
                              )}
                            </div>
                            {rec && (
                              <p className="text-xs text-text-tertiary mt-1.5 leading-relaxed">{rec.reason}</p>
                            )}
                            {thumbnailTexts[i] && (
                              <p className="font-mono text-xs text-text-tertiary mt-1.5">Gancho da miniatura: "{thumbnailTexts[i]}"</p>
                            )}
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}

              {isRefining && (
                <div className="flex items-center justify-center py-8 text-text-tertiary">
                  <Loader2 size={18} className="animate-spin mr-2 text-accent" />
                  <span className="text-sm">Refinando títulos...</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ===== STEP 2: Thumbnail Generation ===== */}
        {step === 2 && (
          <div className="grid md:grid-cols-5 gap-6">
            {/* Left: Controls */}
            <div className="md:col-span-2 space-y-4">
              <div className="card p-6 space-y-4">
                <p className="eyebrow mb-1">TÍTULO</p>
                <div className="p-3 bg-surface-2 border border-border rounded-lg text-sm text-text-primary">
                  {selectedTitle || manualTitle}
                </div>

                <button
                  onClick={() => setStep(1)}
                  className="text-xs text-text-tertiary hover:text-text-primary transition-colors flex items-center gap-1"
                >
                  <ArrowLeft size={12} /> Alterar título
                </button>
              </div>

              {mode === 'video' && frames !== null && (
                <div className="card p-6 space-y-3">
                  <p className="eyebrow">SEU ROSTO EXTRAÍDO DO VÍDEO</p>
                  {frames.length === 0 ? (
                    <p className="text-xs text-text-tertiary">{framesLoading ? 'Buscando quadros nítidos com rosto...' : 'Nenhum rosto utilizável encontrado no vídeo.'}</p>
                  ) : (
                    <>
                      <div className="grid grid-cols-3 gap-2">
                        {frames.map((f) => (
                          <button
                            key={f.url}
                            type="button"
                            onClick={() => setSelectedFrame(selectedFrame === f.url ? null : f.url)}
                            className={`relative rounded-lg overflow-hidden border-2 transition-all ${selectedFrame === f.url ? 'border-accent ring-2 ring-accent/30' : 'border-transparent hover:border-border-hover'}`}
                          >
                            <img src={getApiUrl(f.url)} alt="" className="w-full aspect-video object-cover" />
                            <span className="absolute bottom-1 right-1 font-mono text-[10px] bg-black/70 text-white px-1 rounded">
                              {Math.floor(f.time / 60)}:{String(Math.floor(f.time % 60)).padStart(2, '0')}
                            </span>
                          </button>
                        ))}
                      </div>
                      <p className="text-xs text-text-tertiary">
                        {selectedFrame ? 'Este quadro será a referência da pessoa (o envio de foto tem prioridade).' : 'Escolha um quadro para que a miniatura mostre você, e não uma pessoa estranha.'}
                      </p>
                    </>
                  )}
                </div>
              )}

              <div className="card p-6 space-y-4">
                <p className="eyebrow">FOTO DO ROSTO · OPCIONAL</p>
                <DragDropZone
                  label="Enviar foto de rosto / pessoa"
                  accept="image/*"
                  onFile={setFaceImage}
                  file={faceImage}
                  onClear={() => setFaceImage(null)}
                  icon={Upload}
                />
              </div>

              <div className="card p-6 space-y-4">
                <p className="eyebrow">FUNDO · OPCIONAL</p>
                <DragDropZone
                  label="Enviar imagem de fundo"
                  accept="image/*"
                  onFile={setBgImage}
                  file={bgImage}
                  onClear={() => setBgImage(null)}
                  icon={Image}
                />
              </div>

              <div className="card p-6 space-y-4">
                <p className="eyebrow">INSTRUÇÕES ADICIONAIS · OPCIONAL</p>
                <textarea
                  value={extraPrompt}
                  onChange={(e) => setExtraPrompt(e.target.value)}
                  placeholder="Ex.: Use cores vermelho e preto, iluminação dramática, destaque bem o texto..."
                  className="input-field text-sm resize-none h-20"
                />
              </div>

              <div className="card p-6 space-y-4">
                <p className="eyebrow">TEXTO NA MINIATURA</p>
                <SegmentedControl
                  options={[{ value: true, label: 'Nítido' }, { value: false, label: 'Pintado por IA' }]}
                  value={burnText}
                  onChange={setBurnText}
                  size="sm"
                />
                <p className="text-xs text-text-tertiary">
                  {burnText ? 'O texto é aplicado em tipografia nítida e legível após a geração da imagem.' : 'O modelo de imagem desenha o texto diretamente na arte: mais integrado visualmente.'}
                </p>
              </div>

              <div className="card p-6 space-y-4">
                <p className="eyebrow">QUANTIDADE</p>
                <SegmentedControl
                  options={[1, 2, 3, 4].map(n => ({ value: n, label: String(n) }))}
                  value={thumbnailCount}
                  onChange={setThumbnailCount}
                  size="sm"
                />
              </div>

              <button
                onClick={handleGenerate}
                disabled={isGenerating}
                className="w-full btn-primary"
              >
                {isGenerating ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Gerando miniaturas...
                  </>
                ) : (
                  <>
                    <Sparkles size={16} />
                    Gerar Miniaturas
                  </>
                )}
              </button>
            </div>

            {/* Right: Generated Thumbnails */}
            <div className="md:col-span-3">
              {generatedThumbnails.length > 0 ? (
                <div className="space-y-4">
                  <p className="text-sm text-text-secondary font-medium">Miniaturas geradas — clique para selecionar</p>
                  <div className="grid gap-4">
                    {generatedThumbnails.map((thumb, i) => {
                      const url = thumb.url;
                      return (
                      <div
                        key={url}
                        onClick={() => setSelectedThumbnail(url)}
                        className={`card overflow-hidden group relative cursor-pointer transition-all duration-200 ${selectedThumbnail === url ? 'border-2 border-accent shadow-card-hover' : 'hover:border-border-hover'
                          }`}
                      >
                        <img
                          src={getApiUrl(url)}
                          alt={`Miniatura ${i + 1}`}
                          className="w-full aspect-video object-cover"
                        />
                        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-all flex items-center justify-center gap-3 opacity-0 group-hover:opacity-100">
                          <button
                            onClick={(e) => { e.stopPropagation(); handleDownload(url); }}
                            className="btn-quiet bg-surface-1/90 backdrop-blur-sm"
                          >
                            <Download size={14} />
                            Baixar
                          </button>
                        </div>
                        <div className="p-3 flex items-center justify-between gap-3 bg-surface-1">
                          <div className="min-w-0">
                            <span className="text-xs text-text-secondary flex items-center gap-2">
                              Miniatura {i + 1}{thumb.text ? ` · "${thumb.text}"` : ''}
                              {selectedThumbnail === url && (
                                <span className="text-accent flex items-center gap-1 font-medium"><Check size={10} /> Selecionada</span>
                              )}
                            </span>
                            {thumb.why && <p className="text-xs text-text-tertiary mt-1 truncate">{thumb.why}</p>}
                            {thumb.fallback && <p className="text-xs text-warn mt-1">O Gemini bloqueou o desenho desta pessoa (figuras públicas protegidas); renderizado sem ela.</p>}
                          </div>
                          <button
                            onClick={(e) => { e.stopPropagation(); handleDownload(url); }}
                            className="text-xs text-text-tertiary hover:text-text-primary transition-colors flex items-center gap-1 shrink-0"
                          >
                            <Download size={12} /> Salvar
                          </button>
                        </div>
                      </div>
                      );
                    })}
                  </div>

                  {/* Phone preview */}
                  <div className="card p-4 space-y-3">
                    <p className="eyebrow">PRÉVIA NO CELULAR</p>
                    <div className="space-y-3">
                      {generatedThumbnails.map((thumb) => (
                        <div key={thumb.url} className="flex gap-3 items-start">
                          <img src={getApiUrl(thumb.url)} alt="" className="w-[168px] h-[94px] object-cover rounded-lg shrink-0 border border-border" />
                          <div className="min-w-0">
                            <p className="text-sm text-text-primary leading-snug line-clamp-2 font-medium">{selectedTitle || manualTitle}</p>
                            <p className="font-mono text-xs text-text-tertiary mt-1">Seu canal · 1,2 mil visualizações · há 2 horas</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Regenerate */}
                  <button
                    onClick={handleGenerate}
                    disabled={isGenerating}
                    className="w-full btn-ghost"
                  >
                    {isGenerating ? (
                      <>
                        <Loader2 size={14} className="animate-spin text-accent" />
                        Gerando novamente...
                      </>
                    ) : (
                      <>
                        <Sparkles size={14} />
                        Gerar Novamente
                      </>
                    )}
                  </button>

                  {/* Proceed to Description */}
                  {selectedThumbnail && (
                    <button
                      onClick={() => setStep(3)}
                      className="w-full btn-primary"
                    >
                      <ArrowRight size={16} />
                      Avançar: Descrição
                    </button>
                  )}
                </div>
              ) : isGenerating ? (
                <div className="h-full flex flex-col items-center justify-center text-text-tertiary space-y-4 min-h-[400px]">
                  <div className="w-14 h-14 rounded-full border-2 border-border border-t-accent animate-spin" />
                  <div className="text-center">
                    <p className="text-sm font-medium text-text-primary">Gerando miniaturas...</p>
                    <p className="text-xs text-text-tertiary mt-1">Isso pode levar cerca de um minuto por miniatura</p>
                  </div>
                </div>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-text-tertiary space-y-4 min-h-[400px]">
                  <div className="w-16 h-16 rounded-xl bg-surface-2 border border-border flex items-center justify-center">
                    <Image size={24} className="text-text-tertiary" />
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-text-secondary">Suas miniaturas aparecerão aqui</p>
                    <p className="text-xs text-text-tertiary mt-1">Configure as opções e clique em Gerar Miniaturas</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ===== STEP 3: YouTube Description ===== */}
        {step === 3 && (
          <div className="grid md:grid-cols-5 gap-6">
            {/* Left: Context & Controls */}
            <div className="md:col-span-2 space-y-4">
              <button
                onClick={() => setStep(2)}
                className="text-xs text-text-tertiary hover:text-text-primary transition-colors flex items-center gap-1 mb-2"
              >
                <ArrowLeft size={12} /> Voltar para Miniaturas
              </button>

              {/* Selected Thumbnail Preview */}
              {selectedThumbnail && (
                <div className="card overflow-hidden">
                  <img
                    src={getApiUrl(selectedThumbnail)}
                    alt="Miniatura selecionada"
                    className="w-full aspect-video object-cover"
                  />
                  <div className="p-3 bg-surface-1">
                    <span className="text-xs text-accent flex items-center gap-1 font-medium"><Check size={10} /> Miniatura Selecionada</span>
                  </div>
                </div>
              )}

              {/* Title */}
              <div className="card p-6 space-y-3">
                <p className="eyebrow">TÍTULO</p>
                <div className="p-3 bg-surface-2 border border-border rounded-lg text-sm text-text-primary">
                  {selectedTitle || manualTitle}
                </div>
              </div>

              {/* Generate Description Button */}
              {mode === 'video' && (
                <div className="card p-6 space-y-4">
                  <div className="flex items-center justify-between">
                    <p className="eyebrow flex items-center gap-2">
                      <Sparkles size={14} className="text-accent" />
                      DESCRIÇÃO COM IA
                    </p>
                    <span className="font-mono text-xs text-text-tertiary">COM CAPÍTULOS</span>
                  </div>
                  <p className="text-xs text-text-tertiary">
                    Gere uma descrição para o YouTube com marcações de capítulos da transcrição do seu vídeo.
                  </p>
                  <button
                    onClick={handleGenerateDescription}
                    disabled={isDescribing}
                    className="w-full btn-ghost"
                  >
                    {isDescribing ? (
                      <>
                        <Loader2 size={14} className="animate-spin text-accent" />
                        Gerando descrição...
                      </>
                    ) : (
                      <>
                        <FileText size={14} />
                        {description ? 'Gerar Novamente Descrição' : 'Gerar Descrição'}
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>

            {/* Right: Editable Description */}
            <div className="md:col-span-3 space-y-4">
              <div className="card p-6 space-y-4 h-full flex flex-col">
                <div className="flex items-center justify-between">
                  <p className="eyebrow flex items-center gap-2">
                    <FileText size={14} className="text-text-tertiary" />
                    DESCRIÇÃO DO YOUTUBE
                  </p>
                  <span className="font-mono text-xs text-text-tertiary">{description.length} / 5000</span>
                </div>

                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={mode === 'video'
                    ? "Clique em 'Gerar Descrição' para criar automaticamente com capítulos, ou escreva a sua..."
                    : "Escreva a descrição do seu vídeo aqui..."
                  }
                  className="input-field text-sm resize-none flex-1 min-h-[500px] font-mono custom-scrollbar leading-relaxed"
                  maxLength={5000}
                />

                {!description && (
                  <p className="text-xs text-text-tertiary">
                    {mode === 'video'
                      ? "A IA criará uma descrição atrativa com marcações de capítulos a partir da transcrição do vídeo."
                      : "Escreva uma descrição para o seu vídeo."}
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        
        </div>
    </div>
  );
}
