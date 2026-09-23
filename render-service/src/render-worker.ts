import fs from "node:fs";
import path from "node:path";
import { selectComposition, renderMedia } from "@remotion/renderer";
import { getBundleLocation } from "./bundle.js";
import { renderJobs } from "./server.js";

export interface RenderParams {
  renderId: string;
  jobId: string;
  clipIndex: number;
  props: {
    videoUrl: string;
    durationInFrames: number;
    fps: number;
    width: number;
    height: number;
    subtitles: unknown;
    hook: unknown;
    effects: unknown;
  };
}

/**
 * Executes a Remotion render in the background.
 * Updates the in-memory render job map with progress and final status.
 */
export async function executeRender(params: RenderParams): Promise<void> {
  const { renderId, jobId, clipIndex, props } = params;
  const job = renderJobs.get(renderId);

  if (!job) {
    console.error(`[render-worker] Job ${renderId} not found in map`);
    return;
  }

  try {
    job.status = "rendering";
    job.progress = 0;

    const bundleLocation = getBundleLocation();

    // Select the composition with the provided input props
    const composition = await selectComposition({
      serveUrl: bundleLocation,
      id: "ShortVideo",
      inputProps: props,
    });

    // Determine output directory and file path
    const outputDir = process.env.SHARED_OUTPUT_DIR
      ? path.resolve(process.env.SHARED_OUTPUT_DIR)
      : process.env.OUTPUT_DIR
      ? path.resolve(process.env.OUTPUT_DIR)
      : path.resolve(import.meta.dirname, "../../output");

    const jobOutputDir = path.join(outputDir, jobId);
    fs.mkdirSync(jobOutputDir, { recursive: true });

    const outputFileName = `remotion_${clipIndex}_${renderId}.mp4`;
    const relativePath = path.posix.join(jobId, outputFileName);
    const outputLocation = path.join(jobOutputDir, outputFileName);

    const startTime = Date.now();
    console.log(
      `[render-worker] RENDER STARTED | renderId=${renderId} | jobId=${jobId} | clipIndex=${clipIndex} | durationInFrames=${props.durationInFrames} | fps=${props.fps}`
    );

    const timeoutMs = parseInt(process.env.RENDER_TIMEOUT_MS || "300000", 10);

    // Render the video
    await renderMedia({
      composition,
      serveUrl: bundleLocation,
      codec: "h264",
      crf: 22,
      outputLocation,
      timeoutInMilliseconds: timeoutMs,
      onProgress: ({ progress }) => {
        const percent = Math.round(progress * 100);
        job.progress = percent;

        if (percent % 25 === 0 && percent > 0 && percent < 100) {
          console.log(`[render-worker] RENDER PROGRESS | renderId=${renderId} | progress=${percent}%`);
        }
      },
    });

    const endTime = Date.now();
    const durationMs = endTime - startTime;

    // Success
    job.status = "done";
    job.progress = 100;
    job.outputUrl = relativePath;

    console.log(
      `[render-worker] RENDER COMPLETED | renderId=${renderId} | timeMs=${durationMs} | output=${outputLocation}`
    );
  } catch (err) {
    job.status = "error";
    job.error = err instanceof Error ? err.message : String(err);

    console.error(`[render-worker] RENDER FAILED | renderId=${renderId} | error:`, err);

    // Attempt to cleanup temporary output file if it exists
    try {
      const failedOutputDir = process.env.SHARED_OUTPUT_DIR
        ? path.resolve(process.env.SHARED_OUTPUT_DIR)
        : process.env.OUTPUT_DIR
        ? path.resolve(process.env.OUTPUT_DIR)
        : path.resolve(import.meta.dirname, "../../output");
      const failedLoc = path.join(failedOutputDir, jobId, `remotion_${clipIndex}_${renderId}.mp4`);
      if (fs.existsSync(failedLoc)) {
        fs.unlinkSync(failedLoc);
        console.log(`[render-worker] CLEANUP SUCCESS | renderId=${renderId} | deleted=${failedLoc}`);
      }
    } catch (cleanupErr) {
      console.error(`[render-worker] CLEANUP FAILED | renderId=${renderId} | error:`, cleanupErr);
    }
  }
}

