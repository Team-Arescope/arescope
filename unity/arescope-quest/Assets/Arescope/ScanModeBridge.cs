using System;
using System.Threading.Tasks;
using Arescope.Hud;
using Genesis.RoomScan;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.XR;

namespace Arescope
{
    public sealed class ScanModeBridge : MonoBehaviour
    {
        public ViewModeController modes;
        public ArescopeHudController hud;
        public Camera headsetCamera;
        public OVRPassthroughLayer passthroughLayer;
        public LiveScanMinimap minimap;
        public ScanWireframe wireframe;
        public LiveScanPoints livePoints;
        public float resetHoldSeconds=1.2f;
        public bool Busy { get; private set; }
        public Mesh FinalMesh { get; private set; }
        bool previousX, previousY, resetFired, combo; float yHeld;
        void Awake()
        {
            if(headsetCamera==null) headsetCamera=Camera.main;
            if(passthroughLayer==null) passthroughLayer=FindFirstObjectByType<OVRPassthroughLayer>();
            if(modes==null) modes=GetComponent<ViewModeController>() ?? gameObject.AddComponent<ViewModeController>();
            if(hud==null) hud=GetComponent<ArescopeHudController>();
            if(minimap==null) minimap=GetComponent<LiveScanMinimap>();
            if(wireframe==null) wireframe=GetComponent<ScanWireframe>() ?? gameObject.AddComponent<ScanWireframe>();
            if(livePoints==null) livePoints=GetComponent<LiveScanPoints>() ?? gameObject.AddComponent<LiveScanPoints>();
            livePoints.headsetCamera=headsetCamera;
            ConfigureView(); modes.Switch(ViewMode.Passthrough);
        }
        void ConfigureView() => modes.Configure(headsetCamera,passthroughLayer,null,wireframe.VisualRoot);
        void Update()
        {
            var left=InputDevices.GetDeviceAtXRNode(XRNode.LeftHand);
            left.TryGetFeatureValue(CommonUsages.primaryButton,out bool x);
            left.TryGetFeatureValue(CommonUsages.secondaryButton,out bool y);
            if(x && y) combo=true;
            // Commit taps on release, so a log-upload chord cannot also start/reset a scan.
            if(y && !x && !combo && !Busy)
            {
                yHeld+=Time.unscaledDeltaTime;
                if(!resetFired && yHeld>=resetHoldSeconds) { resetFired=true; ResetScan(); }
            }
            if(!y && previousY)
            {
                if(!resetFired && !combo && !Busy) ToggleView();
                yHeld=0; resetFired=false;
            }
            if(!x && previousX && !combo && !y && !Busy) StartOrFinishScan();
            if(!x && !y) combo=false;
            previousX=x; previousY=y;
        }
        public async void StartOrFinishScan()
        {
            if(Busy) return;
            Busy=true;
            try
            {
                var scanner=RoomScanner.Instance;
                if(scanner==null || RoomScanSession.Instance==null) throw new InvalidOperationException("RoomScan session unavailable");
                if(!scanner.IsScanning)
                {
                    wireframe.Clear(); if(FinalMesh!=null) Destroy(FinalMesh); FinalMesh=null;
                    ConfigureView(); modes.Switch(ViewMode.Passthrough); minimap?.SetMesh(null);
                    LiveFrameSender.ResetSession();
                    ArescopeFrame.Capture();
                    await RoomScanSession.Instance.StartScanAsync();
                    if(this==null) return;
                    if(!scanner.IsScanning) throw new InvalidOperationException("scanner did not enter scanning state");
                    scanner.SetRenderMode(ScanRenderMode.None); livePoints.Begin();
                    modes.Configure(headsetCamera,passthroughLayer,null,livePoints.VisualRoot);
                    modes.Switch(ViewMode.Mixed);
                    hud?.ShowEvent("Scan started"); ArescopeLog.Info("scan","started");
                }
                else await FinishAsync(scanner);
            }
            catch(Exception e) { ArescopeLog.Exception("scan",e); hud?.ShowEvent(e.Message); }
            finally { Busy=false; }
        }
        async Task FinishAsync(RoomScanner scanner)
        {
            livePoints.End(); hud?.ShowEvent("Processing scan");
            Mesh mesh=null;
            try
            {
                // StopScanning can release volumes: every GPU/CPU snapshot precedes it.
                var data=await ArescopeMeshExport.ReadAsync(200000,600000);
                if(this==null) return;
                var textured=ArescopeTexturedMesh.Read();
                if(data!=null) mesh=Build(data.Positions,data.Indices,data.Colors);
                else if(textured!=null) mesh=Build(textured.Positions,textured.Indices,null);
                else if(scanner.RefinedMesh!=null) mesh=Instantiate(scanner.RefinedMesh);
                GetComponent<MeshUploader>()?.Capture(mesh,textured);
            }
            finally { scanner.StopScanning(); }
            if(mesh==null || mesh.vertexCount==0)
            {
                if(mesh!=null) Destroy(mesh);
                hud?.ShowEvent("Empty scan: "+ArescopeMeshExport.LastReason); ConfigureView(); modes.Switch(ViewMode.Passthrough); return;
            }
            FinalMesh=mesh;
            if(!wireframe.SetMesh(mesh)) throw new InvalidOperationException("wireframe could not be built");
            ConfigureView(); modes.Switch(ViewMode.Scan); minimap?.SetMesh(mesh);
            hud?.ShowEvent("Scan ready"); ArescopeLog.Info("scan","finalized vertices="+mesh.vertexCount);
            var uploader=GetComponent<MeshUploader>(); if(uploader!=null) _=uploader.UploadAsync();
        }
        static Mesh Build(Vector3[] p,int[] indices,Color32[] colors)
        {
            var mesh=new Mesh { name="Arescope Final Scan",indexFormat=IndexFormat.UInt32 };
            mesh.vertices=p; mesh.triangles=indices;
            if(colors!=null && colors.Length==p.Length) mesh.colors32=colors;
            mesh.RecalculateBounds(); return mesh;
        }
        void ToggleView()
        {
            ConfigureView();
            if(RoomScanner.Instance!=null && RoomScanner.Instance.IsScanning)
            {
                // Live cloud has its own root and stays visible during this passthrough toggle.
                modes.Configure(headsetCamera,passthroughLayer,null,livePoints.VisualRoot);
                // Mixed/Scan both keep live geometry enabled while toggling passthrough.
                modes.Switch(modes.CurrentMode==ViewMode.Scan?ViewMode.Mixed:ViewMode.Scan);
            }
            else if(FinalMesh!=null) modes.Switch(ModePolicy.Next(modes.CurrentMode));
        }
        public async void ResetScan()
        {
            if(Busy) return; Busy=true;
            try
            {
                livePoints.End();
                var scanner=RoomScanner.Instance;
                if(scanner!=null && scanner.IsScanning) scanner.StopScanning();
                if(RoomScanSession.Instance!=null) await RoomScanSession.Instance.UnloadActiveScanAsync();
                if(this==null) return;
                wireframe.Clear(); minimap?.SetMesh(null);
                if(FinalMesh!=null) Destroy(FinalMesh); FinalMesh=null;
                GetComponent<MeshUploader>()?.ClearCapture();
                ConfigureView(); modes.Switch(ViewMode.Passthrough);
                LiveFrameSender.ResetSession();
                hud?.ShowEvent("Scan reset"); ArescopeLog.Info("scan","reset");
            }
            catch(Exception e) { ArescopeLog.Exception("scan-reset",e); }
            finally { Busy=false; }
        }
        void OnDestroy() { if(FinalMesh!=null) Destroy(FinalMesh); }
    }
}
