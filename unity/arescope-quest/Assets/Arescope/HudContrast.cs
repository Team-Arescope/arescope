using System;
using Arescope.Hud;
using Genesis.RoomScan;
using UnityEngine;
using UnityEngine.Rendering;

namespace Arescope
{
    public sealed class HudContrast : MonoBehaviour
    {
        public ArescopeHudController hud;
        public Camera headsetCamera;
        public float interval=1, lumaThreshold=.62f, brightFraction=.70f, normalAlpha=.25f, brightAlpha=.48f;
        public PassthroughCameraProvider provider;
        RenderTexture small; Texture2D fallback; float next; bool busy, warned;
        readonly Vector3[] corners=new Vector3[4];
        async void Update()
        {
            if(busy || hud==null || Time.unscaledTime<next) return;
            next=Time.unscaledTime+interval;
            if(provider==null) provider=FindFirstObjectByType<PassthroughCameraProvider>();
            if(headsetCamera==null) headsetCamera=Camera.main;
            var frame=provider?.CurrentFrame;
            if(frame==null || headsetCamera==null)
            {
                if(!warned) { warned=true; ArescopeLog.Warn("contrast","camera frame unavailable; using normal backdrop"); }
                hud.SetCardBackdropAlpha("all",normalAlpha); return;
            }
            busy=true;
            try
            {
                if(small==null) { small=new RenderTexture(32,32,0,RenderTextureFormat.ARGB32,RenderTextureReadWrite.sRGB); small.Create(); }
                Graphics.Blit(frame,small);
                Color32[] pixels;
                if(SystemInfo.supportsAsyncGPUReadback)
                {
                    var request=await AsyncGPUReadback.RequestAsync(small,0,TextureFormat.RGBA32);
                    if(this==null || request.hasError) return;
                    var data=request.GetData<Color32>(); pixels=new Color32[data.Length]; data.CopyTo(pixels);
                }
                else
                {
                    if(fallback==null) fallback=new Texture2D(32,32,TextureFormat.RGBA32,false);
                    var old=RenderTexture.active;
                    try { RenderTexture.active=small; fallback.ReadPixels(new Rect(0,0,32,32),0,0); fallback.Apply(); pixels=fallback.GetPixels32(); }
                    finally { RenderTexture.active=old; }
                }
                if(hud==null || headsetCamera==null || pixels.Length<32*32) return;
                foreach(var panel in hud.GetPanelRects())
                {
                    if(panel.Value==null) continue;
                    panel.Value.GetWorldCorners(corners);
                    float xmin=1,ymin=1,xmax=0,ymax=0; bool inFront=true;
                    for(int i=0;i<4;++i)
                    {
                        var v=headsetCamera.WorldToViewportPoint(corners[i]); inFront &= v.z>0;
                        xmin=Mathf.Min(xmin,v.x); xmax=Mathf.Max(xmax,v.x); ymin=Mathf.Min(ymin,v.y); ymax=Mathf.Max(ymax,v.y);
                    }
                    if(!inFront) continue;
                    int bright=0,total=0;
                    int x0=Mathf.Clamp(Mathf.FloorToInt(xmin*32),0,31),x1=Mathf.Clamp(Mathf.CeilToInt(xmax*32),0,32);
                    int y0=Mathf.Clamp(Mathf.FloorToInt(ymin*32),0,31),y1=Mathf.Clamp(Mathf.CeilToInt(ymax*32),0,32);
                    for(int y=y0;y<y1;++y) for(int x=x0;x<x1;++x)
                    { var c=pixels[y*32+x]; if((.2126f*c.r+.7152f*c.g+.0722f*c.b)/255>=lumaThreshold) ++bright; ++total; }
                    hud.SetCardBackdropAlpha(panel.Key,total>0 && (float)bright/total>=brightFraction?brightAlpha:normalAlpha);
                }
            }
            catch(Exception e) { if(!warned) { warned=true; ArescopeLog.Warn("contrast",e.Message); } }
            finally { busy=false; }
        }
        void OnDestroy() { if(small!=null) { small.Release(); Destroy(small); } if(fallback!=null) Destroy(fallback); }
    }
}
