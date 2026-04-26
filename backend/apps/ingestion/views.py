from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .parsers import SUPPORTED_SOURCES
from .serializers import IngestEnvelopeSerializer, IngestRequestSerializer
from .services import IngestionError, ingest_post


class IngestAPIView(APIView):
    """``POST /api/ingest/`` — accept a raw paste, return the NLP-ready payload."""

    def post(self, request, *args, **kwargs):
        request_ser = IngestRequestSerializer(data=request.data)
        request_ser.is_valid(raise_exception=True)

        try:
            result = ingest_post(
                source=request_ser.validated_data["source"],
                raw_text=request_ser.validated_data["raw_text"],
            )
        except IngestionError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )

        envelope = {
            "created": result.created,
            "duplicate": not result.created,
            "cleaning": {
                "char_count": result.normalized.char_count,
                "word_count": result.normalized.word_count,
                "removed_urls": result.normalized.removed_urls,
                "removed_mentions": result.normalized.removed_mentions,
                "removed_hashtags": result.normalized.removed_hashtags,
            },
            "payload": result.payload,
        }
        response_ser = IngestEnvelopeSerializer(envelope)
        http_status = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
        return Response(response_ser.data, status=http_status)


def paste_page(request):
    """Server-rendered manual-paste UI."""
    return render(
        request,
        "ingestion/paste.html",
        {"sources": SUPPORTED_SOURCES},
    )
