#ifndef ARESCOPE_BILLBOARD_INCLUDED
#define ARESCOPE_BILLBOARD_INCLUDED
// UV contains the four quad corners. Offset after the eye-specific view transform.
float3 ArescopeBillboardOffset(float3 viewPos, float2 corner, float pointSize)
{
    viewPos.xy += corner * pointSize * max(0.05, -viewPos.z);
    return viewPos;
}
#endif
