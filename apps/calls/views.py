from pathlib import Path
import base64
import io
import tempfile
import uuid
import wave

from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from apps.calls.models import Call, TranscriptChunk, LiveCallSession
from apps.calls.serializers.call_serializer import CallSerializer
from apps.calls.serializers.transcript_serializer import TranscriptChunkSerializer
from apps.analysis.models import CallAnalysis
from apps.analysis.serializers.call_analysis_serializer import CallAnalysisSerializer
from apps.analysis.services.call_analysis_service import CallAnalysisService
from apps.analysis.services.whisper_service import WhisperService


def normalize_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def build_transcript_text(chunks) -> str:
    texts = []
    for chunk in chunks:
        text = normalize_text(chunk.text)
        if text and not chunk.is_partial:
            texts.append(text)
    return " ".join(texts).strip()


def extract_new_portion(existing_text: str, incoming_text: str, max_window: int = 120) -> str:
    existing = normalize_text(existing_text)
    incoming = normalize_text(incoming_text)

    if not incoming:
        return ""

    if not existing:
        return incoming

    existing_tail = existing[-max_window:]

    if incoming.lower() == existing_tail.lower():
        return ""

    if incoming.lower() in existing_tail.lower():
        return ""

    max_overlap = 0
    search_len = min(len(existing_tail), len(incoming), max_window)

    for i in range(1, search_len + 1):
        if existing_tail[-i:].lower() == incoming[:i].lower():
            max_overlap = i

    candidate = incoming[max_overlap:].strip()

    if not candidate and len(incoming.split()) >= 3:
        return incoming

    return candidate


def get_next_sequence(call: Call) -> int:
    last_chunk = TranscriptChunk.objects.filter(call=call).order_by("-sequence_number", "-created_at").first()
    return 1 if not last_chunk else last_chunk.sequence_number + 1


def serialize_transcript_segments(chunks):
    return [
        {
            "id": chunk.id,
            "speaker": chunk.speaker,
            "text": chunk.text,
            "sequence_number": chunk.sequence_number,
            "timestamp_seconds": chunk.timestamp_seconds,
            "is_partial": chunk.is_partial,
            "source": chunk.source,
            "created_at": chunk.created_at.isoformat() if chunk.created_at else None,
        }
        for chunk in chunks
    ]


def assistant_payload(call: Call):
    chunks = TranscriptChunk.objects.filter(call=call).order_by("sequence_number", "created_at")
    transcript_text = build_transcript_text(chunks)
    analysis = CallAnalysis.objects.filter(call=call).last()

    return {
        "call_id": call.id,
        "call_status": call.status,
        "transcript": transcript_text,
        "transcript_segments": serialize_transcript_segments(chunks),
        "analysis": CallAnalysisSerializer(analysis).data if analysis else None,
    }


def pcm_bytes_to_wav_file(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1, sampwidth: int = 2) -> str:
    temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    temp_wav.close()

    with wave.open(temp_wav.name, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)

    return temp_wav.name


class CallViewSet(viewsets.ModelViewSet):
    queryset = Call.objects.all().order_by("-created_at")
    serializer_class = CallSerializer
    permission_classes = [AllowAny]


class TranscriptChunkViewSet(viewsets.ModelViewSet):
    queryset = TranscriptChunk.objects.all().order_by("sequence_number", "created_at")
    serializer_class = TranscriptChunkSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        chunk = serializer.save(source="manual", is_partial=False)
        chunk.call.status = "analyzing"
        chunk.call.save(update_fields=["status"])

        CallAnalysisService.analyze_call(chunk.call)

        chunk.call.status = "completed"
        chunk.call.save(update_fields=["status"])


@api_view(["POST"])
@permission_classes([AllowAny])
def analyze_call_view(request, call_id):
    try:
        call = Call.objects.get(id=call_id)
    except Call.DoesNotExist:
        return Response({"error": "Call not found"}, status=status.HTTP_404_NOT_FOUND)

    call.status = "analyzing"
    call.save(update_fields=["status"])

    analysis = CallAnalysisService.analyze_call(call)

    call.status = "completed"
    call.save(update_fields=["status"])

    return Response(CallAnalysisSerializer(analysis).data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser])
def upload_audio_and_transcribe_view(request, call_id):
    try:
        call = Call.objects.get(id=call_id)
    except Call.DoesNotExist:
        return Response({"error": "Call not found"}, status=status.HTTP_404_NOT_FOUND)

    audio_file = request.FILES.get("audio_file")
    if not audio_file:
        return Response({"error": "audio_file is required"}, status=status.HTTP_400_BAD_REQUEST)

    call.audio_file = audio_file
    call.status = "transcribing"
    call.save(update_fields=["audio_file", "status"])

    TranscriptChunk.objects.filter(call=call).delete()

    try:
        result = WhisperService.transcribe_audio(call.audio_file.path)
        full_text = normalize_text(result.get("text", ""))
        segments = result.get("segments", [])

        if segments:
            for idx, segment in enumerate(segments, start=1):
                text = normalize_text(segment.get("text", ""))
                if text:
                    TranscriptChunk.objects.create(
                        call=call,
                        speaker="caller",
                        text=text,
                        sequence_number=idx,
                        timestamp_seconds=float(segment.get("start", 0) or 0),
                        is_partial=False,
                        source="recorded_upload",
                    )
        elif full_text:
            TranscriptChunk.objects.create(
                call=call,
                speaker="caller",
                text=full_text,
                sequence_number=1,
                timestamp_seconds=0,
                is_partial=False,
                source="recorded_upload",
            )

        call.status = "analyzing"
        call.save(update_fields=["status"])

        analysis = CallAnalysisService.analyze_call(call)

        call.status = "completed"
        call.save(update_fields=["status"])

        payload = assistant_payload(call)
        payload["message"] = "Audio uploaded, transcribed, and analyzed successfully"
        payload["analysis"] = CallAnalysisSerializer(analysis).data
        return Response(payload, status=status.HTTP_200_OK)

    except Exception as e:
        call.status = "failed"
        call.save(update_fields=["status"])
        return Response(
            {"error": f"Transcription failed: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def live_start_view(request, call_id):
    try:
        call = Call.objects.get(id=call_id)
    except Call.DoesNotExist:
        return Response({"error": "Call not found"}, status=status.HTTP_404_NOT_FOUND)

    session, _ = LiveCallSession.objects.update_or_create(
        call=call,
        defaults={
            "session_key": str(uuid.uuid4()),
            "sample_rate": 16000,
            "channels": 1,
            "status": "active",
            "pcm_buffer": b"",
            "last_sequence_number": 0,
            "last_transcript_text": "",
            "ended_at": None,
        },
    )

    print("PCM DEBUG live_start_view call_id:", call_id)
    print("PCM DEBUG session_key:", session.session_key)

    call.status = "live"
    call.save(update_fields=["status"])

    return Response(
        {
            "message": "Live PCM session started",
            "session_key": session.session_key,
            "sample_rate": session.sample_rate,
            "channels": session.channels,
        },
        status=status.HTTP_200_OK,
           
    )
    


@api_view(["POST"])
@permission_classes([AllowAny])
def live_pcm_chunk_view(request, call_id):
    try:
        call = Call.objects.get(id=call_id)
        session = LiveCallSession.objects.get(call=call, status="active")
    except Call.DoesNotExist:
        return Response({"error": "Call not found"}, status=status.HTTP_404_NOT_FOUND)
    except LiveCallSession.DoesNotExist:
        return Response({"error": "Live session not active"}, status=status.HTTP_400_BAD_REQUEST)

    session_key = request.data.get("session_key")
    sequence_number = request.data.get("sequence_number")
    pcm_b64 = request.data.get("pcm_data")
    speaker = request.data.get("speaker", "caller")

    print("PCM DEBUG live_pcm_chunk_view call_id:", call_id)
    print("PCM DEBUG session_key from request:", session_key)
    print("PCM DEBUG sequence_number:", sequence_number)
    print("PCM DEBUG speaker:", speaker)
    print("PCM DEBUG pcm_b64 length:", len(pcm_b64) if pcm_b64 else 0)

    if not session_key or session_key != session.session_key:
        return Response({"error": "Invalid session_key"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        sequence_number = int(sequence_number)
    except (TypeError, ValueError):
        return Response({"error": "sequence_number must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

    if sequence_number <= session.last_sequence_number:
        payload = assistant_payload(call)
        payload["message"] = "Duplicate or old PCM chunk ignored"
        payload["chunk_text"] = ""
        return Response(payload, status=status.HTTP_200_OK)

    if not pcm_b64:
        return Response({"error": "pcm_data is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        pcm_bytes = base64.b64decode(pcm_b64)
    except Exception:
        return Response({"error": "Invalid pcm_data encoding"}, status=status.HTTP_400_BAD_REQUEST)

    print("PCM DEBUG decoded pcm bytes:", len(pcm_bytes))

    existing_buffer = session.pcm_buffer or b""
    new_buffer = existing_buffer + pcm_bytes
    print("PCM DEBUG accumulated pcm buffer bytes:", len(new_buffer))

    session.pcm_buffer = new_buffer
    session.last_sequence_number = sequence_number
    session.save(update_fields=["pcm_buffer", "last_sequence_number", "updated_at"])

    # Wait until we have enough audio (~3 seconds at 16k mono s16le = 96000 bytes)
    if len(new_buffer) < 96000:
        payload = assistant_payload(call)
        payload["message"] = "PCM chunk buffered"
        payload["chunk_text"] = ""
        return Response(payload, status=status.HTTP_200_OK)

    wav_path = None
    try:
        print("PCM DEBUG writing wav from bytes:", len(new_buffer))
        wav_path = pcm_bytes_to_wav_file(
            new_buffer,
            sample_rate=session.sample_rate,
            channels=session.channels,
        )
        print("PCM DEBUG wav_path:", wav_path)

        result = WhisperService.transcribe_audio(wav_path)
        print("PCM DEBUG whisper raw result text:", repr(result.get("text", "")))

        incoming_text = normalize_text(result.get("text", ""))
        print("PCM DEBUG incoming_text:", repr(incoming_text))

        existing_transcript = build_transcript_text(
            TranscriptChunk.objects.filter(call=call).order_by("sequence_number", "created_at")
        )
        print("PCM DEBUG existing_transcript tail:", repr(existing_transcript[-200:]))

        # Safer live dedupe: only compare against recent tail, not the full transcript
        recent_tail = normalize_text(session.last_transcript_text or existing_transcript)[-200:]
        new_text = extract_new_portion(recent_tail, incoming_text)
        print("PCM DEBUG new_text:", repr(new_text))

        if new_text:
            TranscriptChunk.objects.create(
                call=call,
                speaker=speaker,
                text=new_text,
                sequence_number=get_next_sequence(call),
                timestamp_seconds=0,
                is_partial=False,
                source="live_stream",
            )
            session.last_transcript_text = normalize_text(f"{existing_transcript} {new_text}")

        # keep only the tail (~2 seconds) for continuity, avoid unbounded growth
        session.pcm_buffer = new_buffer[-64000:] if len(new_buffer) > 64000 else new_buffer
        session.save(update_fields=["pcm_buffer", "last_transcript_text", "updated_at"])

        call.status = "analyzing"
        call.save(update_fields=["status"])

        analysis = CallAnalysisService.analyze_call(call)

        call.status = "live"
        call.save(update_fields=["status"])

        payload = assistant_payload(call)
        payload["message"] = "PCM chunk processed successfully"
        payload["chunk_text"] = new_text
        payload["raw_incoming_text"] = incoming_text
        payload["analysis"] = CallAnalysisSerializer(analysis).data
        return Response(payload, status=status.HTTP_200_OK)

    except Exception as e:
        import traceback
        print("PCM DEBUG EXCEPTION:", repr(e))
        traceback.print_exc()

        # Keep session alive so later chunks can continue processing
        call.status = "live"
        call.save(update_fields=["status"])

        payload = assistant_payload(call)
        payload["message"] = f"PCM chunk failed but session kept alive: {str(e)}"
        payload["chunk_text"] = ""
        return Response(payload, status=status.HTTP_200_OK)

    finally:
        if wav_path:
            try:
                Path(wav_path).unlink(missing_ok=True)
            except Exception:
                pass


@api_view(["POST"])
@permission_classes([AllowAny])
def live_stop_view(request, call_id):
    try:
        call = Call.objects.get(id=call_id)
        session = LiveCallSession.objects.get(call=call)
    except Call.DoesNotExist:
        return Response({"error": "Call not found"}, status=status.HTTP_404_NOT_FOUND)
    except LiveCallSession.DoesNotExist:
        return Response({"error": "Live session not found"}, status=status.HTTP_404_NOT_FOUND)

    session.status = "stopped"
    session.ended_at = timezone.now()
    session.save(update_fields=["status", "ended_at", "updated_at"])

    call.status = "completed"
    call.save(update_fields=["status"])

    payload = assistant_payload(call)
    payload["message"] = "Live session stopped"
    return Response(payload, status=status.HTTP_200_OK)


# old endpoint kept for compatibility, but not recommended anymore
@api_view(["POST"])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser])
def stream_chunk_view(request, call_id):
    return Response(
        {
            "error": "Legacy webm live streaming is deprecated. Use /live/start/, /live/pcm-chunk/, and /live/stop/."
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def live_assistant_view(request, call_id):
    try:
        call = Call.objects.get(id=call_id)
    except Call.DoesNotExist:
        return Response({"error": "Call not found"}, status=status.HTTP_404_NOT_FOUND)

    return Response(assistant_payload(call), status=status.HTTP_200_OK)