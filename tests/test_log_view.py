from log_view import friendly_log_line, friendly_logs

# Raw lines captured from a real production job.
RAW_JOB = [
    "Job started by worker.",
    "🎙️  Transcribing video...",
    "🎙️ Transcribing… 25% (3s)",
    "🎙️ Transcribing… 100% (7s)",
    "🎙️ [ASR] parakeet ok: lang=es segments=43",
    "🔥 Found 2 viral clips!",
    "🎬 Processing Clip 1: 0.004s - 35.336s",
    "🎞️ [Encoder] video encoder: h264_nvenc (FFMPEG_ENCODER=auto)",
    "🎬 Processing clip: output/e7f00666/temp_e7f00666_agente-ia_clip_1.mp4",
    "✅ Found 2 scenes.",
    "🧠 Step 2: Preparing Active Tracking...",
    "🤖 Step 3: Analyzing Scenes for Strategy (Single vs Group)...",
    "✂️ Step 4: Processing video frames...",
    "🔊 Step 5: Extracting audio...",
    "✨ Step 6: Merging...",
    "✅ Clip saved to output/e7f00666/e7f00666_agente-ia_clip_1.mp4",
    "✅ Clip 1 ready: output/e7f00666/e7f00666_agente-ia_clip_1.mp4",
    "Process finished successfully.",
]


def test_real_job_produces_clean_user_view():
    assert friendly_logs(RAW_JOB) == [
        "🚀 Iniciando processamento do vídeo...",
        "🎙️ Iniciando transcrição do áudio...",
        "🎙️ Transcrição em andamento: 25%",
        "🎙️ Transcrição em andamento: 100%",
        "🔥 2 momentos virais identificados!",
        "🎬 Gerando corte 1…",
        "✅ Corte 1 pronto!",
        "🎉 Processamento concluído com sucesso!",
    ]


def test_download_and_transcription_logs():
    raw = [
        "📥 Downloading video from YouTube...",
        "[download]  25.0% of ~50.00MiB at 5.00MiB/s",
        "📥 Baixando vídeo: 50%",
        "✅ Download succeeded (direct).",
        "🎙️ Iniciando transcrição do áudio...",
        "🎙️ Transcrição iniciada com sucesso!",
        "🎙️ Transcrição em andamento: 75% (5s)",
        "Detected language 'pt', 12 segments",
    ]
    assert friendly_logs(raw) == [
        "📥 Iniciando download do vídeo...",
        "📥 Baixando vídeo: 25.0%",
        "📥 Baixando vídeo: 50%",
        "✅ Download concluído com sucesso!",
        "🎙️ Iniciando transcrição do áudio...",
        "🎙️ Transcrição iniciada com sucesso!",
        "🎙️ Transcrição em andamento: 75%",
        "✅ Transcrição concluída com sucesso!",
    ]


def test_no_paths_ever_leak():
    for line in friendly_logs(RAW_JOB):
        assert "output/" not in line
        assert ".mp4" not in line


def test_timing_and_hardware_log_lines():
    line_gpu = "⏱️ Tempo total de processamento: 2m 15s (GPU - NVIDIA NVENC)"
    assert friendly_log_line(line_gpu) == "⏱️ Tempo total: 2m 15s (GPU - NVIDIA NVENC)"

    line_cpu = "⏱️ Tempo total de processamento: 45s (CPU - libx264)"
    assert friendly_log_line(line_cpu) == "⏱️ Tempo total: 45s (CPU - libx264)"

    line_raw = "⏱️  Total execution time: 135.20s"
    assert friendly_log_line(line_raw) == "⏱️ Tempo total: 135.20s"


def test_technical_lines_are_hidden():
    assert friendly_log_line("🎙️ [ASR] parakeet ok: lang=es segments=43") is None
    assert friendly_log_line("🎞️ [Encoder] video encoder: h264_nvenc") is None
    assert friendly_log_line("🧠 Step 2: Preparing Active Tracking...") is None
    assert friendly_log_line("yt-dlp downloading format 137") is None


def test_errors_kept_without_paths():
    assert friendly_log_line("Process failed with exit code 1") == \
        "❌ Ocorreu uma falha no processamento."
    out = friendly_log_line("❌ Could not read output/abc/clip.mp4")
    assert out is not None and "output/" not in out


def test_consecutive_duplicates_collapse():
    logs = ["🎙️  Transcribing video...", "🎙️  Transcribing audio from: x.mp4"]
    assert friendly_logs(logs) == ["🎙️ Iniciando transcrição do áudio..."]
