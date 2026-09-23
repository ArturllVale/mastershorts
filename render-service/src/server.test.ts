import { test, describe, before, after } from "node:test";
import assert from "node:assert/strict";
import { app, setIsReady, renderJobs } from "./server.js";
import http from "node:http";

let server: http.Server;
let port: number;
let baseUrl: string;

describe("Render Service API", () => {
  before(async () => {
    // Start the server on a random port for testing
    return new Promise<void>((resolve) => {
      server = app.listen(0, "127.0.0.1", () => {
        const address = server.address() as import("net").AddressInfo;
        port = address.port;
        baseUrl = `http://127.0.0.1:${port}`;
        resolve();
      });
    });
  });

  after(() => {
    server.close();
  });

  test("GET /health should return ok and ready status", async () => {
    setIsReady(false);
    const res = await fetch(`${baseUrl}/health`);
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.ok, true);
    assert.equal(data.ready, false);
  });

  test("GET /ready should return 503 if not ready", async () => {
    setIsReady(false);
    const res = await fetch(`${baseUrl}/ready`);
    assert.equal(res.status, 503);
    const data = await res.json();
    assert.equal(data.ok, false);
  });

  test("GET /ready should return 200 if ready", async () => {
    setIsReady(true);
    const res = await fetch(`${baseUrl}/ready`);
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.ok, true);
  });

  test("POST /render should return 503 if not ready", async () => {
    setIsReady(false);
    const res = await fetch(`${baseUrl}/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jobId: "job-1",
        clipIndex: 0,
        props: { videoUrl: "url", durationInFrames: 100, fps: 30, width: 100, height: 100 }
      })
    });
    assert.equal(res.status, 503);
  });

  test("POST /render should return 400 for invalid request", async () => {
    setIsReady(true);
    const res = await fetch(`${baseUrl}/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jobId: "" }) // Invalid empty jobId
    });
    assert.equal(res.status, 400);
  });

  test("POST /render should return 202 and queue render", async () => {
    setIsReady(true);
    const res = await fetch(`${baseUrl}/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jobId: "test-job",
        clipIndex: 0,
        props: { videoUrl: "test-url", durationInFrames: 100, fps: 30, width: 1080, height: 1920 }
      })
    });
    assert.equal(res.status, 202);
    const data = await res.json();
    assert.equal(data.status, "queued");
    assert.ok(data.renderId);

    // Verify it was added to the map
    const job = renderJobs.get(data.renderId);
    assert.ok(job);
    assert.equal(job.jobId, "test-job");
  });
});
