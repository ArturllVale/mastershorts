import { useState } from 'react';

export function useStreamDownload() {
  const [downloadPct, setDownloadPct] = useState(null);

  const downloadClip = async (currentVideoUrl, fileName) => {
    try {
      setDownloadPct(0);
      const response = await fetch(currentVideoUrl);
      if (!response.ok) throw new Error('Download failed');
      const total = Number(response.headers.get('content-length')) || 0;
      let blob;
      // No body reader (old browser) or no length to measure against: fall
      // back to the plain path rather than lose the download.
      if (!response.body || !total) {
        blob = await response.blob();
      } else {
        const reader = response.body.getReader();
        const chunks = [];
        let received = 0;
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          chunks.push(value);
          received += value.length;
          setDownloadPct(Math.min(99, Math.round((received / total) * 100)));
        }
        blob = new Blob(chunks, { type: 'video/mp4' });
      }
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Download error:', err);
      window.open(currentVideoUrl, '_blank');
    } finally {
      setDownloadPct(null);
    }
  };

  return { downloadPct, downloadClip };
}
