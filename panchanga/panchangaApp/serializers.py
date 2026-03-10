from rest_framework import serializers

class PanchangaInputSerializer(serializers.Serializer):
    date = serializers.CharField()
    time = serializers.CharField()
    location = serializers.CharField()