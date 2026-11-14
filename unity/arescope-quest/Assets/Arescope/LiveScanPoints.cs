using System;
using System.Collections.Generic;
using Genesis.RoomScan;
using UnityEngine;
using UnityEngine.Rendering;

namespace Arescope
{
    public sealed class LiveScanPoints : MonoBehaviour
    {
        public Camera headsetCamera;
        public float interval=.2f, voxelSize=.035f, maxDistance=9, pointSize=.0045f;
        public int cacheCapacity=60000, renderCapacity=16000;
        public bool IsScanning { get; private set; }
        readonly Vector3[] sample=new Vector3[6000]; readonly Color32[] sampleColors=new Color32[6000];
        readonly Dictionary<long,int> voxels=new Dictionary<long,int>();
        readonly List<Vector3> cache=new List<Vector3>(); readonly List<Color32> cacheColors=new List<Color32>();
        readonly Plane[] planes=new Plane[6];
        GameObject root; Mesh mesh; Material material; float next; bool busy; int generation;
        public GameObject VisualRoot => root;
        public void Begin()
        {
            ++generation; voxels.Clear(); cache.Clear(); cacheColors.Clear(); IsScanning=true; next=0;
            Publish();
            if(root!=null) root.SetActive(true);
        }
        public void End() { IsScanning=false; ++generation; if(root!=null) root.SetActive(false); }
        async void Update()
        {
            if(!IsScanning || busy || Time.unscaledTime<next) return;
            next=Time.unscaledTime+interval; busy=true; int capturedGeneration=generation;
            try
            {
                int count=await ArescopeLiveCloud.SampleAsync(sample,sampleColors,sample.Length);
                if(this==null || !IsScanning || capturedGeneration!=generation) return;
                for(int i=0;i<count;++i)
                {
                    long key;
                    try { key=MinimapProjectionMath.VoxelKey(ArescopeFrame.ToMath(sample[i]),voxelSize); }
                    catch(ArgumentOutOfRangeException) { continue; }
                    if(voxels.ContainsKey(key)) continue;
                    if(cache.Count>=cacheCapacity) break;
                    voxels.Add(key,cache.Count); cache.Add(sample[i]); cacheColors.Add(sampleColors[i]);
                }
                if(count==0) ArescopeLog.Warn("points",ArescopeLiveCloud.LastReason);
                Publish();
            }
            catch(Exception e) { ArescopeLog.Exception("points",e); }
            finally { busy=false; }
        }
        void Publish()
        {
            if(root==null)
            {
                var shader=Resources.Load<Shader>("ArescopeWire") ?? Shader.Find("Arescope/Wire");
                if(shader==null) return;
                root=new GameObject("Arescope Live Points",typeof(MeshFilter),typeof(MeshRenderer));
                mesh=new Mesh { name="Arescope Live Billboards",indexFormat=IndexFormat.UInt32 }; mesh.MarkDynamic();
                material=ScanWireframe.MaterialFor(shader,new Color(1,1,1,.55f),pointSize,1);
                root.GetComponent<MeshFilter>().sharedMesh=mesh; var renderer=root.GetComponent<MeshRenderer>();
                renderer.sharedMaterial=material; renderer.shadowCastingMode=ShadowCastingMode.Off; renderer.receiveShadows=false;
            }
            ArescopeFrame.Apply(root.transform);
            var relocation=ArescopeFrame.Relocation(); var camera=headsetCamera!=null?headsetCamera:Camera.main;
            Vector3 head=camera!=null?camera.transform.position:Vector3.zero;
            if(camera!=null) GeometryUtility.CalculateFrustumPlanes(camera,planes);
            int capacity=Mathf.Max(1,renderCapacity), written=0;
            var p=new Vector3[capacity]; var c=new Color32[capacity];
            // Traverse the entire cache: offscreen entries never consume the render budget.
            int start=cache.Count==0?0:(Time.frameCount*997)%cache.Count;
            for(int j=0;j<cache.Count && written<capacity;++j)
            {
                int i=(start+j)%cache.Count; Vector3 world=relocation.MultiplyPoint3x4(cache[i]);
                if((world-head).sqrMagnitude>maxDistance*maxDistance) continue;
                bool inside=true;
                if(camera!=null) for(int k=0;k<6;++k) if(planes[k].GetDistanceToPoint(world)<-.01f) { inside=false; break; }
                if(!inside) continue;
                p[written]=cache[i]; c[written]=cacheColors[i]; ++written;
            }
            ScanWireframe.UpdateBillboards(mesh,p,c,written);
        }
        void LateUpdate() { if(root!=null && IsScanning) ArescopeFrame.Apply(root.transform); }
        void OnDisable() { End(); }
        void OnDestroy() { if(root!=null) Destroy(root); if(mesh!=null) Destroy(mesh); if(material!=null) Destroy(material); }
    }
}
