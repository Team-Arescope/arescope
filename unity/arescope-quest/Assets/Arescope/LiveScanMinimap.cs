using System;
using System.Collections.Generic;
using Genesis.RoomScan;
using UnityEngine;
using Arescope.Hud;

namespace Arescope
{
    public sealed class LiveScanMinimap : MonoBehaviour
    {
        public ArescopeHudController hud;
        public Transform headsetTransform;
        public float interval=1.5f, rangeMeters=10, heightBand=.03f;
        public int maxPoints=96, meshSampleBudget=20000;
        readonly Vector3[] sample=new Vector3[768]; readonly List<Vector2> points=new List<Vector2>(96);
        Mesh finalMesh; Vector3[] finalVertices; bool busy; float next; int generation;
        public void SetMesh(Mesh mesh)
        {
            finalMesh=mesh; finalVertices=mesh!=null?mesh.vertices:null; ++generation; next=0;
            if(hud!=null) hud.SetMapPoints(new Vector2[0],rangeMeters,true);
        }
        async void Update()
        {
            if(busy || hud==null || headsetTransform==null || Time.unscaledTime<next) return;
            busy=true; next=Time.unscaledTime+interval; int version=generation;
            try
            {
                var vertices=finalVertices;
                int count=vertices!=null?vertices.Length:await ArescopeLiveCloud.SampleAsync(sample,sample.Length);
                if(this==null || version!=generation || hud==null || headsetTransform==null) return;
                if(vertices==null) vertices=sample;
                int budget=finalMesh!=null?Mathf.Max(1,meshSampleBudget):sample.Length;
                int step=Mathf.Max(1,Mathf.CeilToInt((float)count/budget));
                points.Clear(); var relocation=ArescopeFrame.Relocation();
                Float3 head=ArescopeFrame.ToMath(headsetTransform.position), forward=ArescopeFrame.ToMath(headsetTransform.forward);
                for(int i=0;i<count && points.Count<maxPoints;i+=step)
                {
                    var world=relocation.MultiplyPoint3x4(vertices[i]);
                    if(MinimapProjectionMath.TryProject(ArescopeFrame.ToMath(world),head,forward,out float x,out float z,rangeMeters,heightBand))
                        points.Add(new Vector2(x,z));
                }
                hud.SetMapPoints(points,rangeMeters,true); hud.SetHeadingDeg(headsetTransform.eulerAngles.y);
            }
            catch(Exception e) { ArescopeLog.Exception("minimap",e); }
            finally { busy=false; }
        }
    }
}
