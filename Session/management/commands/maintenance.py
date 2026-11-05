from django.core.management.base import BaseCommand, CommandError

from Session import maintenance


class Command(BaseCommand):
    help = (
        "Maintenance of the site, relayed to Tourtoirac and Hautefort (Session/maintenance.py): "
        "status, announce (--in minutes before the start, --duration minutes announced, "
        "--message), start (at once), cancel, end. Fails when a service did not answer; "
        "the others got the action all the same."
    )

    def add_arguments(self, parser):
        parser.add_argument("action", choices=("status",) + maintenance.ACTIONS)
        parser.add_argument("--in", dest="minutes_before", type=int, default=5,
                            help="announce: minutes until the start (default 5)")
        parser.add_argument("--duration", dest="duration_minutes", type=int, default=10,
                            help="announce: minutes the players are told it lasts (default 10)")
        parser.add_argument("--message", default="", help="announce: a text shown to the players")

    def handle(self, *args, **options):
        action = options["action"]
        try:
            if action == "status":
                states = maintenance.status()
            else:
                states = maintenance.apply(action, options["minutes_before"], options["duration_minutes"],
                                           options["message"])
        except maintenance.MaintenanceRequestError as error:
            raise CommandError(str(error)) from error
        for name, state in states.items():
            if "error" in state:
                self.stdout.write(f"{name}: ERROR {state['error']}")
            else:
                when = f" at {state['starts_at']}" if state.get("starts_at") else ""
                duration = f", {state['duration_minutes']} min" if state.get("duration_minutes") else ""
                self.stdout.write(f"{name}: {state['phase']}{when}{duration}")
        failed = maintenance.failures(states)
        if failed:
            raise CommandError("Service(s) not reached: " + "; ".join(failed))
