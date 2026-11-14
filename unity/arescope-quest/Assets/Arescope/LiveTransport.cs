using System;
using System.Text;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Networking;

namespace Arescope
{
    internal static class LiveTransport
    {
        [Serializable] sealed class Endpoint { public string baseUrl, origin, endpoint; }
        internal static bool Config(out string origin,out string token)
        {
            origin=Resources.Load<TextAsset>("arescope-endpoint")?.text.Trim();
            token=Resources.Load<TextAsset>("arescope-live-token")?.text.Trim();
            if(!string.IsNullOrEmpty(origin) && origin.StartsWith("{"))
            {
                try { var c=JsonUtility.FromJson<Endpoint>(origin); origin=c.baseUrl ?? c.origin ?? c.endpoint; }
                catch { origin=null; }
            }
            if(!Uri.TryCreate(origin,UriKind.Absolute,out var uri) || uri.Scheme!="https" || string.IsNullOrWhiteSpace(token)) return false;
            origin=uri.GetLeftPart(UriPartial.Authority);
            return true;
        }
        internal sealed class Response { public long Code; public bool Success; public string Text, Error; }
        internal static async Task<Response> Post(string path,byte[] body,string type,int timeout)
        {
            if(!Config(out string origin,out string token)) return new Response { Error="endpoint or token missing" };
            using(var request=new UnityWebRequest(origin+path,"POST"))
            {
                request.uploadHandler=new UploadHandlerRaw(body); request.downloadHandler=new DownloadHandlerBuffer(); request.timeout=timeout;
                request.SetRequestHeader("Authorization","Bearer "+token); request.SetRequestHeader("Content-Type",type);
                try
                {
                    var op=request.SendWebRequest(); while(!op.isDone) await Task.Yield();
                    return new Response { Code=request.responseCode, Success=request.result==UnityWebRequest.Result.Success,
                        Text=request.downloadHandler.text, Error=request.error };
                }
                catch(Exception e) { return new Response { Code=request.responseCode, Error=e.Message }; }
            }
        }
        internal static byte[] Utf8(string text) => Encoding.UTF8.GetBytes(text);
    }
}
