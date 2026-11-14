Shader "Arescope/Wire"
{
    Properties
    {
        _Color ("Tint", Color) = (1,1,1,1)
        _PointSize ("Billboard size", Float) = 0
        _UseVertexColor ("Use vertex color", Range(0,1)) = 0
    }
    SubShader
    {
        Tags { "RenderPipeline"="UniversalPipeline" "Queue"="Transparent" "RenderType"="Transparent" }
        Pass
        {
            Name "ArescopeUnlit"
            Tags { "LightMode"="SRPDefaultUnlit" }
            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off
            Cull Off
            HLSLPROGRAM
            #pragma vertex Vert
            #pragma fragment Frag
            #pragma multi_compile_instancing
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Assets/Arescope/Shaders/ArescopeBillboard.hlsl"
            CBUFFER_START(UnityPerMaterial)
                half4 _Color;
                float _PointSize;
                float _UseVertexColor;
            CBUFFER_END
            struct Attributes
            {
                float4 positionOS : POSITION;
                float2 uv : TEXCOORD0;
                half4 color : COLOR;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                half4 color : COLOR;
                UNITY_VERTEX_OUTPUT_STEREO
            };
            Varyings Vert(Attributes v)
            {
                Varyings o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                float3 viewPos = TransformWorldToView(TransformObjectToWorld(v.positionOS.xyz));
                viewPos = ArescopeBillboardOffset(viewPos, v.uv, _PointSize);
                o.positionCS = mul(UNITY_MATRIX_P, float4(viewPos, 1));
                o.color = _Color * lerp(half4(1,1,1,1), v.color, saturate(_UseVertexColor));
                return o;
            }
            half4 Frag(Varyings i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                return i.color;
            }
            ENDHLSL
        }
    }
    FallBack Off
}
