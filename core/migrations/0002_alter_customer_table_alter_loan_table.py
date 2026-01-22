from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='customer',
            table=None,
        ),
        migrations.AlterModelTable(
            name='loan',
            table=None,
        ),
    ]
