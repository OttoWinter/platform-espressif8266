from github import Github
import argparse
import os
import sys
import requests
import tarfile
import json
from io import BytesIO
from datetime import datetime
import re
import hashlib
from pathlib import Path
import copy

parser = argparse.ArgumentParser()
gh_token = os.getenv('GH_TOKEN')
parser.add_argument('--token', help="Github Token", type=str,
                    required=gh_token is None, default=gh_token)
parser.add_argument('--tag', help="Release tag", type=str, required=True)
parser.add_argument('--system', help="Artifact System", nargs='*', default=['*'], type=str)
parser.add_argument('--version', help="Artifact Version Base", type=str, required=True)
parser.add_argument('--url', help="Artifact URL", type=str, required=True)
parser.add_argument('--name', help="Artifact Name", type=str, required=True)
parser.add_argument('--description', help="Artifact Description", type=str)
parser.add_argument('--description-url', help="Artifact Description URL", type=str)
args = parser.parse_args()

temp_path = Path('temp')
temp_path.mkdir(exist_ok=True)

datestr = datetime.now().strftime('%y%m%d')
vsplit = re.split(r'[\.\-]', args.version)
vstr = ''.join(f'{int(v):02d}' for v in vsplit)
while vstr.startswith('0'):
    vstr = vstr[1:]
version = f"1.{vstr}.{datestr}"

asset_name = f'{args.name}'
if args.system[0] != '*':
    asset_name += f'-{args.system[0]}'
asset_name += f'-v{version}'
base_name = asset_name
asset_name += '.tar.gz'
print(f"Asset Name: {asset_name}")



gh = Github(args.token)
repo = gh.get_repo('OttoWinter/platform-espressif8266')
for rel in repo.get_releases():
    if rel.tag_name == args.tag:
        break
else:
    print(f"Could not find tag {args.tag}")
    sys.exit(1)

if any(asset.name == asset_name for asset in rel.get_assets()):
    print("Already uploaded!")
    sys.exit(0)

download_path = temp_path / (base_name + '.download.tar.gz')
if not download_path.exists():
    print(f"Downloading {args.url} to {download_path}")
    with download_path.open(mode='wb') as fh:
        with requests.get(args.url, allow_redirects=True, stream=True) as resp:
            resp.raise_for_status()
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    fh.write(chunk)
    print(f"Done!")

download_file = download_path.open(mode='rb')
download_tar = tarfile.open(fileobj=download_file)

names = []
for member in download_tar.getmembers():
    names.append(member.name)

prefix_len = len(names[0])
for name in names[1:]:
    prefix_len = min(prefix_len, len(name))
    while not name.startswith(names[0][:prefix_len]):
        prefix_len -= 1
print(f"Common prefix: {names[0][:prefix_len]}")
if prefix_len != 0:
    prefix_len += 1

result_path = temp_path / (base_name + '.result.tar.gz')
result_file = result_path.open(mode='wb')
result_tar = tarfile.open(mode='w:gz', fileobj=result_file)
print(f"Writing result tar {result_file.name}")

def set_tarinfo(ti):
    ti.uid = 501
    ti.gid = 20
    ti.uname = 'esphome'
    ti.gname = 'staff'

prefix = names[0][prefix_len:]

for member in download_tar.getmembers():
    if len(member.name) <= prefix_len:
        continue
    new_member = copy.copy(member)
    set_tarinfo(new_member)
    new_member.gname = 'staff'
    old_name = new_member.name
    new_member.name = old_name[prefix_len:]
    # print(old_name, new_member.name)
    orig_file = None
    if member.isfile():
        orig_file = download_tar.extractfile(old_name)
    elif member.issym():
        member_path = Path(member.name)
        link_path = member_path.parent / member.linkname
        link_path.resolve()
        try:
            download_tar.getmember(str(link_path))
        except KeyError:
            print("===")
            print(f"WARNING: Symbolic link {member.name}->{member.linkname} not found in archive!")
            print("===")
            raise
        if new_member.linkname.startswith(prefix):
            new_member.linkname = new_member.linkname[prefix_len:]
    elif member.islnk():
        if new_member.linkname.startswith(prefix):
            new_member.linkname = new_member.linkname[prefix_len:]
    elif member.isdev():
        print(f"No dev allowed! {member.name}")
        assert False
    if new_member.name == 'package.json':
        continue
    result_tar.addfile(new_member, orig_file)

system_var = args.system if len(args.system) != 1 else args.system[0]
package_json = {
    'name': args.name,
    'version': version,
    'system': system_var,
}
if args.description is not None:
    package_json['description'] = args.description
if args.description_url is not None:
    package_json['url'] = args.description_url
package_json = json.dumps(package_json, indent=2, sort_keys=True)
print(package_json)

package_json = package_json.encode()
data = BytesIO(package_json)
info = tarfile.TarInfo(name='package.json')
info.size = len(package_json)
set_tarinfo(info)
result_tar.addfile(tarinfo=info, fileobj=data)
result_tar.close()
download_tar.close()
result_file.close()
print(f"Done!")

print(f"Computing SHA1...")
result_file = result_path.open(mode='rb')
sha1 = hashlib.sha1()
while True:
    data = result_file.read(8192)
    if not data:
        break
    sha1.update(data)

sha1 = sha1.hexdigest()
print(f"SHA1: {sha1}")
result_file.close()

print(f"Uploading {result_path} as {asset_name}")

asset = rel.upload_asset(str(result_path), name=asset_name)
print(f"Done!")
asset_url = asset.browser_download_url
print(f"Asset URL: {asset_url}")

with open('manifest.json', 'r') as manifest_json:
    manifest = json.load(manifest_json)

manifest_obj = manifest.pop(args.name, [])
manifest_obj = [obj for obj in manifest_obj if (obj['system'] != system_var and obj['version'] != version)]
manifest[args.name] = manifest_obj
print("Updating manifest.json")
manjs = {
    'sha1': sha1,
    'url': asset_url,
    'system': system_var,
    'version': version,
}
print(manjs)
manifest_obj.append(manjs)

with open('manifest.json', 'w') as manifest_json:
    json.dump(manifest, manifest_json, indent=2, sort_keys=True)

download_file.close()
result_file.close()
