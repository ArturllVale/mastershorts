export interface CaptionWord {
  text: string;
  startMs: number;
  endMs: number;
}

export interface SubtitleStyle {
  fontFamily?: string;
  fontSize?: number;
  fontColor?: string;
  highlightColor?: string;
  borderColor?: string;
  borderWidth?: number;
  bgColor?: string;
  bgOpacity?: number;
  animation?: "pop" | "karaoke" | "word-highlight" | "none" | "fade";
  baseOpacity?: number;
  uppercase?: boolean;
  marginV?: number;
}

export interface SubtitleConfig {
  captions: CaptionWord[];
  position?: string;
  style: SubtitleStyle;
}

export interface HookConfig {
  text: string;
  position?: string;
  style?: string;
  size?: string;
  displayDurationSec?: number;
}

export interface EffectsConfig {
  segments?: Array<{
    start: number;
    end: number;
    type: string;
  }>;
}

export interface ShortVideoProps {
  videoUrl: string;
  durationInFrames?: number;
  fps?: number;
  width?: number;
  height?: number;
  subtitles?: SubtitleConfig | null;
  hook?: HookConfig | null;
  effects?: EffectsConfig | null;
}
