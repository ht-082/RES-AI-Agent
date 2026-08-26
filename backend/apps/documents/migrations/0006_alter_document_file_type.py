# xlsm(매크로 통합문서) 지원 — 재무모델(FM) 파일이 이 포맷이라 그대로 두면
# 수집 대상에서 조용히 빠진다. choices 변경이라 DB 스키마는 바뀌지 않는다.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0005_corpusversion_document_corpus'),
    ]

    operations = [
        migrations.AlterField(
            model_name='document',
            name='file_type',
            field=models.CharField(
                choices=[('pdf', 'PDF'), ('docx', 'Word'), ('xlsx', 'Excel'),
                         ('xlsm', 'Excel(매크로)'), ('pptx', 'PowerPoint')],
                max_length=10),
        ),
    ]
