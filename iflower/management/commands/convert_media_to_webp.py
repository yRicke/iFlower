from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image

from iflower.models import OrderItem, Product, ProductImage, Store


class Command(BaseCommand):
    help = 'Converte imagens PNG da pasta media para WebP e atualiza as referências no banco.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Executa a conversão. Sem esta opção, apenas lista as alterações.')
        parser.add_argument('--delete-original', action='store_true', help='Remove cada PNG após a conversão e atualização das referências.')
        parser.add_argument('--quality', type=int, default=85, help='Qualidade do WebP, entre 0 e 100. Padrão: 85.')

    def handle(self, *args, **options):
        if not 0 <= options['quality'] <= 100:
            raise CommandError('A qualidade deve estar entre 0 e 100.')
        if options['delete_original'] and not options['apply']:
            raise CommandError('Use --delete-original somente junto com --apply.')

        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            raise CommandError(f'A pasta de mídia não existe: {media_root}')

        png_files = sorted(path for path in media_root.rglob('*') if path.is_file() and path.suffix.lower() == '.png')
        if not png_files:
            self.stdout.write(self.style.WARNING('Nenhum PNG encontrado na pasta media.'))
            return

        replacements = {}
        converted = 0
        skipped = 0
        for source in png_files:
            target = source.with_suffix('.webp')
            source_name = source.relative_to(media_root).as_posix()
            target_name = target.relative_to(media_root).as_posix()
            replacements[source_name] = target_name

            if target.exists():
                skipped += 1
                self.stdout.write(f'Já existe: {target_name}')
                continue

            self.stdout.write(f'{"Converter" if options["apply"] else "Simular"}: {source_name} -> {target_name}')
            if not options['apply']:
                continue

            self.convert(source, target, options['quality'])
            converted += 1

        if not options['apply']:
            self.stdout.write(self.style.WARNING(f'Simulação concluída: {len(png_files)} PNG(s) seriam convertidos. Use --apply para executar.'))
            return

        updated_references = self.update_references(replacements)
        if options['delete_original']:
            for source in png_files:
                source.unlink()

        message = f'Conversão concluída: {converted} arquivo(s) convertidos, {skipped} já existentes e {updated_references} referência(s) atualizada(s).'
        if options['delete_original']:
            message += f' {len(png_files)} PNG(s) removidos.'
        self.stdout.write(self.style.SUCCESS(message))

    @staticmethod
    def convert(source, target, quality):
        with Image.open(source) as image:
            image.load()
            has_transparency = image.mode in {'RGBA', 'LA'} or 'transparency' in image.info
            normalized = image.convert('RGBA' if has_transparency else 'RGB')
            normalized.save(target, 'WEBP', quality=quality, method=6)

    @staticmethod
    def update_references(replacements):
        updated = 0
        with transaction.atomic():
            for model, field in ((Store, 'logo'), (Store, 'cover'), (Product, 'image'), (ProductImage, 'image')):
                for instance in model.objects.exclude(**{field: ''}).iterator():
                    current_name = getattr(instance, field).name
                    replacement = replacements.get(current_name)
                    if replacement:
                        getattr(instance, field).name = replacement
                        instance.save(update_fields=[field])
                        updated += 1

            for item in OrderItem.objects.exclude(image='').iterator():
                replacement = replacements.get(item.image)
                if replacement:
                    item.image = replacement
                    item.save(update_fields=['image'])
                    updated += 1
        return updated
