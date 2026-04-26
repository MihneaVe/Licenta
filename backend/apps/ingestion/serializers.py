from rest_framework import serializers

from .parsers import SUPPORTED_SOURCES


class IngestRequestSerializer(serializers.Serializer):
    """Validated input for the manual-paste endpoint."""

    source = serializers.ChoiceField(choices=SUPPORTED_SOURCES)
    raw_text = serializers.CharField(
        max_length=20_000,
        trim_whitespace=False,
        help_text="The exact text the user copy-pasted from Reddit / X.",
    )

    def validate_raw_text(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError("raw_text cannot be empty.")
        return value


class IngestResponseSerializer(serializers.Serializer):
    """The clean payload handed off to the NLP pipeline."""

    post_id = serializers.IntegerField()
    source = serializers.CharField()
    source_id = serializers.CharField()
    content = serializers.CharField()
    author = serializers.CharField(allow_blank=True)
    url = serializers.CharField(allow_blank=True)
    score = serializers.IntegerField()
    original_date = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    metadata = serializers.DictField()
    ready_for_nlp = serializers.BooleanField()


class IngestEnvelopeSerializer(serializers.Serializer):
    """Wraps the payload with ingestion bookkeeping for the API response."""

    created = serializers.BooleanField()
    duplicate = serializers.BooleanField()
    cleaning = serializers.DictField()
    payload = IngestResponseSerializer()
