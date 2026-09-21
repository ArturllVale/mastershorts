-- CreateTable
CREATE TABLE "Job" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "status" TEXT NOT NULL DEFAULT 'queued',
    "cmd" TEXT,
    "env" TEXT,
    "output_dir" TEXT,
    "attestation" TEXT,
    "user_id" TEXT,
    "reservation_id" TEXT,
    "watermark" BOOLEAN NOT NULL DEFAULT false,
    "partial" TEXT,
    "webhook_url" TEXT,
    "webhook_secret" TEXT,
    "base_url" TEXT,
    "proxy_bytes" INTEGER,
    "proxy_route" TEXT,
    "ready_files" TEXT,
    "result" TEXT,
    "error" TEXT,
    "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "JobLog" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "job_id" TEXT NOT NULL,
    "message" TEXT NOT NULL,
    "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "JobLog_job_id_fkey" FOREIGN KEY ("job_id") REFERENCES "Job" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Clip" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "job_id" TEXT NOT NULL,
    "title" TEXT,
    CONSTRAINT "Clip_job_id_fkey" FOREIGN KEY ("job_id") REFERENCES "Job" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ClipAsset" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "clip_id" INTEGER NOT NULL,
    "file_path" TEXT NOT NULL,
    CONSTRAINT "ClipAsset_clip_id_fkey" FOREIGN KEY ("clip_id") REFERENCES "Clip" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "WebhookDelivery" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "job_id" TEXT NOT NULL,
    "status_code" INTEGER NOT NULL,
    "response_body" TEXT,
    CONSTRAINT "WebhookDelivery_job_id_fkey" FOREIGN KEY ("job_id") REFERENCES "Job" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);
