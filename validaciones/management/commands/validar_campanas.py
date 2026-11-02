from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from validaciones.service import (
    DuplicateExecution,
    InvalidExecutionPeriod,
    create_execution,
    execute_validation,
)


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as error:
        raise CommandError(f"Fecha inválida: {value}. Use AAAA-MM-DD.") from error


class Command(BaseCommand):
    help = "Ejecuta el mismo motor de validación utilizado por el portal."

    def add_arguments(self, parser):
        parser.add_argument("--desde", required=True)
        parser.add_argument("--hasta", required=True)
        parser.add_argument(
            "--tipo",
            choices=("MANUAL", "PROGRAMADA"),
            default="PROGRAMADA",
        )
        parser.add_argument("--usuario", default="")

    def handle(self, *args, **options):
        start = parse_date(options["desde"])
        end = parse_date(options["hasta"])
        if start > end:
            raise CommandError("La fecha desde no puede ser posterior a la fecha hasta.")
        user = None
        if options["usuario"]:
            user_model = get_user_model()
            try:
                user = user_model.objects.get(username__iexact=options["usuario"].strip())
            except user_model.DoesNotExist as error:
                raise CommandError("El usuario indicado no existe.") from error
        try:
            execution = create_execution(start, end, options["tipo"], user=user)
        except (DuplicateExecution, InvalidExecutionPeriod) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(f"Ejecución #{execution.pk} registrada.")
        execute_validation(execution.pk)
        execution.refresh_from_db()
        self.stdout.write(
            self.style.SUCCESS(
                f"Ejecución #{execution.pk} completada: "
                f"evaluados={execution.total_evaluados}, "
                f"correctos={execution.total_correctos}, "
                f"errores={execution.total_errores}, "
                f"por_revisar={execution.total_revisar}, "
                f"no_aplica={execution.total_no_aplica}."
            )
        )
