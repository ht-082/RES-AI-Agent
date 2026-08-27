"""workspaces 스키마 드리프트 정리 — created_by 컬럼명 정합.

모델은 db_column='created_by' 를 명시하는데 0001_initial 의 상태에는 그것이 없어
makemigrations 가 매번 AlterField 를 제안했다. 그대로 자동 생성해 적용하면
Django 가 `RENAME COLUMN created_by_id TO created_by` 를 시도하는데, schema.sql 로
만든 DB에는 created_by_id 가 없어 실패한다. contracts.0003 과 같은 방식으로
상태만 맞추고, DB 조작은 실제로 필요한 경우에만 하도록 존재 검사를 건다.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _rename(table, frm, to):
    return f"""
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = '{table}' AND column_name = '{frm}')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = '{table}' AND column_name = '{to}') THEN
        ALTER TABLE {table} RENAME COLUMN {frm} TO {to};
    END IF;
END $$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('workspaces', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='workspace',
                    name='created_by',
                    field=models.ForeignKey(
                        blank=True, db_column='created_by', null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='workspaces',
                        to=settings.AUTH_USER_MODEL),
                ),
                migrations.AlterField(
                    model_name='project',
                    name='created_by',
                    field=models.ForeignKey(
                        blank=True, db_column='created_by', null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='projects',
                        to=settings.AUTH_USER_MODEL),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=_rename('workspaces', 'created_by_id', 'created_by'),
                    reverse_sql=_rename('workspaces', 'created_by', 'created_by_id')),
                migrations.RunSQL(
                    sql=_rename('projects', 'created_by_id', 'created_by'),
                    reverse_sql=_rename('projects', 'created_by', 'created_by_id')),
            ],
        ),
    ]
