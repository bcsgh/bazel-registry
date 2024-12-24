# Copyright (c) 2024, Benjamin Shropshire,
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its contributors
#    may be used to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import argparse
import copy
import deepdiff  # pip install deepdiff
import git  # pip install GitPython
import json
import os

def SortPaths(root, files):
  md = {}
  src = {}

  for j in files:
    j_abs = os.path.abspath(j)
    j = j_abs.removeprefix(root)

    dr = os.path.dirname(j)
    fn = os.path.basename(j)

    if fn == "metadata.json":
      md[dr] = j_abs

    elif fn == "source.json":
      mod, ver = dr.split("/", maxsplit=1)
      src.setdefault(mod, {})[ver] = j_abs

    else:
      print(dr, fn)

  return md, src


def UpdateJson(update, f, new_json, old_json):
  if update:
    print("Writing ", f)
    with open(f, "wt") as w:
      json.dump(new_json, w, indent=2)
  else:
    diff = deepdiff.DeepDiff(new_json, old_json)
    if diff:
      print(f)
      print(json.dumps(new_json, indent=2))


def UpdateFile(update, f, new_str):
  if update:
    print("Writing ", f)
    with open(f, "wt") as w:
      w.write(new_str)
    pass
  else:
    if os.path.exists(f):
      with open(f, "r") as r:
        old_str = r.read()
    else:
      old_str = ""

    if old_str != new_str:
      print("  Difference ", f)


def main(args):
  root = os.path.abspath(args.prefix) + '/modules/'

  md, src = SortPaths(root, args.files)

  ##### Populate stuff

  for mod, metadata in md.items():
    print("=====\n%s" % mod)
    vers = [v for v in src.get(mod, {}).keys() if not v.startswith("local-")]

    #### Populate metadat.json
    with open(metadata, "r") as mdf:
      md_json = json.load(mdf)

    md_orig = copy.deepcopy(md_json)
    md_json["versions"] = vers
    UpdateJson(args.update, metadata, md_json, md_orig)

    #### Inspect local git repo
    r = os.path.join(os.path.dirname(metadata), "local_repo")
    if not os.path.exists(r):
      print("No git repo at %s" % r)
      continue

    repo = git.Repo(r)
    git_url = repo.remotes["origin"].url

    for ver in vers:
      if not ver in repo.tags:
        print("Unknown version %s in %s" % (ver, mod))
        continue

      verp = os.path.join(root, mod, ver)

      #### Populate source.json from git
      ver_sp = os.path.join(verp, "source.json")
      if os.path.exists(ver_sp):
        with open(ver_sp, "r") as spf:
          sp_json = json.load(spf)

        if sp_json and sp_json.get("type", "") != "git_repository":
          print("%s is of type %s" % (ver_sp, sp_json.get("type", "archive")))
        else:
          sp_orig = copy.deepcopy(sp_json)
          sp_json["type"] = "git_repository"
          sp_json["remote"] = git_url
          sp_json["tag"] = ver
          UpdateJson(args.update, ver_sp, sp_json, sp_orig)

      ## Populate MODULE.bazel from git
      blob = repo.tags[ver].commit.tree / "MODULE.bazel"
      body = blob.data_stream.read().decode('utf-8')
      mb = os.path.join(os.path.dirname(metadata), ver, "MODULE.bazel")
      UpdateFile(args.update, mb, body)

    for rem in repo.remotes:
      if not rem.name.startswith("/"): continue

      ### Dir
      lv = os.path.join(root, mod, "local-%s" % rem.name)
      if not os.path.exists(lv): os.mkdir(lv)

      ### sources.json
      lvs = os.path.join(lv, "source.json")
      if os.path.exists(lvs):
        with open(lvs, "r") as lvf:
          old_j = json.load(lvf)
      else:
        old_j = {}

      target = os.path.realpath(next(rem.urls))
      j = {
        "type": "local_path",
        "path": target,
      }

      UpdateJson(args.update, lvs, j, old_j)

      ### MODULE.bazel
      if args.update:
        mbl = os.path.join(lv, "MODULE.bazel")
        mbt = os.path.join(target, "MODULE.bazel")
        if not os.path.exists(mbl):
          print("Linking ", mbl)
          os.symlink(mbt, mbl)

  return 0;


if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--prefix", type=str, help="A prefix to remove from paths.")
  parser.add_argument("--update", default=False, action='store_true', help="Re-write the files.")
  parser.add_argument("files", type=str, nargs="*", help="input files")
  args = parser.parse_args()
  exit(main(args))
