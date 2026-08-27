"""contracts 스키마 드리프트 정리 — created_by 컬럼명 정합.

배경: 이 프로젝트는 db/schema.sql(initdb 원본)과 Django 마이그레이션을 병행한다.
schema.sql 이 만드는 컬럼은 `created_by` 인데, 모델에 db_column 을 명시하지 않으면
Django 는 `created_by_id` 를 기대한다. 그 어긋남 때문에 User 삭제 시 SET_NULL 갱신이
`column contract_reviews.created_by_id does not exist` 로 실패했다.

이 마이그레이션은 **DB를 파괴하지 않는다.** 자동 생성(makemigrations)에 맡기면
contract_drafts.created_by 를 DROP 하려 드는데, 그 컬럼은 schema.sql 이 정의한
것이고 병합 예정인 계약 기능이 참조할 수 있어 남겨 둔다.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

# 마이그레이션만으로 만든 DB에는 created_by_id 가, schema.sql 로 만든 DB에는
# created_by 가 있다. 어느 쪽이든 한 번만 맞도록 존재 검사를 걸어 rename 한다.
RENAME_TO_SCHEMA = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'contract_reviews' AND column_name = 'created_by_id')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'contract_reviews' AND column_name = 'created_by') THEN
        ALTER TABLE contract_reviews RENAME COLUMN created_by_id TO created_by;
    END IF;
END $$;
"""

RENAME_BACK = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'contract_reviews' AND column_name = 'created_by')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'contract_reviews' AND column_name = 'created_by_id') THEN
        ALTER TABLE contract_reviews RENAME COLUMN created_by TO created_by_id;
    END IF;
END $$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0002_remove_contractdraft_created_by_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ① ContractDraft.created_by: 모델에서는 이미 user 로 대체됐지만 마이그레이션
        #    상태에는 남아 있어 매번 RemoveField 를 제안한다. DB 컬럼은 보존하고
        #    상태만 정리한다.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name='contractdraft', name='created_by'),
            ],
            database_operations=[],
        ),
        # ② ContractReview.created_by: db_column 을 명시해 schema.sql 과 맞춘다.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='contractreview',
                    name='created_by',
                    field=models.ForeignKey(
                        blank=True, db_column='created_by', null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='contract_reviews',
                        to=settings.AUTH_USER_MODEL),
                ),
            ],
            database_operations=[
                migrations.RunSQL(sql=RENAME_TO_SCHEMA, reverse_sql=RENAME_BACK),
            ],
        ),
    ]
