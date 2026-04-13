from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.calls.views import (
    CallViewSet,
    TranscriptChunkViewSet,
    analyze_call_view,
    upload_audio_and_transcribe_view,
    stream_chunk_view,
    live_assistant_view,
    live_start_view,
    live_pcm_chunk_view,
    live_stop_view,
)

router = DefaultRouter()
router.register(r"calls", CallViewSet, basename="calls")
router.register(r"transcripts", TranscriptChunkViewSet, basename="transcripts")

urlpatterns = [
    path("", include(router.urls)),
    path("calls/<int:call_id>/analyze/", analyze_call_view, name="analyze-call"),
    path("calls/<int:call_id>/upload-audio/", upload_audio_and_transcribe_view, name="upload-audio"),
    path("calls/<int:call_id>/stream-chunk/", stream_chunk_view, name="stream-chunk"),
    path("calls/<int:call_id>/assistant/", live_assistant_view, name="assistant"),

    path("calls/<int:call_id>/live/start/", live_start_view, name="live-start"),
    path("calls/<int:call_id>/live/pcm-chunk/", live_pcm_chunk_view, name="live-pcm-chunk"),
    path("calls/<int:call_id>/live/stop/", live_stop_view, name="live-stop"),
]