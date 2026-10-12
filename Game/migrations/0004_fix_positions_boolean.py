from django.db import migrations


def fix_positions_to_boolean(apps, schema_editor):
    """
    options.fix_positions used to be the position {x, y} of a button drawn on
    the table, or null to hide it. The button moved to a bar of the page: the
    option is now a boolean, false where it was null and true otherwise.
    """
    for name in ("Game", "Variant"):
        model = apps.get_model("Game", name)
        for row in model.objects.all().iterator():
            options = row.options
            if not isinstance(options, dict) or "fix_positions" not in options:
                continue
            value = options["fix_positions"]
            if isinstance(value, bool):
                continue
            row.options = {**options, "fix_positions": value is not None}
            row.save(update_fields=["options"])


class Migration(migrations.Migration):
    """
    Not reversible into what it was: the coordinates are dropped, and they no
    longer mean anything. Going backwards keeps the booleans, which the code
    before this migration reads the same way (false hides, true shows).
    """

    dependencies = [
        ("Game", "0003_options"),
    ]

    operations = [
        migrations.RunPython(fix_positions_to_boolean, migrations.RunPython.noop),
    ]
