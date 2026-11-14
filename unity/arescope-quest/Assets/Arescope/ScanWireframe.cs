using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace Arescope
{
    public sealed class ScanWireframe : MonoBehaviour
    {
        public int maxTriangles=200000, maxPoints=12000;
        public float pointSize=.006f;
        public Color lineColor=new Color(.93f,.54f,.36f,.25f), pointColor=new Color(.97f,.91f,.87f,.55f);
        public GameObject VisualRoot { get; private set; }
        Mesh lineMesh, pointMesh;
        Material lineMaterial, pointMaterial;
        void EnsureRoot()
        {
            if(VisualRoot!=null) return;
            VisualRoot=new GameObject("Arescope Scan Visuals");
            // Exported positions are capture-world metres. Apply only A_now * inverse(A_capture).
            VisualRoot.transform.SetParent(null,false);
        }
        public bool SetMesh(Mesh source)
        {
            Clear();
            if(source==null || source.vertexCount==0) return false;
            var shader=Resources.Load<Shader>("ArescopeWire") ?? Shader.Find("Arescope/Wire");
            if(shader==null) { ArescopeLog.Warn("wire","Arescope/Wire missing"); return false; }
            EnsureRoot();
            var p=source.vertices; var c=source.colors32; var triangles=source.triangles;
            int triangleCount=triangles.Length/3, budget=Mathf.Max(1,maxTriangles);
            int step=Mathf.Max(1,Mathf.CeilToInt((float)triangleCount/budget));
            var remap=new Dictionary<int,int>(); var vertices=new List<Vector3>(); var edges=new HashSet<ulong>(); var lines=new List<int>();
            for(int t=0;t<triangleCount;t+=step)
            {
                int a=triangles[t*3],b=triangles[t*3+1],d=triangles[t*3+2];
                if(a<0 || b<0 || d<0 || a>=p.Length || b>=p.Length || d>=p.Length || a==b || a==d || b==d) continue;
                a=Remap(a,p,remap,vertices); b=Remap(b,p,remap,vertices); d=Remap(d,p,remap,vertices);
                Edge(a,b,edges,lines); Edge(b,d,edges,lines); Edge(d,a,edges,lines);
            }
            lineMesh=new Mesh { name="Arescope Lines", indexFormat=IndexFormat.UInt32 };
            lineMesh.SetVertices(vertices); lineMesh.SetIndices(lines.ToArray(),MeshTopology.Lines,0); lineMesh.RecalculateBounds();
            lineMaterial=MaterialFor(shader,lineColor,0,0);
            MakeRenderer("Wire",lineMesh,lineMaterial);
            int count=Mathf.Min(p.Length,Mathf.Max(0,maxPoints));
            var sample=new Vector3[count]; var colors=new Color32[count];
            for(int i=0;i<count;++i) { int at=(int)((long)i*p.Length/count); sample[i]=p[at]; colors[i]=c.Length==p.Length?c[at]:new Color32(255,255,255,255); }
            pointMesh=new Mesh { name="Arescope Final Points", indexFormat=IndexFormat.UInt32 };
            UpdateBillboards(pointMesh,sample,colors,count);
            pointMaterial=MaterialFor(shader,pointColor,pointSize,1);
            MakeRenderer("Points",pointMesh,pointMaterial);
            ArescopeFrame.Apply(VisualRoot.transform);
            ArescopeLog.Info("wire","triangles="+triangleCount+" edges="+edges.Count+" points="+count);
            return lines.Count>0;
        }
        static int Remap(int i,Vector3[] p,Dictionary<int,int> map,List<Vector3> result)
        { if(!map.TryGetValue(i,out int value)) { value=result.Count; map.Add(i,value); result.Add(p[i]); } return value; }
        static void Edge(int a,int b,HashSet<ulong> edges,List<int> lines)
        { ulong key=((ulong)(uint)Math.Min(a,b)<<32)|(uint)Math.Max(a,b); if(edges.Add(key)) { lines.Add(a); lines.Add(b); } }
        void MakeRenderer(string title,Mesh mesh,Material material)
        {
            var go=new GameObject(title,typeof(MeshFilter),typeof(MeshRenderer)); go.transform.SetParent(VisualRoot.transform,false);
            go.GetComponent<MeshFilter>().sharedMesh=mesh;
            var renderer=go.GetComponent<MeshRenderer>(); renderer.sharedMaterial=material;
            renderer.shadowCastingMode=ShadowCastingMode.Off; renderer.receiveShadows=false;
        }
        internal static Material MaterialFor(Shader shader,Color color,float size,float vertexColor)
        { var m=new Material(shader); m.SetColor("_Color",color); m.SetFloat("_PointSize",size); m.SetFloat("_UseVertexColor",vertexColor); return m; }
        internal static void UpdateBillboards(Mesh mesh,Vector3[] points,Color32[] colors,int count)
        {
            var v=new Vector3[count*4]; var uv=new Vector2[count*4]; var c=new Color32[count*4]; var indices=new int[count*6];
            for(int i=0;i<count;++i)
            {
                int q=i*4,k=i*6;
                for(int j=0;j<4;++j) { v[q+j]=points[i]; c[q+j]=colors[i]; }
                uv[q]=new Vector2(-.5f,-.5f); uv[q+1]=new Vector2(.5f,-.5f); uv[q+2]=new Vector2(.5f,.5f); uv[q+3]=new Vector2(-.5f,.5f);
                indices[k]=q; indices[k+1]=q+1; indices[k+2]=q+2; indices[k+3]=q; indices[k+4]=q+2; indices[k+5]=q+3;
            }
            mesh.Clear(); mesh.SetVertices(v,0,count*4); mesh.SetUVs(0,uv,0,count*4); mesh.SetColors(c,0,count*4);
            mesh.SetIndices(indices,0,count*6,MeshTopology.Triangles,0,false);
            mesh.RecalculateBounds(); var bounds=mesh.bounds; bounds.Expand(.2f); mesh.bounds=bounds;
        }
        void LateUpdate() { if(VisualRoot!=null) ArescopeFrame.Apply(VisualRoot.transform); }
        public void SetVisible(bool visible) { if(VisualRoot!=null) VisualRoot.SetActive(visible); }
        public void Clear()
        {
            if(VisualRoot!=null) { VisualRoot.SetActive(false); Destroy(VisualRoot); VisualRoot=null; }
            if(lineMesh!=null) Destroy(lineMesh); if(pointMesh!=null) Destroy(pointMesh);
            if(lineMaterial!=null) Destroy(lineMaterial); if(pointMaterial!=null) Destroy(pointMaterial);
        }
        void OnDestroy() { Clear(); }
    }
}
