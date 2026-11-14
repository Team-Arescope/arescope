using System.Text;
using UnityEngine;
using UnityEngine.XR;
using Arescope.Hud;

namespace Arescope.Client
{
    [DisallowMultipleComponent]
    public sealed class CopilotHudBridge : MonoBehaviour
    {
        [SerializeField] private int controller = 5;
        [SerializeField] private float pressThreshold = 0.75f;
        [SerializeField] private float releaseThreshold = 0.35f;
        [SerializeField] private CopilotClient client;
        [SerializeField] private ArescopeHudController hud;

        private bool gripHeld;
        private readonly StringBuilder streamingAnswer = new StringBuilder(1024);

        public int ControllerNode => controller;
        public float PressThreshold => pressThreshold;
        public float ReleaseThreshold => releaseThreshold;

        private void Awake()
        {
            if (client == null)
            {
                client = GetComponent<CopilotClient>();
            }

            if (hud == null)
            {
                hud = GetComponent<ArescopeHudController>();
            }
        }

        private void OnEnable()
        {
            if (client == null)
            {
                client = GetComponent<CopilotClient>();
            }

            if (hud == null)
            {
                hud = GetComponent<ArescopeHudController>();
            }

            if (client != null)
            {
                client.StateChanged += HandleStateChanged;
                client.TranscriptReceived += HandleTranscriptReceived;
                client.AssistantDelta += HandleAssistantDelta;
                client.AssistantCompleted += HandleAssistantCompleted;
                client.ErrorOccurred += HandleErrorOccurred;
                client.SettingsApplied += HandleSettingsApplied;
                HandleStateChanged(client.State);
            }
        }

        private void OnDisable()
        {
            if (client != null)
            {
                client.StateChanged -= HandleStateChanged;
                client.TranscriptReceived -= HandleTranscriptReceived;
                client.AssistantDelta -= HandleAssistantDelta;
                client.AssistantCompleted -= HandleAssistantCompleted;
                client.ErrorOccurred -= HandleErrorOccurred;
                client.SettingsApplied -= HandleSettingsApplied;
            }

            gripHeld = false;
        }

        private void Update()
        {
            if (client == null)
            {
                return;
            }

            float grip = ReadGripAnalog();
            if (!gripHeld && grip >= pressThreshold)
            {
                gripHeld = true;
                streamingAnswer.Clear();
                client.StartRecording();
            }
            else if (gripHeld && grip <= releaseThreshold)
            {
                gripHeld = false;
                client.StopRecordingAndSend();
            }

            if (hud != null && client.State == CopilotState.Recording)
            {
                hud.SetVoiceState("LISTENING", client.CurrentMicLevel);
            }
        }

        private float ReadGripAnalog()
        {
            float xrGrip = 0f;
            var node = (XRNode)controller;
            var device = InputDevices.GetDeviceAtXRNode(node);
            if (device.isValid && device.TryGetFeatureValue(CommonUsages.grip, out float value))
            {
                xrGrip = Mathf.Max(xrGrip, value);
            }

            OVRInput.Controller ovrController = node == XRNode.LeftHand
                ? OVRInput.Controller.LTouch
                : OVRInput.Controller.RTouch;
            float ovrGrip = OVRInput.Get(OVRInput.Axis1D.PrimaryHandTrigger, ovrController);
            return Mathf.Clamp01(Mathf.Max(xrGrip, ovrGrip));
        }

        private void HandleStateChanged(CopilotState state)
        {
            if (hud == null)
            {
                return;
            }

            string label = state switch
            {
                CopilotState.Idle => "-",
                CopilotState.Recording => "LISTENING",
                CopilotState.Uploading => "TRANSCRIBING",
                CopilotState.Streaming => "THINKING",
                CopilotState.Speaking => "SPEAKING",
                CopilotState.Cancelled => "CANCELLED",
                CopilotState.Error => "ERROR",
                _ => "-"
            };

            float level = state == CopilotState.Recording && client != null ? client.CurrentMicLevel : 0f;
            hud.SetVoiceState(label, level);
        }

        private void HandleTranscriptReceived(string transcript)
        {
            streamingAnswer.Clear();
            if (hud != null && !string.IsNullOrWhiteSpace(transcript))
            {
                hud.SetAssistantText($"> {transcript}");
            }
        }

        private void HandleAssistantDelta(string delta)
        {
            if (string.IsNullOrEmpty(delta))
            {
                return;
            }

            streamingAnswer.Append(delta);
            if (hud != null)
            {
                hud.SetAssistantText(streamingAnswer.ToString());
            }
        }

        private void HandleAssistantCompleted(string fullText)
        {
            streamingAnswer.Clear();
            if (!string.IsNullOrEmpty(fullText))
            {
                streamingAnswer.Append(fullText);
            }

            if (hud != null)
            {
                hud.SetAssistantText(fullText ?? string.Empty);
            }
        }

        private void HandleErrorOccurred(string error)
        {
            if (hud != null && !string.IsNullOrWhiteSpace(error))
            {
                hud.ShowEvent(error, 4f);
            }
        }

        private void HandleSettingsApplied(CopilotClient.CopilotSettingsState settings)
        {
            if (hud == null || settings == null)
            {
                return;
            }

            hud.SetHudEnabled(settings.hud_enabled);
            hud.SetFollowMode(settings.hud_follow_mode);
        }
    }
}
