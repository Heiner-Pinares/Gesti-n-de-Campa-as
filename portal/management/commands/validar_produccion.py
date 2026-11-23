from django.core.management.base import BaseCommand, CommandError

from portal.production_checks import run_production_checks


class Command(BaseCommand):
    help = "Comprueba requisitos de producción sin migrar ni autenticar contra AD."

    def add_arguments(self, parser):
        parser.add_argument("--port", type=int, required=True)
        parser.add_argument("--sin-comprobar-puerto", action="store_true")

    def handle(self, *args, **options):
        port = options["port"]
        if not 1 <= port <= 65535:
            raise CommandError("El puerto debe estar entre 1 y 65535.")

        checks = run_production_checks(
            port,
            skip_port_check=options["sin_comprobar_puerto"],
        )
        errors = 0
        warnings = 0
        for check in checks:
            line = f"[{check.level}] {check.name}: {check.detail}"
            if check.level == "ERROR":
                errors += 1
                self.stderr.write(self.style.ERROR(line))
            elif check.level == "ADVERTENCIA":
                warnings += 1
                self.stdout.write(self.style.WARNING(line))
            else:
                self.stdout.write(self.style.SUCCESS(line))

        self.stdout.write(f"Resumen: {errors} error(es), {warnings} advertencia(s).")
        if errors:
            raise CommandError("La validación de producción encontró errores bloqueantes.")
        self.stdout.write(self.style.SUCCESS("Validación de producción aprobada."))
