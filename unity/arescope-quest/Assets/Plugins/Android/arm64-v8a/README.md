Native binaries are resolved or built from licensed packages; none are fabricated.

After installing com.unity.xr.meta-openxr, copy its
Runtime/Plugins/android/arm64/libUnityARFoundationMeta.so here if Unity omits it.
RoomScan requires libxatlas.so for texture refinement (build it with the pinned
package setup wizard and the Unity Android NDK if the package does not supply it).

Verify the APK contains lib/arm64-v8a/libUnityARFoundationMeta.so and
lib/arm64-v8a/libxatlas.so. A .meta file alone does not provide a native library.
