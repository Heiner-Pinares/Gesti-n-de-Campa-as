"""Instalación explícita e idempotente de las tablas Oracle del portal."""

import os

import oracledb
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from config.database import oracle_connect_kwargs
from portal.oracle_schema import load_schema_objects
from validaciones.management.commands.verificar_oracle import friendly_oracle_error


CONFIRMATION = "CREAR_TABLAS_GC"


class Command(BaseCommand):
    help = "Muestra o aplica el DDL Oracle aprobado del portal. Nunca se ejecuta automáticamente."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Crea únicamente los objetos que todavía no existen.")
        parser.add_argument("--confirmacion", default="", help=f"Para aplicar debe indicar {CONFIRMATION}.")

    def handle(self, *args, **options):
        objects = load_schema_objects()
        self.stdout.write("Plan de objetos Oracle:")
        for item in objects:
            self.stdout.write(f"- {item.object_type}: {item.name}")

        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Modo plan: no se ejecutó DDL."))
            return
        if options["confirmacion"] != CONFIRMATION:
            raise CommandError(f"Confirmación inválida. Use --confirmacion {CONFIRMATION}.")

        expected_schema = (os.getenv("ORACLE_SCHEMA") or "USRVALCBIO").strip().upper()
        credentials = oracle_connect_kwargs(os.environ, settings.BASE_DIR)
        connection = None
        created = []
        skipped = []
        try:
            connection = oracledb.connect(**credentials)
            with connection.cursor() as cursor:
                cursor.execute("SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') FROM DUAL")
                current_schema = cursor.fetchone()[0].upper()
                if current_schema != expected_schema:
                    raise CommandError(
                        f"Esquema actual inesperado: {current_schema}. Se esperaba {expected_schema}."
                    )

                for item in objects:
                    cursor.execute(
                        "SELECT OBJECT_TYPE FROM USER_OBJECTS WHERE OBJECT_NAME = :name",
                        {"name": item.name},
                    )
                    existing_types = {row[0] for row in cursor.fetchall()}
                    if item.object_type in existing_types:
                        skipped.append(item.name)
                        continue
                    if existing_types:
                        raise CommandError(
                            f"Existe un objeto incompatible llamado {item.name}: "
                            + ", ".join(sorted(existing_types))
                        )
                    try:
                        cursor.execute(item.ddl)
                    except oracledb.Error as error:
                        detail = getattr(getattr(error, "args", [None])[0], "message", "Error Oracle")
                        raise CommandError(f"Falló la creación de {item.name}: {detail}") from error
                    created.append(item.name)
            connection.commit()
        except oracledb.Error as error:
            raise CommandError(friendly_oracle_error(error)) from error
        finally:
            if connection is not None:
                connection.close()

        self.stdout.write(self.style.SUCCESS(f"Objetos creados: {len(created)}."))
        if created:
            self.stdout.write("  " + ", ".join(created))
        self.stdout.write(f"Objetos ya existentes: {len(skipped)}.")
        if skipped:
            self.stdout.write("  " + ", ".join(skipped))
