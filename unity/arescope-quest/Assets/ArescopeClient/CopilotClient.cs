using System;
using System.Collections;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace Arescope.Client
{
    public enum CopilotState
    {
        Idle,
        Recording,
        Uploading,
        Streaming,
        Speaking,
        Cancelled,
        Error
    }

    [DisallowMultipleComponent]
    public sealed class CopilotClient : MonoBehaviour
    {
        private const int MaxUploadAudioBytes = 8 * 1024 * 1024;
        private const int MaxSpeechOutputBytes = 8 * 1024 * 1024;

        [SerializeField] private string baseUrl = "https://localhost";
        [SerializeField] private string bearerToken = "";
        [SerializeField] private float requestTimeoutSeconds = 45f;
        [SerializeField] private float settingsPollIntervalSeconds = 30f;
        [SerializeField] private float maxRecordingSeconds = 60f;
        [SerializeField] private int maxResponseBytes = 2097152;
        [SerializeField] private string chatPath = "/api/copilot/chat";
        [SerializeField] private int sampleRate = 16000;
        [SerializeField] private AudioSource audioSource;

        public event Action<CopilotState> StateChanged;
        public event Action<string> TranscriptReceived;
        public event Action<string> AssistantDelta;
        public event Action<string> AssistantCompleted;
        public event Action<string> ErrorOccurred;
        public event Action<CopilotSettingsState> SettingsApplied;

        public CopilotState State { get; private set; } = CopilotState.Idle;
        public string BaseUrl => baseUrl;
        public string Voice { get; private set; } = "male";
        public float Volume { get; private set; } = 1.0f;
        public bool HudEnabled { get; private set; } = true;
        public string HudFollowMode { get; private set; } = "smooth";
        public int SettingsVersion { get; private set; } = -1;
        public float CurrentMicLevel { get; private set; }

        private AudioClip recordingClip;
        private string activeMicDevice;
        private float recordingStartedAt;
        private int clampedRecordLimitSec = 60;
        private Coroutine pipelineCoroutine;
        private Coroutine settingsCoroutine;
        private UnityWebRequest activeRequest;
        private bool cancelRequested;
        private float[] levelProbeBuffer;

        [Serializable]
        public sealed class CopilotSettingsState
        {
            public int version;
            public string voice = "male";
            public float volume = 1.0f;
            public bool hud_enabled = true;
            public string hud_follow_mode = "smooth";
        }

        [Serializable]
        private sealed class SettingsEnvelope
        {
            public int version;
            public string voice;
            public float volume = 1.0f;
            public bool hud_enabled = true;
            public string hud_follow_mode;
            public CopilotSettingsState settings;
        }

        [Serializable]
        private sealed class SettingsAckRequest
        {
            public int version;
        }

        [Serializable]
        private sealed class TranscribeResponse
        {
            public string text;
            public string model;
        }

        [Serializable]
        private sealed class ChatRequest
        {
            public string text;
            public string context;
        }

        [Serializable]
        private sealed class SpeechRequest
        {
            public string text;
            public string voice;
        }

        [Serializable]
        private sealed class SseEventPayload
        {
            public string type;
            public string text;
            public string model;
            public string message;
        }

        public sealed class SseChunkParser
        {
            private readonly Decoder utf8Decoder = Encoding.UTF8.GetDecoder();
            private readonly StringBuilder lineBuffer = new StringBuilder(1024);
            private readonly StringBuilder dataLines = new StringBuilder(1024);
            private readonly StringBuilder accumulatedText = new StringBuilder(2048);
            private readonly int maxBytes;
            private readonly Action<string> onDelta;
            private readonly Action<string> onComplete;
            private readonly Action<string> onError;

            private int totalBytes;
            private char[] charScratch = new char[4096];

            public bool Completed { get; private set; }
            public bool HasError { get; private set; }
            public string ErrorMessage { get; private set; } = string.Empty;
            public string FullText => accumulatedText.ToString();
            public bool ByteLimitExceeded { get; private set; }

            public SseChunkParser(
                int maxBytes,
                Action<string> onDelta,
                Action<string> onComplete,
                Action<string> onError)
            {
                this.maxBytes = Mathf.Max(1024, maxBytes);
                this.onDelta = onDelta;
                this.onComplete = onComplete;
                this.onError = onError;
            }

            public bool Feed(byte[] bytes, int count)
            {
                if (bytes == null || count <= 0)
                {
                    return !ByteLimitExceeded;
                }

                totalBytes += count;
                if (totalBytes > maxBytes)
                {
                    ByteLimitExceeded = true;
                    HasError = true;
                    ErrorMessage = $"SSE response exceeded {maxBytes} bytes";
                    onError?.Invoke(ErrorMessage);
                    return false;
                }

                int maxChars = Encoding.UTF8.GetMaxCharCount(count);
                if (charScratch.Length < maxChars)
                {
                    charScratch = new char[maxChars];
                }

                int charsDecoded = utf8Decoder.GetChars(bytes, 0, count, charScratch, 0, false);
                AppendChars(charScratch, charsDecoded);
                return !HasError;
            }

            public void CompleteStream()
            {
                int tailChars = utf8Decoder.GetChars(Array.Empty<byte>(), 0, 0, charScratch, 0, true);
                if (tailChars > 0)
                {
                    AppendChars(charScratch, tailChars);
                }

                if (lineBuffer.Length > 0)
                {
                    ProcessLine(lineBuffer.ToString());
                    lineBuffer.Clear();
                }

                FlushEventBlock();
            }

            private void AppendChars(char[] chars, int count)
            {
                for (int i = 0; i < count; i++)
                {
                    char c = chars[i];
                    if (c == '\r')
                    {
                        continue;
                    }

                    if (c == '\n')
                    {
                        ProcessLine(lineBuffer.ToString());
                        lineBuffer.Clear();
                    }
                    else
                    {
                        lineBuffer.Append(c);
                    }
                }
            }

            private void ProcessLine(string line)
            {
                if (string.IsNullOrEmpty(line))
                {
                    FlushEventBlock();
                    return;
                }

                if (line.StartsWith(":", StringComparison.Ordinal))
                {
                    return;
                }

                if (line.StartsWith("data:", StringComparison.Ordinal))
                {
                    string payload = line.Length > 5 ? line.Substring(5) : string.Empty;
                    if (payload.StartsWith(" ", StringComparison.Ordinal))
                    {
                        payload = payload.Substring(1);
                    }

                    if (dataLines.Length > 0)
                    {
                        dataLines.Append('\n');
                    }

                    dataLines.Append(payload);
                }
            }

            private void FlushEventBlock()
            {
                if (dataLines.Length == 0)
                {
                    return;
                }

                string rawJson = dataLines.ToString().Trim();
                dataLines.Clear();
                if (string.IsNullOrEmpty(rawJson) || rawJson == "[DONE]")
                {
                    return;
                }

                SseEventPayload evt;
                try
                {
                    evt = JsonUtility.FromJson<SseEventPayload>(rawJson);
                }
                catch (Exception ex)
                {
                    HasError = true;
                    ErrorMessage = $"Malformed SSE JSON: {ex.Message}";
                    onError?.Invoke(ErrorMessage);
                    return;
                }

                if (evt == null || string.IsNullOrEmpty(evt.type))
                {
                    return;
                }

                switch (evt.type)
                {
                    case "text":
                        if (!string.IsNullOrEmpty(evt.text))
                        {
                            accumulatedText.Append(evt.text);
                            onDelta?.Invoke(evt.text);
                        }
                        break;

                    case "complete":
                        if (!string.IsNullOrEmpty(evt.text))
                        {
                            accumulatedText.Clear();
                            accumulatedText.Append(evt.text);
                        }
                        Completed = true;
                        onComplete?.Invoke(accumulatedText.ToString());
                        break;

                    case "error":
                        HasError = true;
                        ErrorMessage = string.IsNullOrEmpty(evt.message) ? "Copilot stream error" : evt.message;
                        onError?.Invoke(ErrorMessage);
                        break;
                }
            }
        }

        private sealed class SseDownloadHandler : DownloadHandlerScript
        {
            private readonly SseChunkParser parser;

            public SseDownloadHandler(SseChunkParser parser) : base(new byte[4096])
            {
                this.parser = parser;
            }

            protected override bool ReceiveData(byte[] data, int dataLength)
            {
                return parser.Feed(data, dataLength);
            }

            protected override void CompleteContent()
            {
                parser.CompleteStream();
            }
        }

        private void Awake()
        {
            if (audioSource == null)
            {
                audioSource = GetComponent<AudioSource>();
                if (audioSource == null)
                {
                    audioSource = gameObject.AddComponent<AudioSource>();
                    audioSource.playOnAwake = false;
                    audioSource.spatialBlend = 0f;
                }
            }

            var config = GetComponent<CopilotConnectionConfig>();
            if (config != null)
            {
                config.LoadResources();
                config.ApplyTo(this);
            }
        }

        private void OnEnable()
        {
            if (settingsCoroutine == null)
            {
                settingsCoroutine = StartCoroutine(PollSettingsLoop());
            }
        }

        private void OnDisable()
        {
            if (settingsCoroutine != null)
            {
                StopCoroutine(settingsCoroutine);
                settingsCoroutine = null;
            }

            Cancel();
        }

        private void Update()
        {
            if (State == CopilotState.Recording && recordingClip != null)
            {
                CurrentMicLevel = SampleRecentMicLevel();
                if (Time.unscaledTime - recordingStartedAt >= clampedRecordLimitSec)
                {
                    StopRecordingAndSend();
                }
            }
            else
            {
                CurrentMicLevel = 0f;
            }
        }

        public void ApplyConnectionConfig(string configuredBaseUrl, string configuredToken)
        {
            if (!string.IsNullOrWhiteSpace(configuredBaseUrl))
            {
                baseUrl = configuredBaseUrl.Trim().TrimEnd('/');
            }

            if (!string.IsNullOrWhiteSpace(configuredToken))
            {
                bearerToken = configuredToken.Trim();
            }
        }

        public bool StartRecording()
        {
            if (State == CopilotState.Recording || State == CopilotState.Uploading || State == CopilotState.Streaming)
            {
                return false;
            }

            if (audioSource != null && audioSource.isPlaying)
            {
                audioSource.Stop();
            }

            if (Microphone.devices == null || Microphone.devices.Length == 0)
            {
                Fail("No microphone available");
                return false;
            }

            cancelRequested = false;
            activeMicDevice = Microphone.devices[0];
            clampedRecordLimitSec = Mathf.Clamp(Mathf.CeilToInt(maxRecordingSeconds), 1, 120);
            int targetRate = Mathf.Clamp(sampleRate, 8000, 48000);
            recordingClip = Microphone.Start(activeMicDevice, false, clampedRecordLimitSec, targetRate);
            if (recordingClip == null)
            {
                Fail("Microphone failed to start");
                return false;
            }

            recordingStartedAt = Time.unscaledTime;
            CurrentMicLevel = 0f;
            SetState(CopilotState.Recording);
            return true;
        }

        public void StopRecordingAndSend(string optionalContext = null)
        {
            if (State != CopilotState.Recording)
            {
                return;
            }

            int position = Microphone.GetPosition(activeMicDevice);
            Microphone.End(activeMicDevice);

            if (recordingClip == null || position <= 0)
            {
                recordingClip = null;
                Fail("Empty voice recording");
                return;
            }

            int channels = Mathf.Max(1, recordingClip.channels);
            int freq = recordingClip.frequency > 0 ? recordingClip.frequency : Mathf.Clamp(sampleRate, 8000, 48000);
            int sampleFrames = Mathf.Min(position, recordingClip.samples);
            float[] interleaved = new float[sampleFrames * channels];
            recordingClip.GetData(interleaved, 0);
            Destroy(recordingClip);
            recordingClip = null;

            byte[] wavBytes = EncodeWavPcm16(interleaved, channels, freq);
            if (wavBytes == null || wavBytes.Length <= 44)
            {
                Fail("Empty WAV payload");
                return;
            }

            if (wavBytes.Length > MaxUploadAudioBytes)
            {
                Fail("Audio exceeds 8 MiB limit");
                return;
            }

            if (pipelineCoroutine != null)
            {
                StopCoroutine(pipelineCoroutine);
            }

            pipelineCoroutine = StartCoroutine(RunVoicePipeline(wavBytes, optionalContext));
        }

        public void SendTextPrompt(string userText, string optionalContext = null)
        {
            if (string.IsNullOrWhiteSpace(userText))
            {
                Fail("Prompt text is empty");
                return;
            }

            if (pipelineCoroutine != null)
            {
                StopCoroutine(pipelineCoroutine);
            }

            cancelRequested = false;
            pipelineCoroutine = StartCoroutine(RunChatAndSpeechPipeline(userText.Trim(), optionalContext));
        }

        public void Cancel()
        {
            cancelRequested = true;
            if (Microphone.IsRecording(activeMicDevice))
            {
                Microphone.End(activeMicDevice);
            }

            if (recordingClip != null)
            {
                Destroy(recordingClip);
                recordingClip = null;
            }

            if (activeRequest != null)
            {
                activeRequest.Abort();
                activeRequest.Dispose();
                activeRequest = null;
            }

            if (pipelineCoroutine != null)
            {
                StopCoroutine(pipelineCoroutine);
                pipelineCoroutine = null;
            }

            if (audioSource != null && audioSource.isPlaying)
            {
                audioSource.Stop();
            }

            if (State != CopilotState.Idle)
            {
                SetState(CopilotState.Cancelled);
            }
        }

        private IEnumerator RunVoicePipeline(byte[] wavBytes, string optionalContext)
        {
            SetState(CopilotState.Uploading);

            string transcript = null;
            string transcribeUrl = BuildUrl("/api/copilot/transcribe");
            using (var req = new UnityWebRequest(transcribeUrl, UnityWebRequest.kHttpVerbPOST))
            {
                req.uploadHandler = new UploadHandlerRaw(wavBytes) { contentType = "audio/wav" };
                req.downloadHandler = new DownloadHandlerBuffer();
                ApplyHeaders(req, "audio/wav");
                req.timeout = GetClampedTimeoutSeconds();

                activeRequest = req;
                yield return req.SendWebRequest();
                activeRequest = null;

                if (cancelRequested)
                {
                    pipelineCoroutine = null;
                    yield break;
                }

                if (req.result != UnityWebRequest.Result.Success)
                {
                    Fail($"ASR HTTP {req.responseCode}: {req.error}");
                    pipelineCoroutine = null;
                    yield break;
                }

                try
                {
                    var resp = JsonUtility.FromJson<TranscribeResponse>(req.downloadHandler.text);
                    transcript = resp != null ? resp.text?.Trim() : null;
                }
                catch (Exception ex)
                {
                    Fail($"ASR parse error: {ex.Message}");
                    pipelineCoroutine = null;
                    yield break;
                }
            }

            if (string.IsNullOrEmpty(transcript))
            {
                Fail("No speech recognized");
                pipelineCoroutine = null;
                yield break;
            }

            TranscriptReceived?.Invoke(transcript);
            yield return RunChatAndSpeechPipeline(transcript, optionalContext);
        }

        private IEnumerator RunChatAndSpeechPipeline(string promptText, string optionalContext)
        {
            SetState(CopilotState.Streaming);

            string chatUrl = BuildUrl(string.IsNullOrWhiteSpace(chatPath) ? "/api/copilot/chat" : chatPath);
            string bodyJson = JsonUtility.ToJson(new ChatRequest
            {
                text = promptText,
                context = string.IsNullOrEmpty(optionalContext) ? null : optionalContext
            });

            string completedText = null;
            string streamError = null;
            var parser = new SseChunkParser(
                Mathf.Max(4096, maxResponseBytes),
                delta => AssistantDelta?.Invoke(delta),
                full => completedText = full,
                err => streamError = err);

            using (var req = new UnityWebRequest(chatUrl, UnityWebRequest.kHttpVerbPOST))
            {
                byte[] jsonBytes = Encoding.UTF8.GetBytes(bodyJson);
                req.uploadHandler = new UploadHandlerRaw(jsonBytes) { contentType = "application/json" };
                req.downloadHandler = new SseDownloadHandler(parser);
                ApplyHeaders(req, "application/json");
                req.SetRequestHeader("Accept", "text/event-stream");
                req.timeout = GetClampedTimeoutSeconds();

                activeRequest = req;
                yield return req.SendWebRequest();
                activeRequest = null;

                if (cancelRequested)
                {
                    pipelineCoroutine = null;
                    yield break;
                }

                if (req.result != UnityWebRequest.Result.Success)
                {
                    Fail($"Chat HTTP {req.responseCode}: {req.error}");
                    pipelineCoroutine = null;
                    yield break;
                }
            }

            // Gate TTS strictly on SSE 'complete' event; partial streams never trigger speech.
            if (parser.HasError || !parser.Completed || string.IsNullOrWhiteSpace(completedText))
            {
                Fail(string.IsNullOrEmpty(streamError)
                    ? "Assistant stream ended before complete"
                    : streamError);
                pipelineCoroutine = null;
                yield break;
            }

            AssistantCompleted?.Invoke(completedText);
            yield return RunSpeechPlayback(completedText);
            pipelineCoroutine = null;
        }

        private IEnumerator RunSpeechPlayback(string textToSpeak)
        {
            SetState(CopilotState.Speaking);

            string speechUrl = BuildUrl("/api/copilot/speech");
            string bodyJson = JsonUtility.ToJson(new SpeechRequest
            {
                text = textToSpeak,
                voice = string.Equals(Voice, "female", StringComparison.OrdinalIgnoreCase) ? "female" : "male"
            });

            byte[] mp3Bytes;
            using (var req = new UnityWebRequest(speechUrl, UnityWebRequest.kHttpVerbPOST))
            {
                req.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(bodyJson))
                {
                    contentType = "application/json"
                };
                req.downloadHandler = new DownloadHandlerBuffer();
                ApplyHeaders(req, "application/json");
                req.timeout = GetClampedTimeoutSeconds();

                activeRequest = req;
                yield return req.SendWebRequest();
                activeRequest = null;

                if (cancelRequested)
                {
                    yield break;
                }

                if (req.result != UnityWebRequest.Result.Success)
                {
                    Fail($"TTS HTTP {req.responseCode}: {req.error}");
                    yield break;
                }

                mp3Bytes = req.downloadHandler.data;
            }

            if (mp3Bytes == null || mp3Bytes.Length == 0 || mp3Bytes.Length > MaxSpeechOutputBytes)
            {
                Fail("Invalid TTS audio payload");
                yield break;
            }

            string tempPath = Path.Combine(Application.temporaryCachePath, $"arescope_tts_{Guid.NewGuid():N}.mp3");
            AudioClip clip = null;
            try
            {
                File.WriteAllBytes(tempPath, mp3Bytes);
                string fileUri = new Uri(tempPath).AbsoluteUri;
                using (var audioReq = UnityWebRequestMultimedia.GetAudioClip(fileUri, AudioType.MPEG))
                {
                    yield return audioReq.SendWebRequest();
                    if (cancelRequested)
                    {
                        yield break;
                    }

                    if (audioReq.result != UnityWebRequest.Result.Success)
                    {
                        Fail($"MP3 decode error: {audioReq.error}");
                        yield break;
                    }

                    clip = DownloadHandlerAudioClip.GetContent(audioReq);
                }
            }
            finally
            {
                try
                {
                    if (File.Exists(tempPath))
                    {
                        File.Delete(tempPath);
                    }
                }
                catch (Exception)
                {
                    // Ignore temp file cleanup race.
                }
            }

            if (clip == null || audioSource == null)
            {
                Fail("Failed to bind TTS AudioClip");
                yield break;
            }

            audioSource.volume = Mathf.Clamp01(Volume);
            audioSource.clip = clip;
            audioSource.Play();

            while (!cancelRequested && audioSource.isPlaying)
            {
                yield return null;
            }

            audioSource.clip = null;
            Destroy(clip);

            if (!cancelRequested)
            {
                SetState(CopilotState.Idle);
            }
        }

        private IEnumerator PollSettingsLoop()
        {
            yield return null;
            while (enabled)
            {
                if (IsPollableEndpoint())
                {
                    yield return FetchAndApplySettings();
                }

                float waitSec = Mathf.Clamp(settingsPollIntervalSeconds, 5f, 300f);
                yield return new WaitForSecondsRealtime(waitSec);
            }
        }

        private IEnumerator FetchAndApplySettings()
        {
            string settingsUrl = BuildUrl("/api/copilot/settings");
            using (var req = UnityWebRequest.Get(settingsUrl))
            {
                ApplyHeaders(req, null);
                req.timeout = Mathf.Min(15, GetClampedTimeoutSeconds());
                yield return req.SendWebRequest();

                if (req.result != UnityWebRequest.Result.Success || string.IsNullOrWhiteSpace(req.downloadHandler.text))
                {
                    yield break;
                }

                SettingsEnvelope env;
                try
                {
                    env = JsonUtility.FromJson<SettingsEnvelope>(req.downloadHandler.text);
                }
                catch (Exception)
                {
                    yield break;
                }

                if (env == null)
                {
                    yield break;
                }

                var resolved = env.settings != null ? env.settings : new CopilotSettingsState
                {
                    version = env.version,
                    voice = env.voice,
                    volume = env.volume,
                    hud_enabled = env.hud_enabled,
                    hud_follow_mode = env.hud_follow_mode
                };
                if (resolved.version <= 0 && env.version > 0)
                {
                    resolved.version = env.version;
                }

                bool changed = resolved.version != SettingsVersion;
                ApplySettings(resolved);

                if (changed && resolved.version > 0)
                {
                    yield return AckSettings(resolved.version);
                }
            }
        }

        private IEnumerator AckSettings(int version)
        {
            string ackUrl = BuildUrl("/api/copilot/settings/ack");
            string payload = JsonUtility.ToJson(new SettingsAckRequest { version = version });
            using (var req = new UnityWebRequest(ackUrl, UnityWebRequest.kHttpVerbPOST))
            {
                req.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(payload))
                {
                    contentType = "application/json"
                };
                req.downloadHandler = new DownloadHandlerBuffer();
                ApplyHeaders(req, "application/json");
                req.timeout = Mathf.Min(15, GetClampedTimeoutSeconds());
                yield return req.SendWebRequest();
            }
        }

        private void ApplySettings(CopilotSettingsState s)
        {
            SettingsVersion = s.version;
            Voice = string.Equals(s.voice, "female", StringComparison.OrdinalIgnoreCase) ? "female" : "male";
            Volume = Mathf.Clamp01(s.volume);
            HudEnabled = s.hud_enabled;
            HudFollowMode = string.Equals(s.hud_follow_mode, "hard", StringComparison.OrdinalIgnoreCase)
                ? "hard"
                : "smooth";

            if (audioSource != null)
            {
                audioSource.volume = Volume;
            }

            SettingsApplied?.Invoke(new CopilotSettingsState
            {
                version = SettingsVersion,
                voice = Voice,
                volume = Volume,
                hud_enabled = HudEnabled,
                hud_follow_mode = HudFollowMode
            });
        }

        private bool IsPollableEndpoint()
        {
            if (string.IsNullOrWhiteSpace(baseUrl))
            {
                return false;
            }

            if (string.Equals(baseUrl.Trim().TrimEnd('/'), "https://localhost", StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            return true;
        }

        private string BuildUrl(string path)
        {
            string cleanBase = (baseUrl ?? string.Empty).Trim().TrimEnd('/');
            string cleanPath = path.StartsWith("/", StringComparison.Ordinal) ? path : "/" + path;
            return cleanBase + cleanPath;
        }

        private void ApplyHeaders(UnityWebRequest req, string contentType)
        {
            if (!string.IsNullOrWhiteSpace(contentType))
            {
                req.SetRequestHeader("Content-Type", contentType);
            }

            if (!string.IsNullOrWhiteSpace(bearerToken))
            {
                req.SetRequestHeader("Authorization", "Bearer " + bearerToken.Trim());
            }
        }

        private int GetClampedTimeoutSeconds()
        {
            return Mathf.Clamp(Mathf.RoundToInt(requestTimeoutSeconds), 1, 180);
        }

        private float SampleRecentMicLevel()
        {
            if (recordingClip == null)
            {
                return 0f;
            }

            int channels = Mathf.Max(1, recordingClip.channels);
            int window = 256 * channels;
            if (levelProbeBuffer == null || levelProbeBuffer.Length != window)
            {
                levelProbeBuffer = new float[window];
            }

            int pos = Microphone.GetPosition(activeMicDevice);
            int offset = pos - 256;
            if (offset < 0)
            {
                offset += recordingClip.samples;
            }

            if (offset < 0 || offset >= recordingClip.samples)
            {
                return 0f;
            }

            recordingClip.GetData(levelProbeBuffer, offset);
            float sumSq = 0f;
            for (int i = 0; i < levelProbeBuffer.Length; i++)
            {
                float s = levelProbeBuffer[i];
                sumSq += s * s;
            }

            float rms = Mathf.Sqrt(sumSq / levelProbeBuffer.Length);
            return Mathf.Clamp01(rms * 6f);
        }

        public static byte[] EncodeWavPcm16(float[] samples, int channels, int sampleRate)
        {
            if (samples == null || samples.Length == 0 || channels <= 0 || sampleRate <= 0)
            {
                return Array.Empty<byte>();
            }

            int frameCount = samples.Length / channels;
            int dataBytes = frameCount * 2;
            byte[] wav = new byte[44 + dataBytes];

            WriteAscii(wav, 0, "RIFF");
            WriteInt32(wav, 4, 36 + dataBytes);
            WriteAscii(wav, 8, "WAVE");
            WriteAscii(wav, 12, "fmt ");
            WriteInt32(wav, 16, 16);
            WriteInt16(wav, 20, 1);
            WriteInt16(wav, 22, 1);
            WriteInt32(wav, 24, sampleRate);
            WriteInt32(wav, 28, sampleRate * 2);
            WriteInt16(wav, 32, 2);
            WriteInt16(wav, 34, 16);
            WriteAscii(wav, 36, "data");
            WriteInt32(wav, 40, dataBytes);

            int dst = 44;
            for (int f = 0; f < frameCount; f++)
            {
                float mono = 0f;
                int baseIdx = f * channels;
                for (int c = 0; c < channels; c++)
                {
                    mono += samples[baseIdx + c];
                }
                mono /= channels;
                short pcm = (short)Mathf.RoundToInt(Mathf.Clamp(mono, -1f, 1f) * short.MaxValue);
                wav[dst++] = (byte)(pcm & 0xff);
                wav[dst++] = (byte)((pcm >> 8) & 0xff);
            }

            return wav;
        }

        private static void WriteAscii(byte[] dst, int offset, string text)
        {
            for (int i = 0; i < text.Length; i++)
            {
                dst[offset + i] = (byte)text[i];
            }
        }

        private static void WriteInt32(byte[] dst, int offset, int value)
        {
            dst[offset] = (byte)(value & 0xff);
            dst[offset + 1] = (byte)((value >> 8) & 0xff);
            dst[offset + 2] = (byte)((value >> 16) & 0xff);
            dst[offset + 3] = (byte)((value >> 24) & 0xff);
        }

        private static void WriteInt16(byte[] dst, int offset, short value)
        {
            dst[offset] = (byte)(value & 0xff);
            dst[offset + 1] = (byte)((value >> 8) & 0xff);
        }

        private void SetState(CopilotState next)
        {
            if (State == next)
            {
                return;
            }

            State = next;
            StateChanged?.Invoke(next);
        }

        private void Fail(string message)
        {
            SetState(CopilotState.Error);
            ErrorOccurred?.Invoke(message);
        }
    }
}
