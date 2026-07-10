import shlex
import subprocess
import tempfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from catalog_workflow.models import ProductDraft
from catalog_workflow.services import publish_draft

from .export_product_draft_bundle import Command as ExportBundleCommand


class Command(BaseCommand):
    help = 'Export selected drafts, copy them to a remote host, and optionally import them there.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--draft',
            action='append',
            default=[],
            help='ProductDraft id to promote. May be repeated.',
        )
        parser.add_argument(
            '--all-ready',
            action='store_true',
            help='Promote every draft currently marked ready.',
        )
        parser.add_argument('--host', required=True, help='Target host, e.g. 51.89.165.49')
        parser.add_argument('--user', required=True, help='SSH user on the target host')
        parser.add_argument('--remote-dir', default='/tmp/rentalution-catalog-promotion', help='Remote staging directory')
        parser.add_argument('--ssh-port', default='22')
        parser.add_argument('--run-import', action='store_true', help='Run import command on the remote host after copy')
        parser.add_argument('--remote-host-media-root', default='/srv/rentalution/media')
        parser.add_argument('--container-media-root', default='/app/media')
        parser.add_argument('--remote-workdir', default='/srv/rentalution')
        parser.add_argument(
            '--target',
            choices=('dev', 'prod', 'both'),
            help='Where to publish: dev, prod, or both. If omitted, you will be prompted.',
        )

    def handle(self, *args, **options):
        target = options['target']
        if not target:
            target = input('Publish to dev, prod, or both? [dev/prod/both]: ').strip().lower()
        if target not in {'dev', 'prod', 'both'}:
            raise CommandError('Target must be dev, prod, or both.')

        draft_ids = [value for value in options['draft'] if str(value).strip()]
        if options['all_ready']:
            if draft_ids:
                raise CommandError('Use either --all-ready or --draft, not both.')
            draft_ids = list(
                ProductDraft.objects.filter(status=ProductDraft.STATUS_READY).values_list('id', flat=True)
            )
            if not draft_ids:
                ready_count = ProductDraft.objects.filter(status=ProductDraft.STATUS_READY).count()
                raise CommandError(f'No drafts are marked ready. Ready draft count: {ready_count}.')
        if not draft_ids:
            raise CommandError('Provide at least one --draft id or use --all-ready.')

        drafts = ProductDraft.objects.filter(id__in=draft_ids)
        found_ids = {str(draft.id) for draft in drafts}
        missing = [draft_id for draft_id in draft_ids if str(draft_id) not in found_ids]
        if missing:
            raise CommandError(f'Draft(s) not found: {", ".join(missing)}')

        if target in {'dev', 'both'}:
            published = 0
            for draft in drafts.select_related('parent_category'):
                product = publish_draft(draft)
                draft.published_product = product
                draft.status = ProductDraft.STATUS_PUBLISHED
                draft.save(update_fields=['published_product', 'status', 'updated_at'])
                published += 1
            self.stdout.write(self.style.SUCCESS(f'Published {published} draft(s) locally.'))

        if target == 'dev':
            return

        with tempfile.TemporaryDirectory(prefix='rentalution-promo-') as tmpdir:
            bundle_dir = Path(tmpdir) / 'bundle'
            bundle_dir.mkdir(parents=True, exist_ok=True)
            export_cmd = ExportBundleCommand()
            export_cmd.stdout = self.stdout
            export_cmd.stderr = self.stderr
            export_cmd.handle(draft=draft_ids, output_dir=str(bundle_dir))

            remote_target = f"{options['user']}@{options['host']}"
            remote_dir = options['remote_dir']
            ssh_port = str(options['ssh_port'])

            subprocess.run(
                [
                    'ssh',
                    '-p',
                    ssh_port,
                    remote_target,
                    f'mkdir -p {shlex.quote(remote_dir)}',
                ],
                check=True,
            )

            subprocess.run(
                [
                    'rsync',
                    '-av',
                    '-e',
                    f'ssh -p {ssh_port}',
                    f'{bundle_dir}/',
                    f'{remote_target}:{remote_dir}/',
                ],
                check=True,
            )

            self.stdout.write(self.style.SUCCESS(f'Copied bundle to {remote_target}:{remote_dir}'))

            subprocess.run(
                [
                    'rsync',
                    '-av',
                    '-e',
                    f'ssh -p {ssh_port}',
                    f'{bundle_dir / "media"}/',
                    f'{remote_target}:{options["remote_host_media_root"]}/',
                ],
                check=True,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f'Synced media to {remote_target}:{options["remote_host_media_root"]}'
                )
            )

            if options['run_import']:
                import_cmd = (
                    f"cd {shlex.quote(options['remote_workdir'])} && "
                    f"container_id=$(docker compose -f docker-compose.yml -f docker-compose.prod.yml ps -q web) && "
                    f"docker cp {shlex.quote(remote_dir)} \"$container_id\":{shlex.quote(remote_dir)} && "
                    f"docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T web "
                    f"uv run python manage.py import_product_draft_bundle {shlex.quote(remote_dir)} "
                    f"--media-root {shlex.quote(options['container_media_root'])} --publish"
                )
                subprocess.run(
                    [
                        'ssh',
                        '-p',
                        ssh_port,
                        remote_target,
                        import_cmd,
                    ],
                    check=True,
                )
                self.stdout.write(self.style.SUCCESS('Remote import completed.'))
