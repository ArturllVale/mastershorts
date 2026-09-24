# Auditoria do Componente `ClipEditor`

## 1. Estrutura Atual
O `ClipEditor` é atualmente um componente monolítico muito grande (`frontend/src/components/ClipEditor.jsx` com mais de 1300 linhas).
Ele já iniciou uma transição parcial para uma pasta `features/clip-editor/`, extraindo alguns componentes (`SegmentRow.jsx`, `TranscriptChunk.jsx`) e o reducer (`editorReducer.js`), bem como alguns hooks em `src/hooks/` (`useDragSegment.js`, `useVideoSeek.js`, `useEditorShortcuts.js`). No entanto, o componente central continua sendo um "Deus Component", misturando estado de negócio, lógica de UI, cálculos complexos de timeline (cobertura, clamping, conversão de tempo), chamadas à API e formatações pesadas do JSX.

## 2. Principais Problemas
* **Responsabilidades Misturadas:** `ClipEditor.jsx` orquestra o layout, controla o player de vídeo fonte, o player da prévia de corte, desenha as timelines (tracks de clip e de source), lida com operações complexas de dragging e snaps de tempo, gerencia marcações de Three-Point Editing (in/out) e faz integrações diretas com API.
* **Componentes Aninhados e JSX Denso:** Muitas áreas da UI (Header, Tracks, Controles laterais, Transcrição) estão declaradas em linha no JSX principal, resultando num arquivo muito denso e difícil de ler.
* **Cálculos Densos Inline:** Existem hooks grandes (`useMemo`, `useCallback`) contendo forte regra de negócio (como `coverage`, `clipToRendered`, `clampToCovered`, `clipToSource`) injetados diretamente no componente, poluindo a coesão.
* **Exposição Direta de Refs do DOM:** Múltiplas referências diretas (`videoRef`, `sourceRef`, `clipTrackRef`, `sourceTrackRef`) são repassadas e manipuladas no meio da renderização e em handlers acoplados.

## 3. Dependências Importantes
* **Hooks Customizados:** `useAuth`, `useEditorShortcuts`, `useVideoSeek`, `useDragSegment`.
* **Serviços:** `fetchEDL`, `rerenderClip` de `clipService.js` e chamadas à API (`getApiUrl`, `QuotaError`).
* **Estado e Utilitários:** `editorReducer.js`, `fmt`, `totalOf` de `clipUtils.js`.
* **Componentes Extraídos:** `TranscriptChunk.jsx`, `SegmentRow.jsx`.

## 4. Riscos da Refatoração
* **Quebrar Sincronização de Reprodução:** O scrub/timeline está fortemente acoplado com os refs de vídeo e a função `requestAnimationFrame`. Se a lógica de cobertura (`coverage`) e clamp for separada erroneamente, o drag na timeline ou a reprodução podem ficar dessincronizados.
* **Erros de Renderização Otimizada:** O `TranscriptChunk` utiliza `useDeferredValue` e a timeline usa eventos pesados de mouse para o dragging (e.g., `startClipScrub`). Mover isso para componentes menores requer cuidado para não disparar re-renders de todo o layout.
* **Desacoplamento de Refs:** Separar a UI da timeline e dos players vai demandar compartilhamento inteligente de `refs` de vídeo e tracks.
* O projeto está usando `.jsx` (com React clássico e JS sem tipagem estrita via TypeScript), portanto não devemos forçar migração para TypeScript no momento.

## 5. Plano de Divisão dos Componentes (Arquitetura Proposta)
O projeto utilizará a pasta atual `features/clip-editor` para receber a extração de componentes focados, serviços e ganchos (hooks):

```text
frontend/src/features/clip-editor/
├── components/
│   ├── ClipEditor.jsx (Orquestrador)
│   ├── EditorHeader.jsx (Cabeçalho com botão fechar e informações do corte)
│   ├── layout/
│   │   ├── EditorLayout.jsx (Estrutura de colunas)
│   ├── source/
│   │   ├── SourceMonitor.jsx (Player do vídeo original)
│   │   ├── SourceTrack.jsx (Timeline do vídeo original)
│   │   ├── ThreePointControls.jsx (Controles IN/OUT, replace/insert)
│   │   └── TranscriptPanel.jsx (Painel com a transcrição inteira e highlight)
│   ├── preview/
│   │   ├── PreviewMonitor.jsx (Player da prévia com vídeo recortado)
│   │   └── ClipTrack.jsx (Timeline do resultado do corte)
│   └── controls/
│       ├── SidebarControls.jsx (Painel direito: segmentos, enquadramento e rodapé)
│       ├── FramingOptions.jsx
│       └── EditorFooter.jsx (Botões de render e fechar)
├── hooks/
│   ├── useClipEditorData.js (Carregamento da EDL e states principais)
│   ├── useEditorTimeline.js (Lógica de cobertura, clipToSource, clipToRendered, etc.)
│   ├── useThreePointEditing.js (Marcação in/out)
│   └── (Existentes: useDragSegment.js, useVideoSeek.js)
├── state/
│   └── editorReducer.js (Já existente)
├── utils/
│   └── timelineUtils.js (Operações utilitárias de timeline/clips)
└── ...
```

## 6. Arquivos que serão criados ou modificados
* **Modificados:** `frontend/src/components/ClipEditor.jsx` (Será convertido no contêiner principal leve ou movido inteiramente para feature).
* **Criados:** Vários subcomponentes (`EditorHeader.jsx`, `SourceMonitor.jsx`, `SourceTrack.jsx`, `PreviewMonitor.jsx`, `ClipTrack.jsx`, `SidebarControls.jsx`, `ThreePointControls.jsx`, `TranscriptPanel.jsx`).
* **Criados:** Arquivos de utilidade e hooks extraídos da lógica solta em `ClipEditor.jsx`.
