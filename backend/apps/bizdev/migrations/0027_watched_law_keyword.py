from django.db import migrations, models


class Migration(migrations.Migration):
    """관심 법령에 '키워드' 구분을 더한다.

    family(법령명 전용) → term(법령명 또는 키워드) 로 이름을 바꾸고 kind 를
    붙인다. 자동 생성에 맡기면 필드 삭제+추가로 잡아 기존 관심 법령이 전부
    날아가므로 RenameField 로 직접 쓴다.
    """

    dependencies = [('bizdev', '0026_watched_law')]

    operations = [
        migrations.RenameField(
            model_name='watchedlaw', old_name='family', new_name='term',
        ),
        migrations.AlterField(
            model_name='watchedlaw', name='term',
            field=models.CharField(max_length=120, verbose_name='법령명 · 키워드'),
        ),
        migrations.AddField(
            model_name='watchedlaw', name='kind',
            field=models.CharField(choices=[('law', '법령명'), ('keyword', '키워드')],
                                   default='law', max_length=10, verbose_name='구분'),
        ),
        migrations.AlterModelOptions(
            name='watchedlaw',
            options={'ordering': ['kind', 'sort_order', 'term'],
                     'verbose_name': '관심 법령', 'verbose_name_plural': '관심 법령'},
        ),
        migrations.AddConstraint(
            model_name='watchedlaw',
            constraint=models.UniqueConstraint(fields=('kind', 'term'),
                                               name='uniq_watched_law_kind_term'),
        ),
    ]
