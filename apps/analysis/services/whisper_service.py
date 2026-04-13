import os
import whisper


class WhisperService:
    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
            cls._model = whisper.load_model("base").to(device)
        return cls._model

    @classmethod
    def transcribe_audio(cls, audio_path: str) -> dict:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        model = cls.get_model()
        result = model.transcribe(
            audio_path,
            fp16=False,
            language="en",
            temperature=0.0,
            condition_on_previous_text=False,
        )

        return {
            "text": result.get("text", "").strip(),
            "segments": result.get("segments", []),
            "language": result.get("language"),
        }
