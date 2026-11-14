using System;
using UnityEngine;

namespace Arescope.Client
{
    [DisallowMultipleComponent]
    public sealed class CopilotConnectionConfig : MonoBehaviour
    {
        [SerializeField] private string endpointResourceName = "arescope-endpoint";
        [SerializeField] private string optionalTokenResourceName = "arescope-copilot-token";

        public string EndpointResourceName => endpointResourceName;
        public string OptionalTokenResourceName => optionalTokenResourceName;
        public string BaseUrl { get; private set; } = string.Empty;
        public string BearerToken { get; private set; } = string.Empty;
        public bool HasEndpoint => !string.IsNullOrWhiteSpace(BaseUrl);
        public bool HasToken => !string.IsNullOrWhiteSpace(BearerToken);

        [Serializable]
        private sealed class EndpointConfigPayload
        {
            public string baseUrl;
            public string url;
            public string endpoint;
            public string bearerToken;
            public string token;
        }

        private void Awake()
        {
            LoadResources();
            ApplyTo(GetComponent<CopilotClient>());
        }

        public bool LoadResources()
        {
            BaseUrl = string.Empty;
            BearerToken = string.Empty;

            if (!string.IsNullOrWhiteSpace(endpointResourceName))
            {
                var endpointAsset = Resources.Load<TextAsset>(endpointResourceName);
                if (endpointAsset != null && !string.IsNullOrWhiteSpace(endpointAsset.text))
                {
                    ParseEndpointText(endpointAsset.text, out var parsedUrl, out var parsedToken);
                    BaseUrl = parsedUrl;
                    if (!string.IsNullOrWhiteSpace(parsedToken))
                    {
                        BearerToken = parsedToken;
                    }
                }
            }

            if (!string.IsNullOrWhiteSpace(optionalTokenResourceName))
            {
                var tokenAsset = Resources.Load<TextAsset>(optionalTokenResourceName);
                if (tokenAsset != null && !string.IsNullOrWhiteSpace(tokenAsset.text))
                {
                    var trimmed = ExtractSingleValue(tokenAsset.text);
                    if (!string.IsNullOrWhiteSpace(trimmed))
                    {
                        BearerToken = trimmed;
                    }
                }
            }

            return HasEndpoint;
        }

        public void ApplyTo(CopilotClient client)
        {
            if (client == null)
            {
                return;
            }

            if (HasEndpoint || HasToken)
            {
                client.ApplyConnectionConfig(BaseUrl, BearerToken);
            }
        }

        public static void ParseEndpointText(string rawText, out string url, out string token)
        {
            url = string.Empty;
            token = string.Empty;
            if (string.IsNullOrWhiteSpace(rawText))
            {
                return;
            }

            var trimmed = rawText.Trim();
            if (trimmed.StartsWith("{", StringComparison.Ordinal))
            {
                try
                {
                    var payload = JsonUtility.FromJson<EndpointConfigPayload>(trimmed);
                    if (payload != null)
                    {
                        url = FirstNonEmpty(payload.baseUrl, payload.url, payload.endpoint);
                        token = FirstNonEmpty(payload.bearerToken, payload.token);
                        url = NormalizeBaseUrl(url);
                        token = token.Trim();
                        return;
                    }
                }
                catch (Exception)
                {
                    // Fall through to line-based parsing when JSON is partial or malformed.
                }
            }

            var lines = trimmed.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries);
            foreach (var rawLine in lines)
            {
                var line = rawLine.Trim();
                if (string.IsNullOrEmpty(line) || line.StartsWith("#", StringComparison.Ordinal))
                {
                    continue;
                }

                var eqIdx = line.IndexOf('=');
                if (eqIdx > 0)
                {
                    var key = line.Substring(0, eqIdx).Trim().ToLowerInvariant();
                    var val = line.Substring(eqIdx + 1).Trim();
                    if (key == "url" || key == "baseurl" || key == "base_url" || key == "endpoint")
                    {
                        url = NormalizeBaseUrl(val);
                        continue;
                    }

                    if (key == "token" || key == "bearertoken" || key == "bearer_token")
                    {
                        token = val;
                        continue;
                    }
                }

                if (string.IsNullOrEmpty(url))
                {
                    url = NormalizeBaseUrl(line);
                }
            }
        }

        private static string ExtractSingleValue(string rawText)
        {
            if (string.IsNullOrWhiteSpace(rawText))
            {
                return string.Empty;
            }

            var lines = rawText.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries);
            foreach (var rawLine in lines)
            {
                var line = rawLine.Trim();
                if (!string.IsNullOrEmpty(line) && !line.StartsWith("#", StringComparison.Ordinal))
                {
                    return line;
                }
            }

            return string.Empty;
        }

        private static string FirstNonEmpty(params string[] values)
        {
            foreach (var v in values)
            {
                if (!string.IsNullOrWhiteSpace(v))
                {
                    return v.Trim();
                }
            }

            return string.Empty;
        }

        private static string NormalizeBaseUrl(string rawUrl)
        {
            if (string.IsNullOrWhiteSpace(rawUrl))
            {
                return string.Empty;
            }

            var cleaned = rawUrl.Trim().TrimEnd('/');
            if (cleaned.EndsWith("/api/copilot/chat", StringComparison.OrdinalIgnoreCase))
            {
                cleaned = cleaned.Substring(0, cleaned.Length - "/api/copilot/chat".Length);
            }
            else if (cleaned.EndsWith("/api/copilot", StringComparison.OrdinalIgnoreCase))
            {
                cleaned = cleaned.Substring(0, cleaned.Length - "/api/copilot".Length);
            }

            return cleaned.TrimEnd('/');
        }
    }
}
