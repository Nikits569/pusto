from django.db import migrations
import uuid

def fill_checkout_key(apps, schema_editor):
    Pending = apps.get_model("payments", "PendingAdvPromotion")
    qs = Pending.objects.filter(checkout_key__isnull=True).only("id")
    for obj in qs.iterator():
        # гарантированно уникально для каждой строки
        obj.checkout_key = uuid.uuid4()
        obj.save(update_fields=["checkout_key"])

class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0008_pendingadvpromotion_checkout_key"),  # <-- поставь имя своей миграции из шага 3
    ]

    operations = [
        migrations.RunPython(fill_checkout_key, migrations.RunPython.noop),
    ]
