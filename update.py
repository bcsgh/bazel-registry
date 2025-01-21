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
import glob
import git  # pip install GitPython
import json
import os

def SortPaths(root, files):
  md = {}
  src = {}

  files = [
    f
    for g in files
    for f in glob.glob(g)
  ]

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
      w.write("\n")
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


class NoOp:
  def __call__(self, *x, **y): return self
  def __getattr__(self, *x, **y): return self


def ParseModule(body):
  m_name = None
  m_version = None

  def Mod(name=False, version=False, **kwargs):
    nonlocal m_name
    nonlocal m_version
    if name: m_name = name
    if version: m_version = version

  noop = NoOp()
  g = {
      "__builtins__": {},
      "module": Mod,
      "bazel_dep": noop,
      "use_repo": noop,
      "register_toolchains": noop,

      "use_extension": noop,
      "use_repo_rule": noop,
  }
  exec(body, g)
  return m_name, m_version


def AddGit(update, root, repo_path):
  repo = git.Repo(repo_path)

  rm_path = os.path.join(repo_path, "MODULE.bazel")
  if "MODULE.bazel" in repo.head.commit.tree:
    blob = repo.head.commit.tree / "MODULE.bazel"
    body = blob.data_stream.read().decode('utf-8')
  elif os.path.exists(rm_path):
    with open(rm_path, "r") as f:
      body = f.read()
  else:
    print("Missing MODULE.bazel in git @%s." % repo_path)
    print("Missing MODULE.bazel in local @%s." % rm_path)
    return

  m_name, m_version = ParseModule(body)

  if not m_name: return
  print(m_name, "...")

  m_path = os.path.join(root, m_name)
  if not os.path.exists(m_path):
    if update:
      print( "  Making module")
      os.mkdir(m_path)
    else:
      print("Not found", m_path, "from", repo_path)

  r_path = os.path.join(m_path, "local_repo")
  if not os.path.exists(r_path):
    if update:
      print("  Linking repo")
      os.symlink(repo_path, r_path)
    else:
      print("Not found", r_path, "from", repo_path)

  md_path = os.path.join(m_path, "metadata.json")
  if not os.path.exists(md_path):
    if update:
      print("  Making metadata.json")
      with open(md_path, "w") as f:
        f.write("{}\n")
    else:
      print("Not found", md_path, "from", repo_path)

  v_path = os.path.join(m_path, m_version)
  if not os.path.exists(v_path):
    if update:
      print("  Making version", m_version)
      os.mkdir(v_path)
    else:
      print("Not found", v_path, "from", repo_path)

def main(args):
  root = os.path.abspath(args.prefix) + '/modules/'

  for repo in args.add_git or []:
    AddGit(args.update, root, repo)

  md, src = SortPaths(root, args.files)

  ##### Populate stuff

  for mod, metadata in md.items():
    print("=====\n%s" % mod)
    mod_dir = os.path.dirname(metadata)
    listing = [
        (v, os.path.join(mod_dir, v))
        for v in os.listdir(mod_dir)
    ]
    vers = [
        v
        for v, p in listing
        if os.path.isdir(p) and not os.path.islink(p)
    ]

    #### Populate metadat.json
    with open(metadata, "r") as mdf:
      md_json = json.load(mdf)

    md_orig = copy.deepcopy(md_json)
    md_json["versions"] = sorted(vers)
    UpdateJson(args.update, metadata, md_json, md_orig)

    #### Inspect local git repo
    r = os.path.join(mod_dir, "local_repo")
    if not os.path.exists(r):
      print("No git repo at %s" % r)
      continue

    repo = git.Repo(r)
    git_url = repo.remotes["origin"].url

    for t in repo.tags:
      if t.name in vers: continue
      if not "MODULE.bazel" in t.commit.tree: continue

      blob = t.commit.tree / "MODULE.bazel"
      body = blob.data_stream.read().decode('utf-8')

      m_name, m_version = ParseModule(body)
      if mod != m_name: continue
      if t.name != m_version:
        print("Mismated tag and version:", t.name, m_version)

      verp = os.path.join(root, mod, m_version)
      if not os.path.exists(verp): os.mkdir(verp)

      ver_sp = os.path.join(verp, "source.json")
      if not os.path.exists(ver_sp):
        print("Creating", mod, m_version)
        if args.update:
          with open(ver_sp, "w") as spf:
            spf.write("{}")

    for ver in vers:
      if not ver in repo.tags:
        print("Unknown version %s in %s" % (ver, mod))
        continue

      verp = os.path.join(root, mod, ver)

      #### Populate source.json from git
      ver_sp = os.path.join(verp, "source.json")
      if os.path.exists(verp):
        if os.path.exists(ver_sp):
          with open(ver_sp, "r") as spf:
            sp_json = json.load(spf)
        else:
          sp_json = {}

        if sp_json and sp_json.get("type", "") != "git_repository":
          print("%s is of type %s" % (ver_sp, sp_json.get("type", "archive")))
        else:
          sp_orig = copy.deepcopy(sp_json)
          sp_json["type"] = "git_repository"
          sp_json["remote"] = git_url

          if args.pin_commit:
            at = repo.tags[ver].commit
            sp_json["commit"] = at.hexsha
            sp_json["shallow_since"] = at.committed_datetime.strftime("%s %z")
            sp_json.pop("tag", None)
          else:
            sp_json.pop("commit", None)
            sp_json.pop("shallow_since", None)
            sp_json["tag"] = ver

          UpdateJson(args.update, ver_sp, sp_json, sp_orig)

      ## Populate MODULE.bazel from git
      rm_path = os.path.join(r, "MODULE.bazel")
      if "MODULE.bazel" in repo.tags[ver].commit.tree:
        blob = repo.tags[ver].commit.tree / "MODULE.bazel"
        body = blob.data_stream.read().decode('utf-8')
      elif os.path.exists(rm_path):
        with open(rm_path, "r") as f:
          body = f.read()
      else:
        print("Missing MODULE.bazel in git @%s." % ver)
        body = None

      if body:
        mb = os.path.join(mod_dir, ver, "MODULE.bazel")
        UpdateFile(args.update, mb, body)

  return 0;


if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--pin_commit", default=False, action='store_true', help="Use commit's rather than tags.")
  parser.add_argument("--prefix", type=str, help="A prefix to remove from paths.")
  parser.add_argument("--add_git", nargs='*', help="A prefix to remove from paths.")
  parser.add_argument("--update", default=False, action='store_true', help="Re-write the files.")
  parser.add_argument("files", type=str, nargs="*", help="input files")
  args = parser.parse_args()
  exit(main(args))
