"""Alta interactiva y segura de usuarios en TBL_USUARIO_GC."""

from getpass import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crea un usuario del portal y solicita la contraseña sin mostrarla."

    def add_arguments(self, parser):
        parser.add_argument("--usuario")
        parser.add_argument("--nombre")
        parser.add_argument("--email", default="")
        parser.add_argument(
            "--rol",
            choices=("ADMINISTRADOR", "ANALISTA"),
            default="ANALISTA",
        )

    def handle(self, *args, **options):
        user_model = get_user_model()
        username = (options["usuario"] or input("Usuario: ")).strip().upper()
        full_name = (options["nombre"] or input("Nombre completo: ")).strip()
        email = options["email"].strip() or input("Correo (opcional): ").strip()
        if not username or not full_name:
            raise CommandError("Usuario y nombre completo son obligatorios.")
        if user_model.objects.filter(username__iexact=username).exists():
            raise CommandError("El usuario ya existe.")

        password = getpass("Contraseña: ")
        confirmation = getpass("Repita la contraseña: ")
        if password != confirmation:
            raise CommandError("Las contraseñas no coinciden.")
        candidate = user_model(username=username, nombre_completo=full_name, email=email or None)
        try:
            validate_password(password, user=candidate)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from error

        user_model.objects.create_user(
            username=username,
            password=password,
            nombre_completo=full_name,
            email=email or None,
            rol=options["rol"],
        )
        self.stdout.write(self.style.SUCCESS(f"Usuario {username} creado como {options['rol']}."))
