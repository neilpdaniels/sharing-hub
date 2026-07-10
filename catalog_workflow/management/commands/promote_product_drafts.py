import shlex
import subprocess
import tempfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from catalog_workflow.models import ProductDraft

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
        parser.add_argument('--remote-media-root', default='/srv/rentalution/media')
        parser.add_argument('--remote-workdir', default='/srv/rentalution')

    def handle(self, *args, **options):
        draft_ids = [value for value in options['draft'] if str(value).strip()]
        if options['all_ready']:
            if draft_ids:
                raise CommandError('Use either --all-ready or --draft, not both.')
            draft_ids = list(
                ProductDraft.objects.filter(status=ProductDraft.STATUS_READY).values_list('id', flat=True)
            )
        if not draft_ids:
            raise CommandError('Provide at least one --draft id or use --all-ready.')

        drafts = ProductDraft.objects.filter(id__in=draft_ids)
        found_ids = {str(draft.id) for draft in drafts}
        missing = [draft_id for draft_id in draft_ids if str(draft_id) not in found_ids]
        if missing:
            raise CommandError(f'Draft(s) not found: {", ".join(missing)}')

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

            if options['run_import']:
                import_cmd = (
                    f"container_id=$(docker compose -f docker-compose.yml -f docker-compose.prod.yml ps -q web) && "
                    f"docker cp {shlex.quote(remote_dir)} \"$container_id\":{shlex.quote(remote_dir)} && "
                    f"docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T web "
                    f"uv run python manage.py import_product_draft_bundle {shlex.quote(remote_dir)} "
                    f"--media-root {shlex.quote(remote_media_root)}"
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
