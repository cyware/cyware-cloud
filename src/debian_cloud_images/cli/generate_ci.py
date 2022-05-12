import argparse
import json
import logging
import sys
import typing

from .base import BaseCommand


logger = logging.getLogger()


class GenerateCiCommand(BaseCommand):
    argparser_name = 'generate-generate'
    argparser_help = 'generate CI config'
    argparser_usage = '%(prog)s'
    argparser_argument_public_type = None

    @classmethod
    def _argparse_register(cls, parser) -> None:
        super()._argparse_register(parser)

        cls.argparser_argument_public_type = parser.add_argument(
            '--public-type',
            default='dev',
            dest='public_type_name',
            help='the public type to generate config for',
            metavar='TYPE',
        )
        parser.add_argument(
            'output',
            metavar='OUTPUT',
            nargs='?',
            help='Where to write file to (default: stdout)',
        )

    def __init__(self, *, output: str, public_type_name: str, **kw):
        super().__init__(**kw)

        self.public_type = self.config_image.public_types.get(public_type_name)

        if self.public_type is None:
            raise argparse.ArgumentError(
                self.argparser_argument_public_type,
                f'invalid value: {public_type_name}, select one of {", ".join(self.config_image.public_types)}')

        self.output = output

    def check_matches(self, matches, vendor_name, release_name, arch_name):
        if not matches:
            return True, False, None

        enable = None
        enable_upload = None
        upload_group = None

        for m in matches:
            if not m.match_vendors:
                pass
            elif vendor_name in m.match_vendors:
                pass
            elif '*' in m.match_vendors:
                pass
            else:
                continue

            if not m.match_releases:
                pass
            elif release_name in m.match_releases:
                pass
            elif '*' in m.match_releases:
                pass
            else:
                continue

            if not m.match_arches:
                pass
            elif arch_name in m.match_arches:
                pass
            elif '*' in m.match_arches:
                pass
            else:
                continue

            if m.op == 'Enable':
                if enable is None:
                    enable = True
            elif m.op == 'EnableUpload':
                if enable is None:
                    enable = True
                if enable_upload is None:
                    enable_upload = True
            elif m.op == 'Disable':
                if enable is None:
                    enable = False
            elif m.op == 'DisableUpload':
                if enable is None:
                    enable = False
                if enable_upload is None:
                    enable_upload = False

            if upload_group is None:
                upload_group = m.upload_group

        return enable, enable_upload, upload_group

    def __call__(self) -> None:
        out = {}
        needs_upload = []

        for vendor_name, vendor in self.config_image.vendors.items():
            for release_name, release in self.config_image.releases.items():
                for arch_name, arch in self.config_image.archs.items():
                    enable, _, _ = self.check_matches(vendor.matches, vendor_name, release.basename, arch_name)
                    if not enable:
                        continue

                    enable, enable_upload, upload_group = self.check_matches(self.public_type.matches, vendor_name, release.basename, arch_name)
                    if not enable:
                        continue

                    variables = {
                        'CLOUD_ARCH': arch_name,
                        'CLOUD_RELEASE': release_name,
                        'CLOUD_VENDOR': vendor_name,
                    }
                    variables_postupload = {}

                    name_build = f'{vendor_name} {release_name} {arch_name} build'
                    name_upload = f'{vendor_name} {release_name} {arch_name} upload'
                    extends_upload = f'.{vendor_name} upload'
                    extends_postupload = f'.{vendor_name} postupload'

                    if upload_group:
                        variables['CLOUD_UPLOAD_GROUP'] = upload_group
                        variables_postupload['CLOUD_UPLOAD_GROUP'] = upload_group
                        name_upload_group = f'{vendor_name} group-{upload_group} upload'
                        name_postupload = f'{vendor_name} group-{upload_group} postupload'
                    else:
                        name_upload_group = f'{vendor_name} upload'
                        name_postupload = f'{vendor_name} postupload'

                    needs_upload.append(name_build)
                    out[name_build] = {
                        'extends': '.build',
                        'variables': variables,
                    }

                    if enable_upload:
                        needs_upload.append(name_upload)
                        job_upload = out[name_upload] = {
                            'extends': extends_upload,
                            'variables': variables,
                            'needs': [name_build],
                        }

                        if upload_group:
                            job_upload['resource_group'] = name_upload_group

                        job_postupload: dict[str, typing.Any] = out.setdefault(name_postupload, {
                            'extends': extends_postupload,
                            'variables': variables_postupload,
                            'needs': [],
                        })
                        job_postupload['needs'].append(name_upload)

        out['upload'] = {
            'extends': '.upload',
            'dependencies': needs_upload,
        }

        if self.output:
            with open(self.output, 'w') as f:
                self.dump(f, out)
        else:
            self.dump(sys.stdout, out)

    def dump(self, f: typing.TextIO, data: typing.Any) -> None:
        print(f'# Generated with "python3 -m debian_cloud_images.cli.generate_ci {" ".join(sys.argv[1:])}"', file=f)
        json.dump(data, f, indent=2)
        print(file=f)


if __name__ == '__main__':
    GenerateCiCommand._main()
