export function groupCaptionsIntoBlocks(captions, maxChars = 16, maxDurationMs = 1400) {
  if (!captions || !Array.isArray(captions) || captions.length === 0) return [];

  // If captions is already grouped into blocks with .words, return as is
  if (captions[0]?.words && Array.isArray(captions[0].words)) {
    return captions;
  }

  const blocks = [];
  let currentWords = [];
  let blockStartMs = 0;

  for (const caption of captions) {
    const word = {
      text: caption.text || caption.word || '',
      startMs: caption.startMs ?? (caption.start != null ? Math.round(caption.start * 1000) : 0),
      endMs: caption.endMs ?? (caption.end != null ? Math.round(caption.end * 1000) : 0),
    };

    if (!word.text.trim()) continue;

    if (currentWords.length === 0) {
      currentWords = [word];
      blockStartMs = word.startMs;
      continue;
    }

    const currentLen = currentWords.reduce((acc, w) => acc + w.text.length + 1, 0);
    const durationMs = word.endMs - blockStartMs;

    if (currentLen + word.text.length > maxChars || durationMs > maxDurationMs) {
      blocks.push({
        startMs: currentWords[0].startMs,
        endMs: currentWords[currentWords.length - 1].endMs,
        words: currentWords,
      });
      currentWords = [word];
      blockStartMs = word.startMs;
    } else {
      currentWords.push(word);
    }
  }

  if (currentWords.length > 0) {
    blocks.push({
      startMs: currentWords[0].startMs,
      endMs: currentWords[currentWords.length - 1].endMs,
      words: currentWords,
    });
  }

  return blocks;
}

export function getActiveWordIndex(words, currentTimeMs) {
  if (!words || !Array.isArray(words) || words.length === 0) return 0;

  for (let i = 0; i < words.length; i++) {
    const word = words[i];
    const nextStart = i < words.length - 1 ? words[i + 1].startMs : word.endMs;
    if (currentTimeMs >= word.startMs && currentTimeMs < nextStart) {
      return i;
    }
  }

  if (currentTimeMs >= words[words.length - 1].endMs) {
    return words.length - 1;
  }

  return 0;
}
